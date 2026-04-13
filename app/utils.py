import os
import uuid
from fastapi import UploadFile

UPLOAD_DIR = "app/static/uploads"

async def save_upload(file: UploadFile) -> str | None:
    if not file or not file.filename:
        return None

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        return None

    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    with open(path, "wb") as f:
        f.write(contents)

    return f"/static/uploads/{filename}"