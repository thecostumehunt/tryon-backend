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
    except:
        return None

# -------------------
# Core dependency
# -------------------

def get_device(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("Authorization")

    if token and token.startswith("Bearer "):
        token = token.replace("Bearer ", "")
        device_id = verify_device_token(token)

        if device_id:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                device.last_seen = datetime.utcnow()
                db.commit()
                return device

    # If no valid token → create new device
    ip = request.client.host
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
    request.state.new_device_token = token

    return new_device
