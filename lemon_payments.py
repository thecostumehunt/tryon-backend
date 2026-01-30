import os
import requests
from fastapi import APIRouter, Depends, HTTPException
from auth_device import get_device
from models import Device

router = APIRouter(prefix="/lemon", tags=["lemon"])

LEMON_API_KEY = os.getenv("LEMON_API_KEY")
LEMON_STORE_ID = os.getenv("LEMON_STORE_ID")

VARIANTS = {
    "5": os.getenv("LEMON_VARIANT_5"),
    "15": os.getenv("LEMON_VARIANT_15"),
    "100": os.getenv("LEMON_VARIANT_100"),
}


@router.post("/create-link")
def create_lemon_checkout(
    pack: str,
    device: Device = Depends(get_device),
):
    if not LEMON_API_KEY:
        raise HTTPException(500, "LEMON_API_KEY missing")

    if not LEMON_STORE_ID:
        raise HTTPException(500, "LEMON_STORE_ID missing")

    if pack not in VARIANTS or not VARIANTS[pack]:
        raise HTTPException(400, "Invalid credit pack")

    # 🔑 device.token not required here anymore
    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {
                    "custom": {
                        # used by webhook ONLY
                        "device_id": str(device.id),
                        "credits": pack,
                    }
                }
            },
            "relationships": {
                "store": {
                    "data": {
                        "type": "stores",
                        "id": LEMON_STORE_ID
                    }
                },
                "variant": {
                    "data": {
                        "type": "variants",
                        "id": VARIANTS[pack]
                    }
                }
            }
        }
    }

    headers = {
        "Authorization": f"Bearer {LEMON_API_KEY}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    }

    r = requests.post(
        "https://api.lemonsqueezy.com/v1/checkouts",
        json=payload,
        headers=headers,
        timeout=20,
    )

    if r.status_code not in (200, 201):
        raise HTTPException(400, r.text)

    checkout_url = r.json()["data"]["attributes"]["url"]
    return {"checkout_url": checkout_url}
