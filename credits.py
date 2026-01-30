from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import Device
from auth_device import get_device

router = APIRouter()

# -------------------------
# FREE CREDIT UNLOCK
# -------------------------
@router.post("/free/unlock")
def free_unlock(
    payload: dict,
    db: Session = Depends(get_db),
    device: Device = Depends(get_device)
):
    email = payload.get("email")

    if not email or "@" not in email:
        raise HTTPException(400, "Valid email required")

    # ❌ Already used on this device
    if device.free_used:
        raise HTTPException(403, "Free credit already used")

    # ❌ Email reuse across devices
    email_used = db.query(Device).filter(
        Device.email == email
    ).first()

    if email_used:
        raise HTTPException(403, "Free credit already used with this email")

    # ❌ Too many free attempts from same IP
    ip_abuse = db.query(Device).filter(
        Device.ip_hash == device.ip_hash,
        Device.free_used == True
    ).count()

    if ip_abuse >= 3:
        raise HTTPException(
            429,
            "Too many free attempts from this network"
        )

    # ✅ Grant free credit
    device.credits += 1
    device.free_used = True
    device.email = email
    device.last_seen = datetime.utcnow()

    db.commit()

    return {
        "message": "Free credit unlocked",
        "credits": device.credits
    }


# -------------------------
# CREDIT INFO
# -------------------------
@router.get("/credits")
def get_credits(device: Device = Depends(get_device)):
    return {
        "credits": device.credits,
        "free_used": device.free_used
    }
