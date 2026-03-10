import json
import os
import re
from collections import defaultdict
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import Deal, DealNote, InstrumentType, PricingRule, ServiceType
from .schemas import AnalysisPayload, DealCreateRequest, DealDetailResponse, DealNoteCreateRequest, DealResponse

load_dotenv()

app = FastAPI(title="DANEM AI Sales Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_reference_data(db: Session) -> None:
    if db.query(InstrumentType).count() > 0:
        return

    instruments = [
        InstrumentType(name="Манометр", aliases="манометр,датчик давления", category="pressure"),
        InstrumentType(name="Термометр", aliases="термометр,температурный датчик", category="temperature"),
    ]
    services = [ServiceType(name="Поверка"), ServiceType(name="Калибровка")]
    db.add_all(instruments + services)
    db.flush()

    svc = {s.name: s for s in services}
    inst = {i.name: i for i in instruments}

    db.add_all(
        [
            PricingRule(
                instrument_type_id=inst["Манометр"].id,
                service_type_id=svc["Поверка"].id,
                price=1800,
                cost=1100,
                duration_days=5,
                rush_markup_percent=20,
                is_on_site_available=True,
            ),
            PricingRule(
                instrument_type_id=inst["Манометр"].id,
                service_type_id=svc["Калибровка"].id,
                price=2300,
                cost=1400,
                duration_days=7,
                rush_markup_percent=25,
                is_on_site_available=True,
            ),
            PricingRule(
                instrument_type_id=inst["Термометр"].id,
                service_type_id=svc["Поверка"].id,
                price=1500,
                cost=900,
                duration_days=4,
                rush_markup_percent=15,
                is_on_site_available=False,
            ),
        ]
    )
    db.commit()


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_reference_data(db)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def parse_quantity(text: str) -> int:
    matches = re.findall(r"(\d+)\s*(?:шт|ед|прибор)", text.lower())
    if matches:
        return max(int(x) for x in matches)
    any_num = re.findall(r"\b(\d{1,3})\b", text)
    return int(any_num[0]) if any_num else 1


def detect_service_type(text: str, db: Session) -> ServiceType | None:
    low = text.lower()
    service_keywords = {"поверк": "Поверка", "калибров": "Калибровка"}
    for key, name in service_keywords.items():
        if key in low:
            return db.query(ServiceType).filter(ServiceType.name == name).first()
    return db.query(ServiceType).first()


def detect_instrument(text: str, db: Session) -> InstrumentType | None:
    low = text.lower()
    for instrument in db.query(InstrumentType).all():
        tokens = [instrument.name.lower()] + [a.strip().lower() for a in instrument.aliases.split(",") if a.strip()]
        if any(token in low for token in tokens):
            return instrument
    return None


def compute_financials(text: str, db: Session) -> dict[str, Any]:
    instrument = detect_instrument(text, db)
    service = detect_service_type(text, db)
    quantity = parse_quantity(text)
    rush = "сроч" in text.lower()
    on_site = any(word in text.lower() for word in ["выезд", "на месте", "он-сайт"])

    if not instrument or not service:
        return {
            "revenue": 0.0,
            "cost": 0.0,
            "profit": 0.0,
            "timeline": "не определён",
            "recognized": [],
            "recommended_services": [],
        }

    rule = (
        db.query(PricingRule)
        .filter(
            PricingRule.instrument_type_id == instrument.id,
            PricingRule.service_type_id == service.id,
        )
        .first()
    )

    if not rule:
        return {
            "revenue": 0.0,
            "cost": 0.0,
            "profit": 0.0,
            "timeline": "нет правила ценообразования",
            "recognized": [instrument.name, service.name],
            "recommended_services": [service.name],
        }

    markup = (rule.rush_markup_percent / 100) if rush else 0
    price = rule.price * (1 + markup)
    revenue = price * quantity
    cost = rule.cost * quantity
    if on_site and rule.is_on_site_available:
        cost += 3000
        revenue += 5000

    return {
        "revenue": round(revenue, 2),
        "cost": round(cost, 2),
        "profit": round(revenue - cost, 2),
        "timeline": f"{rule.duration_days}{' (срочно)' if rush else ''} дней",
        "recognized": [instrument.name, service.name, f"кол-во: {quantity}"],
        "recommended_services": [service.name],
    }


def ai_analyze(raw_text: str, financials: dict[str, Any]) -> AnalysisPayload:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # fallback without AI
        return AnalysisPayload(
            summary=raw_text[:250],
            known_info=financials["recognized"],
            missing_info=["точный перечень приборов", "город/адрес", "наличие прошлых свидетельств"],
            questions_for_client=[
                "Уточните перечень приборов и модель каждого.",
                "Сколько единиц каждого прибора требуется обслужить?",
                "Какая услуга нужна: поверка или калибровка?",
                "В каком городе/по какому адресу выполнять работы?",
                "Какие желаемые сроки выполнения?",
                "Нужен ли выезд специалиста на объект?",
                "Есть ли прошлые свидетельства/протоколы по этим приборам?",
            ],
            recommended_services=financials["recommended_services"],
            upsell_suggestions=["Предложить регулярный график поверок для снижения просрочек."],
            action_plan=["Собрать недостающие метрологические данные", "Подтвердить спецификацию и отправить КП"],
            deal_probability="средняя",
            potential_revenue=str(financials["revenue"]),
            estimated_cost=str(financials["cost"]),
            estimated_profit=str(financials["profit"]),
            estimated_timeline=financials["timeline"],
            recommended_next_step="Запросить обязательные данные по приборам и услуге.",
            draft_message_to_client="Добрый день! Чтобы подготовить точное КП, пришлите перечень приборов, количество, тип услуги, адрес и желаемые сроки.",
        )

    client = OpenAI(api_key=api_key)
    prompt = f"""
Ты AI-ассистент по продажам метрологических услуг.
Отвечай строго JSON с полями:
summary, known_info, missing_info, questions_for_client, recommended_services, upsell_suggestions,
action_plan, deal_probability, potential_revenue, estimated_cost, estimated_profit, estimated_timeline,
recommended_next_step, draft_message_to_client.

ВАЖНО:
- Не выдумывай цены/себестоимость/сроки, используй только переданные значения.
- Вопросы клиенту фокусируй на метрологии и не спрашивай бюджет без необходимости.
- В первую очередь запроси: перечень приборов, количество, тип услуги, адрес/город, сроки, выезд, прошлые свидетельства.

Исходный текст:
{raw_text}

Расчеты из базы правил:
potential_revenue={financials['revenue']}
estimated_cost={financials['cost']}
estimated_profit={financials['profit']}
estimated_timeline={financials['timeline']}
""".strip()
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Отвечай только валидным JSON на русском."},
                {"role": "user", "content": prompt},
            ],
        )
        parsed = json.loads(res.choices[0].message.content or "{}")
        parsed["potential_revenue"] = str(financials["revenue"])
        parsed["estimated_cost"] = str(financials["cost"])
        parsed["estimated_profit"] = str(financials["profit"])
        parsed["estimated_timeline"] = financials["timeline"]
        return AnalysisPayload(**parsed)
    except Exception:
        return AnalysisPayload(
            summary=raw_text[:250],
            known_info=financials["recognized"],
            questions_for_client=["Уточните перечень приборов, количество и вид метрологической услуги."],
            potential_revenue=str(financials["revenue"]),
            estimated_cost=str(financials["cost"]),
            estimated_profit=str(financials["profit"]),
            estimated_timeline=financials["timeline"],
        )


def collect_full_text(deal: Deal) -> str:
    lines = [deal.raw_input]
    for note in sorted(deal.notes, key=lambda n: n.created_at):
        lines.append(f"[{note.source}] {note.content}")
    return "\n".join(lines)


def save_analysis_to_deal(deal: Deal, analysis: AnalysisPayload) -> None:
    deal.current_summary = analysis.summary
    deal.deal_probability = analysis.deal_probability
    deal.potential_revenue = float(analysis.potential_revenue or 0)
    deal.estimated_cost = float(analysis.estimated_cost or 0)
    deal.estimated_profit = float(analysis.estimated_profit or 0)
    deal.estimated_timeline = analysis.estimated_timeline


def build_deal_detail(deal: Deal, analysis: AnalysisPayload) -> DealDetailResponse:
    return DealDetailResponse(
        **DealResponse.model_validate(deal).model_dump(),
        analysis=analysis,
        notes=[
            {"id": n.id, "source": n.source, "content": n.content, "created_at": n.created_at.isoformat()}
            for n in sorted(deal.notes, key=lambda x: x.created_at)
        ],
    )


analysis_cache: dict[int, AnalysisPayload] = defaultdict(AnalysisPayload)


@app.post("/deals", response_model=DealDetailResponse)
def create_deal(payload: DealCreateRequest, db: Session = Depends(get_db)) -> DealDetailResponse:
    if not payload.raw_input.strip():
        raise HTTPException(status_code=400, detail="raw_input не должен быть пустым")

    deal = Deal(
        title=payload.title,
        client_name=payload.client_name,
        contact_name=payload.contact_name,
        raw_input=payload.raw_input,
        status="new",
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)

    financials = compute_financials(deal.raw_input, db)
    analysis = ai_analyze(deal.raw_input, financials)
    save_analysis_to_deal(deal, analysis)
    db.commit()
    db.refresh(deal)

    analysis_cache[deal.id] = analysis
    return build_deal_detail(deal, analysis)


@app.get("/deals", response_model=list[DealResponse])
def list_deals(db: Session = Depends(get_db)) -> list[DealResponse]:
    deals = db.query(Deal).order_by(Deal.created_at.desc()).all()
    return [DealResponse.model_validate(d) for d in deals]


@app.get("/deals/{deal_id}", response_model=DealDetailResponse)
def get_deal(deal_id: int, db: Session = Depends(get_db)) -> DealDetailResponse:
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    analysis = analysis_cache.get(deal.id)
    if not analysis:
        financials = compute_financials(collect_full_text(deal), db)
        analysis = ai_analyze(collect_full_text(deal), financials)
        analysis_cache[deal.id] = analysis
    return build_deal_detail(deal, analysis)


@app.post("/deals/{deal_id}/notes", response_model=DealDetailResponse)
def add_note(deal_id: int, payload: DealNoteCreateRequest, db: Session = Depends(get_db)) -> DealDetailResponse:
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    note = DealNote(deal_id=deal.id, source=payload.source, content=payload.content)
    db.add(note)
    db.commit()
    db.refresh(deal)

    return reanalyze_deal(deal_id, db)


@app.post("/deals/{deal_id}/reanalyze", response_model=DealDetailResponse)
def reanalyze_deal(deal_id: int, db: Session = Depends(get_db)) -> DealDetailResponse:
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    full_text = collect_full_text(deal)
    financials = compute_financials(full_text, db)
    analysis = ai_analyze(full_text, financials)
    save_analysis_to_deal(deal, analysis)
    db.commit()
    db.refresh(deal)

    analysis_cache[deal.id] = analysis
    return build_deal_detail(deal, analysis)
