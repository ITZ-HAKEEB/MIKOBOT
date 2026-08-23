import os
import hmac
import hashlib
import time
import razorpay
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_TTMTAdfV2IGKfV")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "ItDbZI5Z3wxpA6X59Ur2iB99")

# Initialize Razorpay Client
_razorpay_client: Optional[razorpay.Client] = None
try:
    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
        _razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        print("✅ Razorpay Client initialized successfully!")
except Exception as e:
    print(f"⚠️ Razorpay init warning: {e}")


def get_razorpay_client() -> Optional[razorpay.Client]:
    global _razorpay_client
    if _razorpay_client is None and RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
        try:
            _razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        except Exception:
            pass
    return _razorpay_client


def create_order(user_id: int, amount_paise: int, plan_name: str = "Starter Pack", receipt: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a Razorpay Order.
    Amount must be in paise (e.g. 100 paise = 1 INR). Minimum amount: 100 paise.
    """
    if amount_paise < 100:
        raise ValueError("Minimum order amount is 100 paise (₹1.00)")

    client = get_razorpay_client()
    if not client:
        raise RuntimeError("Razorpay credentials not configured.")

    if not receipt:
        receipt = f"rcpt_{user_id}_{int(time.time())}"

    order_payload = {
        "amount": int(amount_paise),
        "currency": "INR",
        "receipt": receipt[:40],
        "notes": {
            "telegram_user_id": str(user_id),
            "plan_name": plan_name,
        }
    }

    order = client.order.create(data=order_payload)
    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "key_id": RAZORPAY_KEY_ID,
    }


def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Verify payment signature using HMAC-SHA256.
    HMAC-SHA256(order_id + "|" + payment_id, KEY_SECRET) == signature
    """
    if not order_id or not payment_id or not signature:
        return False

    client = get_razorpay_client()
    if client:
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            })
            return True
        except Exception:
            pass

    # Fallback to direct HMAC-SHA256 verification
    try:
        msg = f"{order_id}|{payment_id}".encode("utf-8")
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode("utf-8"),
            msg,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(generated_signature, signature)
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False
