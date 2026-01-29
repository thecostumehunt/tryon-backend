from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import get_db
from auth_device import get_device
from credits import router as credits_router
from tryon import router as tryon_router
from lemon_payments import router as lemon_router
from lemon_webhook import router as lemon_webhook_router


# ----------------------------------
# APP SETUP
# ----------------------------------
app = FastAPI(title="Try-On Backend")


# ----------------------------------
# CORS (important for Streamlit / web)
# ----------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # you can restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------
# ROUTERS
# ----------------------------------
app.include_router(credits_router)
app.include_router(tryon_router)
app.include_router(lemon_router)
app.include_router(lemon_webhook_router)



# ----------------------------------
# ROOT
# ----------------------------------
@app.get("/")
def root():
    return {"status": "Backend running"}


# ----------------------------------
# DEVICE INIT
# ----------------------------------
@app.get("/device/init")
def init_device(request: Request, device = Depends(get_device)):
    response = {
        "device_id": str(device.id),
        "credits": device.credits,
        "free_used": device.free_used
    }

    if hasattr(request.state, "new_device_token"):
        response["device_token"] = request.state.new_device_token

    return response
