# -*- coding: utf-8 -*-
"""
FastAPI REST 서버
실행: python src/serve_api.py
접속: http://localhost:8000/docs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from model_loader import generate, get_model

app = FastAPI(
    title="React Coding Assistant API",
    description="로컬 파인튜닝 모델 기반 React 코딩 어시스턴트",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    instruction: str
    input: str = ""
    max_new_tokens: int = 512


class GenerateResponse(BaseModel):
    response: str
    instruction: str


@app.on_event("startup")
async def startup():
    # 서버 시작 시 모델 미리 로드
    get_model()


@app.get("/health")
def health():
    return {"status": "ok", "model": "qwen2.5-coder-1.5b + react-lora-v4"}


@app.post("/generate", response_model=GenerateResponse)
def generate_code(req: GenerateRequest):
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction이 비어있습니다.")

    result = generate(
        instruction=req.instruction,
        input_text=req.input,
        max_new_tokens=req.max_new_tokens,
    )

    return GenerateResponse(response=result, instruction=req.instruction)


@app.post("/chat")
def chat(req: GenerateRequest):
    """간단한 채팅 엔드포인트 (generate와 동일)"""
    return generate_code(req)


if __name__ == "__main__":
    import uvicorn
    print("React Coding Assistant API 시작")
    print("문서: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
