from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.app.services.smart_tutoring import (
    get_smart_tutoring_engine,
    recent_tutoring_records,
)


router = APIRouter(prefix="/smart-tutor", tags=["smart-tutor"])


@router.post("/image-analyze")
async def analyze_learning_image(file: UploadFile = File(...)) -> dict:
    """OCR 并结构化解析学生上传的题目或教材图片。"""
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="仅支持图片文件")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="图片内容为空")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="图片不能超过 12MB")
    from backend.app.services.multimodal.ocr.engine import get_ocr_engine

    page = get_ocr_engine().recognize(raw, filename=file.filename or "upload.png")
    result = page.to_dict()
    result["filename"] = file.filename or "upload.png"
    result["success"] = not bool(result.get("error"))
    return result


class SmartTutorAskRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    input_type: Literal["text", "voice", "image", "code"] = "text"
    session_id: str | None = None
    preferred_modes: list[str] | None = None


@router.post("/ask")
def ask_smart_tutor(payload: SmartTutorAskRequest) -> dict:
    engine = get_smart_tutoring_engine()
    return engine.ask(
        user_id=payload.user_id,
        question=payload.question,
        input_type=payload.input_type,
        preferred_modes=payload.preferred_modes,
        session_id=payload.session_id,
    )


@router.get("/records/{user_id}")
def get_smart_tutor_records(user_id: str, limit: int = 20) -> dict:
    records = recent_tutoring_records(user_id, limit=limit)
    return {"user_id": user_id, "count": len(records), "records": records}
