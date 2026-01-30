import os
import hmac
import hashlib
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Device, Payment
from auth_device import verify_device_token  # Add this import

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
    # Verify signature first
    raw_body = await request.body()
    signature = request.headers.get("X-Signature")
    if not signature:
        raise HTTPException(400, "Missing signature")
    
    verify_signature(raw_body, signature)
    
    # Parse payload
    payload = await request.json()
    event = payload.get("meta", {}).get("event_name")
    
    if event != "order_created":
        return {"status": "ignored"}
    
    # ✅ NEW: Use device_token instead of deviceid
    custom = payload.get("meta", {}).get("custom_data", {})
    device_token = custom.get("device_token")
    credits = int(custom.get("credits", 0))
    
    if not device_token:
        return {"status": "missing device_token"}
    
    if credits == 0:
        return {"status": "invalid credits"}
    
    # Extract device ID from token
    device_id = verify_device_token(device_token)
    if not device_id:
        return {"status": "invalid device_token"}
    
    # Check for duplicate payment
    order_id = payload["data"]["id"]
    if db.query(Payment).filter(
        Payment.provider == "lemon", 
        Payment.provider_payment_id == order_id
    ).first():
        return {"status": "duplicate"}
    
    # Find or create device
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
    
    # Add credits
    old_credits = device.credits
    device.credits += credits
    db.add(device)
    
    # Log payment
    payment = Payment(
        device_id=device.id,
        provider="lemon",
        provider_payment_id=order_id,
        product_name=payload["data"]["attributes"].get("first_order_item", {}).get("product_name"),
        email=payload["data"]["attributes"].get("user_email"),
        amount=payload["data"]["attributes"].get("total"),
        currency=payload["data"]["attributes"].get("currency", "USD"),
        credits_added=credits,
        created_at=datetime.utcnow()
    )
    db.add(payment)
    db.commit()
    
    print(f"LEMON PAYMENT CONFIRMED: {old_credits} → {device.credits}")
    
    return {"status": "success"}
