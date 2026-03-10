import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()

app = FastAPI(title="DANEM AI Sales Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeDealRequest(BaseModel):
    deal_text: str


class AnalyzeDealResponse(BaseModel):
    summary: str
    known_info: List[str]
    missing_info: List[str]
    questions_for_client: List[str]
    recommended_services: List[str]
    upsell_suggestions: List[str]
    action_plan: List[str]
    deal_probability: str
    potential_revenue: str
    estimated_timeline: str
    recommended_next_step: str
    draft_message_to_client: str


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/ai/analyze-deal", response_model=AnalyzeDealResponse)
def analyze_deal(payload: AnalyzeDealRequest) -> Any:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY не задан в переменных окружения.")

    if not payload.deal_text.strip():
        raise HTTPException(status_code=400, detail="Поле deal_text не должно быть пустым.")

    client = OpenAI(api_key=api_key)

    system_prompt = (
        "Ты AI-ассистент менеджера по продажам метрологических услуг. "
        "Отвечай ТОЛЬКО на русском языке. "
        "Верни строго JSON-объект с английскими именами полей и без markdown."
    )

    user_prompt = f"""
Проанализируй входные данные по сделке и верни только JSON со следующими полями:
- summary (string)
- known_info (array of strings)
- missing_info (array of strings)
- questions_for_client (array of strings)
- recommended_services (array of strings)
- upsell_suggestions (array of strings)
- action_plan (array of strings)
- deal_probability (string)
- potential_revenue (string)
- estimated_timeline (string)
- recommended_next_step (string)
- draft_message_to_client (string)

Текст сделки:
{payload.deal_text}
""".strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return AnalyzeDealResponse(**parsed)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка анализа сделки: {str(exc)}") from exc
