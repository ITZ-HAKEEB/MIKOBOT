import os
import json
import asyncio
from aiohttp import web
from typing import Optional
from modules.payment.razorpay_gateway import create_order, verify_signature, RAZORPAY_KEY_ID
from modules.utils.storage import get_user, update_user
from modules.utils.logger import send_log_message

PLANS = {
    "starter": {"name": "Starter Gems Pack", "amount_paise": 4900, "gems": 6.0, "premium": False},
    "month_vip": {"name": "1 Month VIP Subscription", "amount_paise": 9900, "gems": 12.0, "premium": True},
    "vip_pro": {"name": "3 Months Pro VIP", "amount_paise": 24900, "gems": 35.0, "premium": True},
}


async def handle_create_order(request: web.Request) -> web.Response:
    """POST /api/create-order"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    user_id = data.get("user_id") or 0
    amount = data.get("amount") # in paise or INR
    plan_key = data.get("plan_key", "starter")

    if plan_key in PLANS:
        amount_paise = PLANS[plan_key]["amount_paise"]
        plan_name = PLANS[plan_key]["name"]
    elif amount:
        # If amount provided in INR or paise
        amount_paise = int(amount * 100) if amount < 1000 else int(amount)
        plan_name = data.get("plan_name", "Custom Topup")
    else:
        amount_paise = 4900
        plan_name = "Starter Gems Pack"

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
    plan_key = data.get("plan_key", "starter")

    if not order_id or not payment_id or not signature:
        return web.json_response({"error": "Missing order_id, payment_id, or signature"}, status=400)

    is_valid = verify_signature(order_id, payment_id, signature)
    if not is_valid:
        return web.json_response({"success": False, "error": "Signature verification failed! Payment rejected."}, status=400)

    # Valid Payment: Credit User Account in Database!
    credited = False
    if user_id and str(user_id).isdigit():
        uid = int(user_id)
        ud = get_user(uid)
        plan_info = PLANS.get(plan_key, {"gems": 6.0, "premium": False, "name": "Payment Topup"})
        
        new_gems = round(ud.get("gems", 0.0) + plan_info["gems"], 2)
        updates = {"gems": new_gems}
        if plan_info["premium"]:
            updates["premium"] = True
        
        update_user(uid, **updates)
        credited = True
        print(f"🎉 Successfully credited {plan_info['gems']} gems to User {uid} (Payment ID: {payment_id})")

    return web.json_response({
        "success": True,
        "message": "Payment verified successfully!",
        "order_id": order_id,
        "payment_id": payment_id,
        "credited": credited,
    })


async def handle_config(request: web.Request) -> web.Response:
    """GET /api/config"""
    return web.json_response({
        "key_id": RAZORPAY_KEY_ID,
        "currency": "INR",
        "plans": PLANS,
    })


def create_payment_app() -> web.Application:
    app = web.Application()
    # CORS middleware
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
    app.router.add_get("/api/config", handle_config)
    return app
