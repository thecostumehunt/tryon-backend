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

def hash_text(text: str):
    """Match auth_device hash function exactly"""
    return hashlib.sha256(text.encode()).hexdigest()

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
    
    # ✅ FIXED: Use FINGERPRINT instead of device_token
    custom = payload.get("meta", {}).get("custom_data", {})
    fingerprint = custom.get("fingerprint")
    credits = int(custom.get("credits", 0))
    
    if not fingerprint:
        return {"status": "missing fingerprint"}
    
    if credits == 0:
        return {"status": "invalid credits"}
    
    # ✅ Find device by fingerprint hash (SAME as auth_device.py)
    fp_hash = hash_text(fingerprint)
    device = db.query(Device).filter(Device.fingerprinthash == fp_hash).first()
    
    if not device:
        # Create new device if no fingerprint match (rare)
        device = Device(
            id=uuid.uuid4(),
            fingerprinthash=fp_hash,
            credits=0,
            created_at=datetime.utcnow(),
            last_seen=datetime.utcnow()
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    
    # Check for duplicate payment
    order_id = payload["data"]["id"]
    if db.query(Payment).filter(
        Payment.provider == "lemon", 
        Payment.provider_payment_id == order_id
    ).first():
        return {"status": "duplicate"}
    
    # Add credits
    old_credits = device.credits
    device.credits += credits
    
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
    
    print(f"LEMON PAYMENT CONFIRMED: fingerprint={fp_hash[:8]} {old_credits} → {device.credits}")
    
    return {"status": "success"}
