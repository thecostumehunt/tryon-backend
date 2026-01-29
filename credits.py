from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from database import get_db
from models import Device
from auth_device import get_device

router = APIRouter()

# -------- FREE UNLOCK (already added) --------
@router.post("/free/unlock")
def free_unlock(payload: dict,
                db: Session = Depends(get_db),
                device: Device = Depends(get_device)):

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

    return {"message": "Free credit unlocked", "credits": device.credits}


# -------- CREDIT SYSTEM --------

@router.get("/credits")
def get_credits(device: Device = Depends(get_device)):
    return {
        "credits": device.credits,
        "free_used": device.free_used
    }


@router.post("/credits/lock")
def lock_credit(db: Session = Depends(get_db),
                device: Device = Depends(get_device)):

    if device.credits < 1:
        raise HTTPException(status_code=402, detail="No credits left")

    # cooldown protection (60s)
    if device.last_try_at:
        if (datetime.utcnow() - device.last_try_at).seconds < 60:
            raise HTTPException(status_code=429, detail="Please wait before trying again")

    device.credits -= 1
    device.last_try_at = datetime.utcnow()

    db.commit()

    return {"message": "Credit locked", "credits_left": device.credits}


@router.post("/credits/refund")
def refund_credit(db: Session = Depends(get_db),
                  device: Device = Depends(get_device)):

    device.credits += 1
    db.commit()

    return {"message": "Credit refunded", "credits": device.credits}


@router.post("/credits/commit")
def commit_credit(db: Session = Depends(get_db),
                  device: Device = Depends(get_device)):

    device.total_tries += 1
    db.commit()

    return {"message": "Credit committed", "total_tries": device.total_tries}
