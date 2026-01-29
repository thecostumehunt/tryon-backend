# payments.py

import os
import razorpay
from fastapi import APIRouter, Depends, HTTPException
from auth_device import get_device
from models import Device

router = APIRouter(prefix="/payments", tags=["payments"])

RAZORPAY_KEY = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY or not RAZORPAY_SECRET:
    raise RuntimeError("Razorpay keys not set in environment")

client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))

# amount in paise
PACKS = {
    "5":  {"amount": 20000,  "credits": 5,   "label": "5 Try Pack"},
    "15": {"amount": 50000,  "credits": 15,  "label": "15 Try Pack"},
    "100":{"amount": 200000, "credits": 100, "label": "100 Try Pack"},
}


@router.post("/create-link")
def create_payment_link(pack: str, device: Device = Depends(get_device)):

    if pack not in PACKS:
        raise HTTPException(status_code=400, detail="Invalid pack")

    pack_data = PACKS[pack]

    link = client.payment_link.create({
        "amount": pack_data["amount"],
        "currency": "INR",
        "description": pack_data["label"],
        "customer": {
            "name": "AI Try-On User"
        },
        "notify": {
            "sms": False,
            "email": False
        },
        "notes": {
            "device_id": str(device.id),
            "credits": str(pack_data["credits"])
        },
        "callback_url": "https://YOUR_STREAMLIT_URL?payment=success",
        "callback_method": "get"
    })

    return {
        "payment_url": link["short_url"]
    }
