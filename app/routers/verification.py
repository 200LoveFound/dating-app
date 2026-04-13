import cv2
import base64
import random
import numpy as np
from fastapi import APIRouter, HTTPException, Request
from app.models.models import *
from . import router, templates
from sqlmodel import select
from fastapi.responses import HTMLResponse, JSONResponse
from app.dependencies import AuthDep, SessionDep

page_router = APIRouter(tags=["Verification"])   
api_router = APIRouter(tags=["Verification API"])

# Load cascades
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')

CHALLENGES = [
    {"action": "face_visible", "instruction": "Look straight at the camera and make sure your face is clearly visible"},
    {"action": "turn_side",    "instruction": "Turn your head to the side"},
    {"action": "cover_eye",    "instruction": "Cover one of your eyes with your hand"},
]


#Detection helpers

def decode_image(base64_string: str):
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    img_bytes = base64.b64decode(base64_string)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    return cv2.imdecode(img_array, cv2.IMREAD_COLOR)

def detect_face_visible(image) -> dict:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    passed = len(faces) == 1
    return {"passed": passed, "value": len(faces), "threshold": 1}

def detect_turn_side(image) -> dict:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    frontal = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=8, minSize=(80, 80))
    profile = profile_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    flipped = cv2.flip(gray, 1)
    profile_flipped = profile_cascade.detectMultiScale(flipped, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    passed = len(frontal) == 0 or len(profile) > 0 or len(profile_flipped) > 0
    return {"passed": passed, "value": len(profile_flipped), "threshold": 1}

def detect_cover_eye(image) -> dict:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))

    if len(faces) == 0:
        return {"passed": False, "value": 0, "threshold": 0}
    
    x, y, w, h = faces[0]
    face_region = gray[y:y + int(h * 0.6), x:x + w]
    eyes = eye_cascade.detectMultiScale(face_region, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))
    passed = len(eyes) == 1

    return {"passed": passed, "value": len(eyes), "threshold": 1}

DETECTORS = {
    "face_visible": detect_face_visible,
    "turn_side":    detect_turn_side,
    "cover_eye":    detect_cover_eye,
}

#Routes
@page_router.get("/verify", response_class=HTMLResponse)
def verification_page(request: Request, user: AuthDep, db: SessionDep):

    mine = db.exec(select(Profile).where(Profile.user_id == user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return templates.TemplateResponse(
        request=request,
        name="verification.html",
        context={"user": user, "mine": mine}
    )

@api_router.get("/get-challenge")
async def get_challenge(user_id: str):

    challenge = random.choice(CHALLENGES)
    challenge_store[user_id] = challenge["action"]

    return {"action": challenge["action"], "instruction": challenge["instruction"]}

@api_router.post("/verify-challenge")
async def verify_challenge(request: ChallengeVerifyRequest, db: SessionDep):

    expected_action = challenge_store.get(request.user_id)
    if not expected_action:
        raise HTTPException(status_code=400, detail="No challenge found. Please request a challenge first.")

    try:
        image = decode_image(request.image)
        if image is None:
            return {"verified": False, "reason": "decode_failed", "message": "Could not decode image. Please try again."}

        detector = DETECTORS.get(expected_action)
        if not detector:
            raise HTTPException(status_code=400, detail=f"Unknown action: {expected_action}")

        result = detector(image)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"verified": False, "reason": "processing_error", "message": "An error occurred while analysing the image. Please try again."}

    # If passed, update the DB
    if result["passed"]:

        del challenge_store[request.user_id]

        profile = db.exec(select(Profile).where(Profile.user_id == int(request.user_id))).one_or_none()
        if profile:
            profile.is_verified = True
            db.add(profile)
            db.commit()

    return {
        "verified": result["passed"],
        "action": expected_action,
        "value": result["value"],
        "threshold": result["threshold"],
        "reason": "success" if result["passed"] else "action_not_detected",
        "message": "Verified! Your account is now active." if result["passed"] else f"Could not detect '{expected_action}'. Please try again more clearly in good lighting."
    }