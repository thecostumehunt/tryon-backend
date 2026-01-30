import os
import requests
from fastapi import APIRouter, Depends, HTTPException
from auth_device import get_device
from models import Device

router = APIRouter(prefix="/lemon", tags=["lemon"])

# ----------------------------------
# ENV VARIABLES (MATCH RENDER)
# ----------------------------------
LEMON_API_KEY = os.getenv("LEMON_API_KEY")
LEMON_STORE_ID = os.getenv("LEMON_STORE_ID")

VARIANTS = {
    "5": os.getenv("LEMON_VARIANT_5"),
    "15": os.getenv("LEMON_VARIANT_15"),
    "100": os.getenv("LEMON_VARIANT_100"),
}

STREAMLIT_APP_URL = os.getenv(
    "STREAMLIT_APP_URL",
    "https://your-streamlit-app-url"
)

# ----------------------------------
# CREATE CHECKOUT
# ----------------------------------
@router.post("/create-link")
def create_lemon_checkout(pack: str, device: Device = Depends(get_device)):

    # ---------------------------
    # 🔒 ENV SAFETY CHECKS
    # ---------------------------
    if not LEMON_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="LEMON_API_KEY missing in backend environment variables"
        )

    if not LEMON_STORE_ID:
        raise HTTPException(
            status_code=500,
            detail="LEMON_STORE_ID missing in backend environment variables"
        )

    if pack not in VARIANTS or not VARIANTS[pack]:
        raise HTTPException(
            status_code=400,
            detail="Invalid credit pack"
        )

    # ---------------------------
    # LEMON CHECKOUT CREATION
    # ---------------------------
    url = "https://api.lemonsqueezy.com/v1/checkouts"

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {
                    "custom": {
                        "device_id": str(device.id),
                        "credits": pack
                    }
                },
                "checkout_options": {
                    "redirect_url": STREAMLIT_APP_URL,
                    "cancel_url": STREAMLIT_APP_URL
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
        "Content-Type": "application/vnd.api+json"
    }

    try:
        r = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=20
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LemonSqueezy connection error: {str(e)}"
        )

    if r.status_code not in (200, 201):
        raise HTTPException(
            status_code=400,
            detail=r.text
        )

    data = r.json()
    checkout_url = data["data"]["attributes"]["url"]

    # 👇 CRITICAL FIX: frontend expects this key
    return {"checkout_url": checkout_url}
