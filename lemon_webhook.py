import os
import hmac
import hashlib
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Device, Payment

router = APIRouter(prefix="/lemonsqueezy", tags=["lemonsqueezy"])

WEBHOOK_SECRET = os.getenv("LEMON_WEBHOOK_SECRET")


def verify_signature(payload: bytes, signature: str):
    """
    LemonSqueezy sends X-Signature as a SHA256 hex digest.
    Sometimes prefixed with 'sha256='.
    """
    if not WEBHOOK_SECRET:
        raise HTTPException(500, "LEMON_WEBHOOK_SECRET missing")

    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Normalize signature
    signature = signature.replace("sha256=", "").strip()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")


@router.post("/webhook")
async def lemon_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    verify_signature(raw_body, signature)

    payload = await request.json()
    event = payload.get("meta", {}).get("event_name")

    # We only care about completed orders
    if event != "order_created":
        return {"status": "ignored"}

    attributes = payload["data"]["attributes"]

    # ✅ CORRECT LOCATION OF CUSTOM DATA
    custom = attributes.get("checkout_data", {}).get("custom", {})

    device_id = custom.get("device_id")
    credits = int(custom.get("credits", 0))

    if not device_id or credits <= 0:
        print("❌ Missing device_id or credits in webhook")
        return {"status": "missing_custom_data"}

    order_id = payload["data"]["id"]
    email = attributes.get("user_email")
    product_name = attributes.get("first_order_item", {}).get("product_name")
    amount = attributes.get("total")
    currency = attributes.get("currency", "USD")

    # ---------------------------
    # DUPLICATE PROTECTION
    # ---------------------------
    exists = db.query(Payment).filter(
        Payment.provider == "lemon",
        Payment.provider_payment_id == order_id
    ).first()

    if exists:
        return {"status": "duplicate"}

    # ---------------------------
    # CREDIT DEVICE
    # ---------------------------
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        print("❌ Device not found:", device_id)
        return {"status": "device_not_found"}

    old_credits = device.credits
    device.credits += credits

    db.add(Payment(
        device_id=device.id,
        provider="lemon",
        provider_payment_id=order_id,
        product_name=product_name,
        email=email,
        amount=amount,
        currency=currency,
        credits_added=credits,
        created_at=datetime.utcnow()
    ))

    db.commit()

    print(f"✅ LEMON PAYMENT CONFIRMED — credits {old_credits} → {device.credits}")

    return {"status": "success"}
