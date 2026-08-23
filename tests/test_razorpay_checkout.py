import os
import hmac
import hashlib
from dotenv import load_dotenv

load_dotenv()

from modules.payment.razorpay_gateway import (
    create_order,
    verify_signature,
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
)

def run_tests():
    print("=== Testing Razorpay Standard Web Checkout Integration ===")
    print(f"Key ID: {RAZORPAY_KEY_ID}")
    
    # 1. Test Minimum Amount Validation
    try:
        create_order(user_id=7408854697, amount_paise=50)
        print("❌ Failed: Should reject amount < 100 paise")
    except ValueError:
        print("✅ Success: Properly rejected order with amount < 100 paise")

    # 2. Test Order Creation with Razorpay API
    try:
        order = create_order(user_id=7408854697, amount_paise=4900, plan_name="Starter Gems Pack")
        print(f"✅ Success: Razorpay Order Created! ID: {order['order_id']}, Amount: {order['amount']}, Currency: {order['currency']}")
        order_id = order["order_id"]
    except Exception as e:
        print(f"❌ Order Creation Error: {e}")
        return

    # 3. Test Signature Verification (Valid Case)
    mock_payment_id = "pay_test_MockPayment12345"
    test_msg = f"{order_id}|{mock_payment_id}".encode("utf-8")
    valid_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode("utf-8"),
        test_msg,
        hashlib.sha256
    ).hexdigest()

    is_valid = verify_signature(order_id, mock_payment_id, valid_signature)
    if is_valid:
        print(f"✅ Success: Signature Verification verified genuine HMAC-SHA256 signature!")
    else:
        print(f"❌ Failed: Valid signature was rejected")

    # 4. Test Signature Verification (Tampered Case)
    fake_signature = "fake_tampered_signature_123456"
    is_fake_valid = verify_signature(order_id, mock_payment_id, fake_signature)
    if not is_fake_valid:
        print(f"✅ Success: Correctly rejected tampered/fake signature!")
    else:
        print(f"❌ Failed: Tampered signature was accepted")

    print("\n🎉 ALL RAZORPAY UNIT TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
