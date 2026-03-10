import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import Deal, DealNote, InstrumentType, PricingRule, ServiceType
from .schemas import (
    AnalysisPayload,
    DealCreateRequest,
    DealDetailResponse,
    DealNoteCreateRequest,
    DealResponse,
    InstrumentRuleCreateRequest,
    InstrumentRuleResponse,
    InstrumentRuleUpdateRequest,
    ServiceTypeResponse,
)

load_dotenv()

app = FastAPI(title="DANEM AI Sales Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "pricing_rules.csv"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_reference_data(db: Session) -> None:
    if db.query(PricingRule).count() > 0 or not CSV_PATH.exists():
        return

    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            service_name = row["service_type"].strip()
            service = db.query(ServiceType).filter(ServiceType.name == service_name).first()
            if not service:
                service = ServiceType(name=service_name)
                db.add(service)
                db.flush()

            instrument_name = row["instrument_name"].strip()
            instrument = db.query(InstrumentType).filter(InstrumentType.name == instrument_name).first()
            if not instrument:
                instrument = InstrumentType(
                    name=instrument_name,
                    aliases=row.get("aliases", ""),
                    category="general",
                )
                db.add(instrument)
                db.flush()
            else:
                instrument.aliases = row.get("aliases", instrument.aliases)

            rule = PricingRule(
                instrument_type_id=instrument.id,
                service_type_id=service.id,
                price=float(row["price"]),
                cost=float(row["cost"]),
                duration_days=int(row.get("duration_days") or 0),
                duration_hours=int(row.get("duration_hours") or 0),
                rush_markup_percent=float(row.get("rush_markup_percent") or 0),
                on_site_markup_percent=float(row.get("on_site_markup_percent") or 0),
                is_on_site_available=str(row.get("is_on_site_available", "false")).lower() == "true",
            )
            db.add(rule)

    db.commit()


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_reference_data(db)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def normalized_aliases(instrument: InstrumentType) -> list[str]:
    aliases = [a.strip().lower() for a in re.split(r"[;,]", instrument.aliases or "") if a.strip()]
    return [instrument.name.lower(), *aliases]


def detect_service_type(text: str, db: Session) -> ServiceType | None:
    low = text.lower()
    for service in db.query(ServiceType).all():
        if service.name.lower() in low:
            return service
    service_keywords = {"поверк": "Поверка", "калибров": "Калибровка"}
    for key, name in service_keywords.items():
        if key in low:
            return db.query(ServiceType).filter(ServiceType.name == name).first()
    return None


def extract_state(texts: list[str], db: Session) -> dict[str, Any]:
    instruments = db.query(InstrumentType).all()
    quantity_by_instrument: dict[int, int] = {}
    last_instrument_id: int | None = None
    service: ServiceType | None = None
    rush = False
    on_site = False

    for text in texts:
        low = text.lower()
        detected_this_line: list[int] = []

        for instrument in instruments:
            for alias in normalized_aliases(instrument):
                if alias and alias in low:
                    detected_this_line.append(instrument.id)
                    last_instrument_id = instrument.id
                    qty_match = re.search(rf"(\d+)\s+{re.escape(alias)}", low)
                    if qty_match:
                        quantity_by_instrument[instrument.id] = int(qty_match.group(1))

        generic_qty = re.search(r"(?:все же|итого|всего|нужно|будет)?\s*(\d+)\s*(?:шт|ед|прибор|манометр|расходомер|термометр)", low)
        if generic_qty:
            qty = int(generic_qty.group(1))
            target_ids = detected_this_line or ([last_instrument_id] if last_instrument_id else [])
            for inst_id in target_ids:
                quantity_by_instrument[inst_id] = qty

        maybe_service = detect_service_type(text, db)
        if maybe_service:
            service = maybe_service

        if "сроч" in low:
            rush = True
        if any(word in low for word in ["выезд", "на месте", "на объекте", "on-site"]):
            on_site = True

    return {
        "quantity_by_instrument": quantity_by_instrument,
        "service": service,
        "rush": rush,
        "on_site": on_site,
    }


def compute_financials_from_state(state: dict[str, Any], db: Session) -> dict[str, Any]:
    service: ServiceType | None = state["service"]
    quantity_by_instrument: dict[int, int] = state["quantity_by_instrument"]
    rush: bool = state["rush"]
    on_site: bool = state["on_site"]

    if not quantity_by_instrument:
        return {
            "revenue": 0.0,
            "cost": 0.0,
            "profit": 0.0,
            "timeline": "не определён",
            "recognized": [],
            "missing_info": ["перечень приборов и количество", "тип услуги"],
            "recommended_services": [],
        }

    if not service:
        return {
            "revenue": 0.0,
            "cost": 0.0,
            "profit": 0.0,
            "timeline": "не определён",
            "recognized": [f"распознано приборов: {len(quantity_by_instrument)}"],
            "missing_info": ["тип услуги"],
            "recommended_services": [],
        }

    total_revenue = 0.0
    total_cost = 0.0
    total_days = 0
    total_hours = 0
    recognized: list[str] = [f"услуга: {service.name}"]
    missing_info: list[str] = []

    for instrument_id, qty in quantity_by_instrument.items():
        instrument = db.query(InstrumentType).filter(InstrumentType.id == instrument_id).first()
        if not instrument:
            continue

        recognized.append(f"{instrument.name}: {qty} шт")
        rule = (
            db.query(PricingRule)
            .filter(
                PricingRule.instrument_type_id == instrument.id,
                PricingRule.service_type_id == service.id,
            )
            .first()
        )

        if not rule:
            missing_info.append(f"нет PricingRule для {instrument.name} / {service.name}")
            continue

        unit_price = rule.price
        if rush:
            unit_price *= 1 + (rule.rush_markup_percent / 100)
        if on_site and rule.is_on_site_available:
            unit_price *= 1 + (rule.on_site_markup_percent / 100)

        total_revenue += unit_price * qty
        total_cost += rule.cost * qty
        total_days += rule.duration_days * qty
        total_hours += rule.duration_hours * qty

    total_days += total_hours // 24
    total_hours = total_hours % 24

    return {
        "revenue": round(total_revenue, 2),
        "cost": round(total_cost, 2),
        "profit": round(total_revenue - total_cost, 2),
        "timeline": f"{total_days} дн {total_hours} ч",
        "recognized": recognized,
        "missing_info": missing_info,
        "recommended_services": [service.name],
    }


def ai_analyze(raw_text: str, financials: dict[str, Any]) -> AnalysisPayload:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return AnalysisPayload(
            summary=raw_text[:250],
            known_info=financials["recognized"],
            missing_info=financials["missing_info"]
            or ["город/адрес", "сроки", "нужен ли выезд", "есть ли прошлые свидетельства"],
            questions_for_client=[
                "Уточните полный перечень приборов и модели.",
                "Подтвердите количество по каждому прибору.",
                "Уточните тип услуги: поверка или калибровка.",
                "Укажите адрес/город выполнения работ.",
                "Какие желаемые сроки выполнения?",
                "Нужен ли выезд специалиста?",
                "Есть ли прошлые свидетельства/протоколы?",
            ],
            recommended_services=financials["recommended_services"],
            upsell_suggestions=["Предложить регулярный график поверок."],
            action_plan=["Собрать недостающие метрологические данные", "Отправить КП по актуальным данным"],
            deal_probability="средняя",
            potential_revenue=str(financials["revenue"]),
            estimated_cost=str(financials["cost"]),
            estimated_profit=str(financials["profit"]),
            estimated_timeline=financials["timeline"],
            recommended_next_step="Получить недостающие данные и подтвердить объем работ.",
            draft_message_to_client="Уточните перечень приборов, количество, тип услуги, адрес и сроки, чтобы мы подготовили корректное КП.",
        )

    client = OpenAI(api_key=api_key)
    prompt = f"""
Ты AI-ассистент по продажам метрологических услуг.
Отвечай строго JSON с полями:
summary, known_info, missing_info, questions_for_client, recommended_services, upsell_suggestions,
action_plan, deal_probability, potential_revenue, estimated_cost, estimated_profit, estimated_timeline,
recommended_next_step, draft_message_to_client.

Используй только актуальные факты и расчеты из PricingRule.

Исходный текст:
{raw_text}

Расчеты:
potential_revenue={financials['revenue']}
estimated_cost={financials['cost']}
estimated_profit={financials['profit']}
estimated_timeline={financials['timeline']}
known_info={financials['recognized']}
missing_info={financials['missing_info']}
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
        parsed["known_info"] = financials["recognized"]
        parsed["missing_info"] = financials["missing_info"]
        return AnalysisPayload(**parsed)
    except Exception:
        return AnalysisPayload(
            summary=raw_text[:250],
            known_info=financials["recognized"],
            missing_info=financials["missing_info"],
            questions_for_client=["Уточните перечень приборов, количество и вид метрологической услуги."],
            potential_revenue=str(financials["revenue"]),
            estimated_cost=str(financials["cost"]),
            estimated_profit=str(financials["profit"]),
            estimated_timeline=financials["timeline"],
        )


def collect_timeline_texts(deal: Deal) -> list[str]:
    notes = sorted(deal.notes, key=lambda n: n.created_at)
    return [deal.raw_input, *[note.content for note in notes]]


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


def to_instrument_rule_response(rule: PricingRule) -> InstrumentRuleResponse:
    return InstrumentRuleResponse(
        id=rule.id,
        instrument_type_id=rule.instrument_type_id,
        service_type_id=rule.service_type_id,
        instrument_name=rule.instrument_type.name,
        aliases=rule.instrument_type.aliases,
        category=rule.instrument_type.category,
        service_type=rule.service_type.name,
        price=rule.price,
        cost=rule.cost,
        duration_days=rule.duration_days,
        duration_hours=rule.duration_hours,
        rush_markup_percent=rule.rush_markup_percent,
        on_site_markup_percent=rule.on_site_markup_percent,
        is_on_site_available=rule.is_on_site_available,
    )


def get_or_create_instrument_and_service(db: Session, payload: InstrumentRuleCreateRequest | InstrumentRuleUpdateRequest):
    instrument = db.query(InstrumentType).filter(InstrumentType.name == payload.instrument_name).first()
    if not instrument:
        instrument = InstrumentType(name=payload.instrument_name, aliases=payload.aliases, category=payload.category)
        db.add(instrument)
        db.flush()
    else:
        instrument.aliases = payload.aliases
        instrument.category = payload.category

    service = db.query(ServiceType).filter(ServiceType.name == payload.service_type).first()
    if not service:
        service = ServiceType(name=payload.service_type)
        db.add(service)
        db.flush()

    return instrument, service


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

    state = extract_state(collect_timeline_texts(deal), db)
    financials = compute_financials_from_state(state, db)
    analysis = ai_analyze(payload.raw_input, financials)
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
        full_text = "\n".join(collect_timeline_texts(deal))
        state = extract_state(collect_timeline_texts(deal), db)
        financials = compute_financials_from_state(state, db)
        analysis = ai_analyze(full_text, financials)
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

    texts = collect_timeline_texts(deal)
    state = extract_state(texts, db)
    financials = compute_financials_from_state(state, db)
    analysis = ai_analyze("\n".join(texts), financials)
    save_analysis_to_deal(deal, analysis)
    db.commit()
    db.refresh(deal)

    analysis_cache[deal.id] = analysis
    return build_deal_detail(deal, analysis)


@app.get("/instruments", response_model=list[InstrumentRuleResponse])
def list_instruments(db: Session = Depends(get_db)) -> list[InstrumentRuleResponse]:
    rules = db.query(PricingRule).all()
    return [to_instrument_rule_response(rule) for rule in rules]


@app.post("/instruments", response_model=InstrumentRuleResponse)
def create_instrument(payload: InstrumentRuleCreateRequest, db: Session = Depends(get_db)) -> InstrumentRuleResponse:
    instrument, service = get_or_create_instrument_and_service(db, payload)
    rule = PricingRule(
        instrument_type_id=instrument.id,
        service_type_id=service.id,
        price=payload.price,
        cost=payload.cost,
        duration_days=payload.duration_days,
        duration_hours=payload.duration_hours,
        rush_markup_percent=payload.rush_markup_percent,
        on_site_markup_percent=payload.on_site_markup_percent,
        is_on_site_available=payload.is_on_site_available,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return to_instrument_rule_response(rule)


@app.put("/instruments/{rule_id}", response_model=InstrumentRuleResponse)
def update_instrument(rule_id: int, payload: InstrumentRuleUpdateRequest, db: Session = Depends(get_db)) -> InstrumentRuleResponse:
    rule = db.query(PricingRule).filter(PricingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")

    instrument, service = get_or_create_instrument_and_service(db, payload)
    rule.instrument_type_id = instrument.id
    rule.service_type_id = service.id
    rule.price = payload.price
    rule.cost = payload.cost
    rule.duration_days = payload.duration_days
    rule.duration_hours = payload.duration_hours
    rule.rush_markup_percent = payload.rush_markup_percent
    rule.on_site_markup_percent = payload.on_site_markup_percent
    rule.is_on_site_available = payload.is_on_site_available

    db.commit()
    db.refresh(rule)
    return to_instrument_rule_response(rule)


@app.get("/service-types", response_model=list[ServiceTypeResponse])
def list_service_types(db: Session = Depends(get_db)) -> list[ServiceTypeResponse]:
    services = db.query(ServiceType).order_by(ServiceType.name.asc()).all()
    return [ServiceTypeResponse.model_validate(s) for s in services]
