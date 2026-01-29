import os
import tempfile
import traceback
from datetime import datetime

import fal_client
import requests
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from PIL import Image

from database import get_db
from models import Device, UsageLog
from auth_device import get_device

router = APIRouter()

# Make sure FAL key is loaded
os.environ["FAL_KEY"] = os.getenv("FAL_KEY")


def save_upload(file: UploadFile):
    img = Image.open(file.file).convert("RGB")
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    img.save(temp.name, format="PNG")
    temp.close()
    return temp.name


def download_image(url: str):
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    img = Image.open(r.raw).convert("RGB")
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    img.save(temp.name, format="PNG")
    temp.close()
    return temp.name


@router.post("/tryon")
def try_on(
    garment_url: str,
    person_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    device: Device = Depends(get_device)
):
    if device.credits < 1:
        raise HTTPException(status_code=402, detail="No credits left")

    person_path = None
    cloth_path = None

    try:
        # Lock credit
        device.credits -= 1
        device.last_try_at = datetime.utcnow()
        db.commit()

        # Save images
        person_path = save_upload(person_image)
        cloth_path = download_image(garment_url)

        # Upload to FAL CDN
        person_url = fal_client.upload_file(person_path)
        garment_url = fal_client.upload_file(cloth_path)

        # Run model
        result = fal_client.subscribe(
            "fal-ai/kling/v1-5/kolors-virtual-try-on",
            arguments={
                "human_image_url": person_url,
                "garment_image_url": garment_url
            },
            with_logs=True
        )

        # Extract output
        if "image_url" in result:
            output_url = result["image_url"]
        elif "data" in result and "image_url" in result["data"]:
            output_url = result["data"]["image_url"]
        elif "image" in result and "url" in result["image"]:
            output_url = result["image"]["url"]
        else:
            raise ValueError("No output image found in FAL response")

        # Log usage
        log = UsageLog(
            device_id=device.id,
            outfit_url=garment_url,
            result_url=output_url,
            status="success",
            created_at=datetime.utcnow()
        )
        db.add(log)

        # Commit credit
        device.total_tries += 1
        db.commit()

        return {
            "message": "Try-on complete",
            "image_url": output_url,
            "credits_left": device.credits
        }

    except Exception as e:
        # Refund credit
        device.credits += 1
        db.commit()

        log = UsageLog(
            device_id=device.id,
            outfit_url=garment_url,
            status="failed",
            created_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()

        raise HTTPException(status_code=500, detail=str(e))

    finally:
        try:
            if person_path and os.path.exists(person_path):
                os.remove(person_path)
            if cloth_path and os.path.exists(cloth_path):
                os.remove(cloth_path)
        except:
            pass
