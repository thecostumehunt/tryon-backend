from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import Device
from auth_device import get_device

router = APIRouter()

# ----------------------------------
# 🎁 FREE CREDIT UNLOCK
# ----------------------------------
@router.post("/free/unlock")
def free_unlock(
    payload: dict,
    db: Session = Depends(get_db),
    device: Device = Depends(get_device)
):
    email = payload.get("email")

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")

    if device.free_used:
        raise HTTPException(status_code=403, detail="Free try already used")

    device.credits += 1
    device.free_used = True
    device.email = email
    device.last_seen = datetime.utcnow()

    db.commit()

    return {
        "message": "Free credit unlocked",
        "credits": device.credits
    }


# ----------------------------------
# 💳 GET CURRENT CREDITS
# ----------------------------------
@router.get("/credits")
def get_credits(device: Device = Depends(get_device)):
    return {
        "credits": device.credits,
        "free_used": device.free_used
    }


# ----------------------------------
# 🔒 LOCK CREDIT (ANTI-DOUBLE-SPEND)
# ----------------------------------
@router.post("/credits/lock")
def lock_credit(
    db: Session = Depends(get_db),
    device: Device = Depends(get_device)
):
    # Reload device row with DB-level lock
    device = (
        db.query(Device)
        .filter(Device.id == device.id)
        .with_for_update()
        .first()
    )

    if device.credits < 1:
        raise HTTPException(status_code=402, detail="No credits left")

    # Cooldown: 60 seconds between attempts
    if device.last_try_at:
        if (datetime.utcnow() - device.last_try_at).seconds < 60:
            raise HTTPException(
                status_code=429,
                detail="Please wait before trying again"
            )

    device.credits -= 1
    device.last_try_at = datetime.utcnow()

    db.commit()

    return {
        "message": "Credit locked",
        "credits_left": device.credits
    }


# ----------------------------------
# ↩️ REFUND CREDIT (ON FAILURE)
# ----------------------------------
@router.post("/credits/refund")
def refund_credit(
    db: Session = Depends(get_db),
    device: Device = Depends(get_device)
):
    if not device.last_try_at:
        raise HTTPException(
            status_code=400,
            detail="No recent credit to refund"
        )

    # Refund window: 5 minutes
    if (datetime.utcnow() - device.last_try_at).seconds > 300:
        raise HTTPException(
            status_code=400,
            detail="Refund window expired"
        )

    device.credits += 1
    device.last_try_at = None

    db.commit()

    return {
        "message": "Credit refunded",
        "credits": device.credits
    }


# ----------------------------------
# ✅ COMMIT CREDIT (ON SUCCESS)
# ----------------------------------
@router.post("/credits/commit")
def commit_credit(
    db: Session = Depends(get_db),
    device: Device = Depends(get_device)
):
    if not device.last_try_at:
        raise HTTPException(
            status_code=400,
            detail="No active credit lock"
        )

    device.total_tries += 1
    device.last_try_at = None

    db.commit()

    return {
        "message": "Credit committed",
        "total_tries": device.total_tries
    }
