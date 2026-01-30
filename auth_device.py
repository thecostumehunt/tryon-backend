import uuid
import os
import hashlib
from datetime import datetime, timedelta
from jose import jwt
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import get_db
from models import Device

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

# -------------------
# Helpers
# -------------------

def hash_text(text: str):
    return hashlib.sha256(text.encode()).hexdigest()

def create_device_token(device_id: str):
    payload = {
        "device_id": device_id,
        "exp": datetime.utcnow() + timedelta(days=365)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_device_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["device_id"]
    except Exception:
        return None

# -------------------
# Core dependency
# -------------------

def get_device(
    request: Request,
    db: Session = Depends(get_db)
):
    auth = request.headers.get("Authorization")

    # -------------------
    # EXISTING DEVICE
    # -------------------
    if auth and auth.startswith("Bearer "):
        token = auth.replace("Bearer ", "").strip()
        device_id = verify_device_token(token)

        if device_id:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                device.last_seen = datetime.utcnow()
                db.commit()

                # 🔑 CRITICAL FIX (attach token)
                device.token = token

                return device

    # -------------------
    # NEW DEVICE
    # -------------------
    ip = request.client.host if request.client else "unknown"
    ip_hash = hash_text(ip)

    new_device = Device(
        id=uuid.uuid4(),
        ip_hash=ip_hash,
        created_at=datetime.utcnow(),
        last_seen=datetime.utcnow()
    )

    db.add(new_device)
    db.commit()
    db.refresh(new_device)

    token = create_device_token(str(new_device.id))

    # 🔑 CRITICAL FIX (attach token)
    new_device.token = token

    # expose token for /device/init response
    request.state.new_device_token = token

    return new_device
