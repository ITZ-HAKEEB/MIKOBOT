import os
import json
import asyncio
from aiohttp import web
from typing import Optional
from modules.payment.razorpay_gateway import create_order, verify_signature, RAZORPAY_KEY_ID
from modules.utils.storage import get_user, update_user
from modules.utils.logger import send_log_message

PLANS = {
    "1_month": {"name": "1 Month Premium", "amount_paise": 1500, "months": 1, "free_gems": 1.0, "price_inr": 15},
    "2_months": {"name": "2 Months Premium", "amount_paise": 3000, "months": 2, "free_gems": 2.0, "price_inr": 30},
    "3_months": {"name": "3 Months Premium", "amount_paise": 4000, "months": 3, "free_gems": 3.0, "price_inr": 40},
    "6_months": {"name": "6 Months Premium", "amount_paise": 5000, "months": 6, "free_gems": 6.0, "price_inr": 50},
    "12_months": {"name": "12 Months Premium", "amount_paise": 7500, "months": 12, "free_gems": 12.0, "price_inr": 75},
}


async def handle_create_order(request: web.Request) -> web.Response:
    """POST /api/create-order"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    user_id = data.get("user_id") or 0
    amount = data.get("amount")
    plan_key = data.get("plan_key", "1_month")

    if plan_key in PLANS:
        amount_paise = PLANS[plan_key]["amount_paise"]
        plan_name = PLANS[plan_key]["name"]
    elif amount:
        amount_paise = int(amount * 100) if amount < 1000 else int(amount)
        plan_name = data.get("plan_name", "Custom Premium Plan")
    else:
        amount_paise = 1500
        plan_name = "1 Month Premium"

    if amount_paise < 100:
        return web.json_response({"error": "Amount must be at least ₹1.00 (100 paise)"}, status=400)

    try:
        order_info = create_order(
            user_id=int(user_id) if str(user_id).isdigit() else 0,
            amount_paise=amount_paise,
            plan_name=plan_name
        )
        return web.json_response(order_info)
    except ValueError as ve:
        return web.json_response({"error": str(ve)}, status=400)
    except Exception as e:
        print(f"Error creating Razorpay order: {e}")
        return web.json_response({"error": "Failed to create order with Razorpay", "details": str(e)}, status=500)


async def handle_verify_payment(request: web.Request) -> web.Response:
    """POST /api/verify-payment"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    order_id = data.get("razorpay_order_id") or data.get("order_id")
    payment_id = data.get("razorpay_payment_id") or data.get("payment_id")
    signature = data.get("razorpay_signature") or data.get("signature")
    user_id = data.get("user_id")
    plan_key = data.get("plan_key", "1_month")

    if not order_id or not payment_id or not signature:
        return web.json_response({"error": "Missing order_id, payment_id, or signature"}, status=400)

    is_valid = verify_signature(order_id, payment_id, signature)
    if not is_valid:
        return web.json_response({"success": False, "error": "Signature verification failed! Payment rejected."}, status=400)

    # Valid Payment: Activate Premium & Credit Free Bonus Gems!
    credited = False
    if user_id and str(user_id).isdigit():
        uid = int(user_id)
        ud = get_user(uid)
        plan_info = PLANS.get(plan_key, {"free_gems": 1.0, "name": "1 Month Premium", "months": 1})
        free_gems = plan_info.get("free_gems", 1.0)
        
        new_gems = round(ud.get("gems", 0.0) + free_gems, 2)
        updates = {
            "gems": new_gems,
            "premium": True,
        }
        
        update_user(uid, **updates)
        credited = True
        print(f"🎉 Successfully activated VIP Premium and credited {free_gems} free gems to User {uid} (Payment ID: {payment_id})")

    return web.json_response({
        "success": True,
        "message": f"Payment verified successfully! VIP Premium activated with {PLANS.get(plan_key, {}).get('free_gems', 1)} free gem(s).",
        "order_id": order_id,
        "payment_id": payment_id,
        "credited": credited,
    })


async def handle_razorpay_webhook(request: web.Request) -> web.Response:
    """POST /api/razorpay-webhook - Auto verify manual Razorpay / UPI payments"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    event = data.get("event", "")
    print(f"🔔 [RAZORPAY WEBHOOK] Received event: {event}")

    if event in ["payment.captured", "order.paid"]:
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        amount_paise = payment_entity.get("amount", 0)
        amount_inr = amount_paise / 100
        notes = payment_entity.get("notes", {})
        description = payment_entity.get("description", "")
        contact = payment_entity.get("contact", "")
        email = payment_entity.get("email", "")

        # Try to extract user_id from notes, description, or custom fields
        target_uid = None
        for k in ["user_id", "telegram_id", "id", "uid", "tg_id"]:
            if k in notes and str(notes[k]).isdigit():
                target_uid = int(notes[k])
                break

        if not target_uid:
            # Check description for numbers
            import re
            numbers = re.findall(r"\b\d{8,12}\b", description + " " + json.dumps(notes))
            if numbers:
                target_uid = int(numbers[0])

        # Map amount to plan
        plan_months = 1
        free_gems = 1.0
        if amount_inr >= 75:
            plan_months = 12
            free_gems = 12.0
        elif amount_inr >= 50:
            plan_months = 6
            free_gems = 6.0
        elif amount_inr >= 40:
            plan_months = 3
            free_gems = 3.0
        elif amount_inr >= 30:
            plan_months = 2
            free_gems = 2.0
        elif amount_inr >= 15:
            plan_months = 1
            free_gems = 1.0

        if target_uid:
            ud = get_user(target_uid)
            new_gems = round(ud.get("gems", 0.0) + free_gems, 2)
            new_prem_wallet = round(ud.get("prem_wallet", 0.0) + amount_inr, 2)
            update_user(target_uid, premium=True, gems=new_gems, prem_wallet=new_prem_wallet)
            print(f"🎉 [AUTO-VERIFIED] ₹{amount_inr} payment captured! Activated {plan_months} Month(s) Premium for User {target_uid} (+{free_gems} Gems, Wallet: ₹{new_prem_wallet})")

    return web.json_response({"status": "ok"})


async def handle_user_profile(request: web.Request) -> web.Response:
    """GET /api/user-profile?user_id=123456789"""
    uid_str = request.query.get("user_id", "").strip()
    if not uid_str or not uid_str.isdigit():
        return web.json_response({"error": "Invalid or missing user_id parameter"}, status=400)

    uid = int(uid_str)
    all_users = get_all_users()
    ud = get_user(uid)

    # Calculate global ranking positions
    sorted_rich = sorted(all_users.items(), key=lambda x: x[1].get("balance", 0) + x[1].get("wallet_balance", 0), reverse=True)
    sorted_kills = sorted(all_users.items(), key=lambda x: x[1].get("kills", 0), reverse=True)
    sorted_robs = sorted(all_users.items(), key=lambda x: x[1].get("robs", 0), reverse=True)
    sorted_bombs = sorted(all_users.items(), key=lambda x: x[1].get("bomb_wins", 0), reverse=True)

    def find_rank(sorted_list, target_uid):
        for idx, (k, _) in enumerate(sorted_list, 1):
            if int(k) == target_uid:
                return idx
        return len(sorted_list)

    rank_rich = find_rank(sorted_rich, uid)
    rank_kills = find_rank(sorted_kills, uid)
    rank_robs = find_rank(sorted_robs, uid)
    rank_bombs = find_rank(sorted_bombs, uid)

    import time
    is_protected = bool(ud.get("protected", False))
    protected_until = ud.get("protected_until") or 0
    rem_protect = max(0, int(protected_until - time.time())) if is_protected else 0

    xp = ud.get("xp", 0)
    xp_max = ud.get("xp_max", 1000) or 1000
    xp_percent = min(100, int((xp / xp_max) * 100))

    response_data = {
        "user_id": uid,
        "username": ud.get("username") or "User",
        "display_name": ud.get("display_name") or ud.get("username") or f"User {uid}",
        "custom_emoji": ud.get("emoji") or "",
        "bio": ud.get("intro_text") or "No custom intro set yet.",
        "status": ud.get("status", "alive"),
        "premium": bool(ud.get("premium", False)),
        "level": ud.get("level", 1),
        "xp": xp,
        "xp_max": xp_max,
        "xp_percent": xp_percent,
        "balances": {
            "cash": ud.get("balance", 0),
            "bank": ud.get("wallet_balance", 0),
            "net_worth": ud.get("balance", 0) + ud.get("wallet_balance", 0),
            "gems": ud.get("gems", 0.0),
            "prem_wallet": ud.get("prem_wallet", 0.0),
        },
        "stats": {
            "kills": ud.get("kills", 0),
            "daily_kills": ud.get("daily_kills", 0),
            "robs": ud.get("robs", 0),
            "daily_robs": ud.get("daily_robs", 0),
            "bomb_wins": ud.get("bomb_wins", 0),
            "protected": is_protected and rem_protect > 0,
            "protection_remaining_seconds": rem_protect,
        },
        "rankings": {
            "rich_rank": rank_rich,
            "kills_rank": rank_kills,
            "robs_rank": rank_robs,
            "bombs_rank": rank_bombs,
            "total_players": len(all_users),
        },
        "powers": ud.get("powers", []),
        "friends_count": len(ud.get("friends", {})),
    }

    return web.json_response(response_data)


async def handle_purchase_premium_wallet(request: web.Request) -> web.Response:
    """POST /api/purchase-premium-wallet - Deduct funds from premium wallet and activate VIP"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

    uid = int(data.get("user_id", 0))
    plan_key = data.get("plan_key", "1_month")

    if not uid:
        return web.json_response({"success": False, "error": "User ID is required"}, status=400)

    if plan_key not in PLANS:
        return web.json_response({"success": False, "error": f"Invalid plan: {plan_key}"}, status=400)

    plan = PLANS[plan_key]
    cost_inr = plan["amount_paise"] / 100
    free_gems = float(plan.get("free_gems", 1.0))

    ud = get_user(uid)
    curr_wallet = float(ud.get("prem_wallet", 0.0) or 0.0)

    if curr_wallet < cost_inr:
        return web.json_response({
            "success": False,
            "error": "Insufficient wallet balance",
            "required": cost_inr,
            "current_wallet": curr_wallet,
            "shortage": round(cost_inr - curr_wallet, 2),
            "razorpay_url": "https://razorpay.me/@nishkarshkumar"
        }, status=400)

    new_wallet = round(curr_wallet - cost_inr, 2)
    new_gems = round(float(ud.get("gems", 0.0) or 0.0) + free_gems, 2)

    update_user(uid, prem_wallet=new_wallet, premium=True, gems=new_gems)

    return web.json_response({
        "success": True,
        "message": f"🎉 Successfully activated {plan['name']}! ₹{cost_inr} deducted from your Premium Wallet (+{free_gems} Gems added).",
        "plan_name": plan["name"],
        "cost": cost_inr,
        "remaining_wallet": new_wallet,
        "gems": new_gems,
        "premium": True
    })


async def handle_leaderboards(request: web.Request) -> web.Response:
    """GET /api/leaderboards"""
    all_users = get_all_users()

    def format_top(sorted_list, key_name, extra_key=None):
        out = []
        for idx, (uid, info) in enumerate(sorted_list[:20], 1):
            val = info.get(key_name, 0)
            if extra_key:
                val += info.get(extra_key, 0)
            out.append({
                "rank": idx,
                "user_id": int(uid),
                "name": info.get("display_name") or info.get("username") or f"User {uid}",
                "username": info.get("username") or "",
                "premium": bool(info.get("premium", False)),
                "custom_emoji": info.get("emoji") or "",
                "value": val,
            })
        return out

    sorted_rich = sorted(all_users.items(), key=lambda x: x[1].get("balance", 0) + x[1].get("wallet_balance", 0), reverse=True)
    sorted_kills = sorted(all_users.items(), key=lambda x: x[1].get("kills", 0), reverse=True)
    sorted_robs = sorted(all_users.items(), key=lambda x: x[1].get("robs", 0), reverse=True)
    sorted_bombs = sorted(all_users.items(), key=lambda x: x[1].get("bomb_wins", 0), reverse=True)

    return web.json_response({
        "total_players": len(all_users),
        "richest": format_top(sorted_rich, "balance", "wallet_balance"),
        "killers": format_top(sorted_kills, "kills"),
        "robbers": format_top(sorted_robs, "robs"),
        "bomb_masters": format_top(sorted_bombs, "bomb_wins"),
    })


async def handle_config(request: web.Request) -> web.Response:
    """GET /api/config"""
    return web.json_response({
        "key_id": RAZORPAY_KEY_ID,
        "currency": "INR",
        "plans": PLANS,
        "add_fund_url": "https://razorpay.me/@nishkarshkumar"
    })


def create_payment_app() -> web.Application:
    app = web.Application()
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            if request.method == "OPTIONS":
                return web.Response(
                    status=200,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization",
                    },
                )
            response = await handler(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            return response
        return middleware_handler

    app.middlewares.append(cors_middleware)
    app.router.add_post("/api/create-order", handle_create_order)
    app.router.add_post("/api/verify-payment", handle_verify_payment)
    app.router.add_post("/api/razorpay-webhook", handle_razorpay_webhook)
    app.router.add_post("/api/purchase-premium-wallet", handle_purchase_premium_wallet)
    app.router.add_get("/api/user-profile", handle_user_profile)
    app.router.add_get("/api/leaderboards", handle_leaderboards)
    app.router.add_get("/api/config", handle_config)
    return app

