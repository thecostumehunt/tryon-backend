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
    digest = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(digest, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")


@router.post("/webhook")
async def lemon_webhook(request: Request, db: Session = Depends(get_db)):

    body = await request.body()
    signature = request.headers.get("X-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    verify_signature(body, signature)

    payload = await request.json()
    event = payload.get("meta", {}).get("event_name")

    if event != "order_created":
        return {"status": "ignored"}

    custom = payload.get("meta", {}).get("custom_data", {})

    device_id = custom.get("device_id")
    credits = int(custom.get("credits", 0))

    order_id = payload["data"]["id"]
    attributes = payload["data"]["attributes"]

    email = attributes.get("user_email")
    product_name = attributes.get("first_order_item", {}).get("product_name")
    amount = attributes.get("total")
    currency = attributes.get("currency", "USD")

    if not device_id or credits == 0:
        return {"status": "missing_custom_data"}

    # prevent duplicates
    exists = db.query(Payment).filter(
        Payment.provider_payment_id == order_id
    ).first()

    if exists:
        return {"status": "duplicate"}

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        return {"status": "device_not_found"}

    old = device.credits
    device.credits += credits
    db.commit()

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

    print(f"✅ LEMON PAYMENT CONFIRMED — credits {old} → {device.credits}")

    return {"status": "success"}
