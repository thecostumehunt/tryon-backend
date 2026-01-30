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
    """
    if not WEBHOOK_SECRET:
        raise HTTPException(500, "LEMON_WEBHOOK_SECRET missing")

    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    signature = signature.replace("sha256=", "").strip()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")


@router.post("/webhook")
async def lemon_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-Signature")

    if not signature:
        raise HTTPException(400, "Missing signature")

    verify_signature(raw_body, signature)

    payload = await request.json()
    event = payload.get("meta", {}).get("event_name")

    if event != "order_created":
        return {"status": "ignored"}

    # ✅ CORRECT PLACE (from your real payload)
    custom = payload.get("meta", {}).get("custom_data", {})

    device_id = custom.get("device_id")
    credits = int(custom.get("credits", 0))

    if not device_id:
        return {"status": "missing_device_id"}

    if credits <= 0:
        return {"status": "invalid_credits"}

    order_id = payload["data"]["id"]
    attributes = payload["data"]["attributes"]

    email = attributes.get("user_email")
    product_name = attributes.get("first_order_item", {}).get("product_name")
    amount = attributes.get("total")
    currency = attributes.get("currency", "USD")

    # ---------------------------
    # DUPLICATE PROTECTION
    # ---------------------------
    if db.query(Payment).filter(
        Payment.provider == "lemon",
        Payment.provider_payment_id == order_id
    ).first():
        return {"status": "duplicate"}

    # ---------------------------
    # DEVICE RECOVERY (CRITICAL)
    # ---------------------------
    device = db.query(Device).filter(Device.id == device_id).first()

    if not device:
        device = Device(
            id=device_id,
            credits=0,
            created_at=datetime.utcnow(),
            last_seen=datetime.utcnow()
        )
        db.add(device)
        db.commit()
        db.refresh(device)

    # ---------------------------
    # CREDIT USER
    # ---------------------------
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
