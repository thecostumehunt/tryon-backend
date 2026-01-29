import os
import paypalrestsdk
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth_device import get_device
from models import Device

router = APIRouter(prefix="/paypal", tags=["paypal"])

paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

# USD pricing
PACKS = {
    "5":   {"price": "2.00",  "credits": 5},
    "15":  {"price": "5.00",  "credits": 15},
    "100": {"price": "20.00", "credits": 100}
}

@router.post("/create-link")
def create_paypal_link(
    pack: str,
    device: Device = Depends(get_device),
    db: Session = Depends(get_db)
):
    if pack not in PACKS:
        raise HTTPException(status_code=400, detail="Invalid pack")

    data = PACKS[pack]

    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": "https://your-frontend.com/payment-success",
            "cancel_url": "https://your-frontend.com/payment-cancel"
        },
        "transactions": [{
            "amount": {
                "total": data["price"],
                "currency": "USD"
            },
            "description": f"{data['credits']} AI Try-On Credits",
            "custom": f"{device.id}:{data['credits']}"
        }]
    })

    if payment.create():
        approval_url = next(
            link.href for link in payment.links if link.rel == "approval_url"
        )
        return {"payment_url": approval_url}

    raise HTTPException(status_code=400, detail=str(payment.error))
