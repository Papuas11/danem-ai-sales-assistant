# DANEM AI Sales Assistant (MVP v2)

Минимально рабочая CRM+AI версия для метрологических продаж:
- хранение сделок в PostgreSQL (или SQLite fallback для локального запуска);
- добавление новой информации по сделке;
- повторный AI-анализ по всей истории;
- расчет выручки/себестоимости/прибыли/срока только по `PricingRule`.

## Структура
- `backend/` — FastAPI + SQLAlchemy
- `frontend/` — Next.js (страницы списка и карточки сделки)

## Модели данных
- `Deal`
- `DealNote`
- `InstrumentType`
- `ServiceType`
- `PricingRule`

## Важная логика
- AI не придумывает цену: в prompt передаются готовые цифры из базы.
- Расчеты выполняются по `PricingRule`.
- Если распознан `манометр`, выбирается соответствующее правило.

## Требования
- Python 3.10+
- Node.js 18+
- `OPENAI_API_KEY` (опционально: без него работает fallback-анализ)
- `DATABASE_URL` (рекомендуется PostgreSQL)

Пример PostgreSQL:
```bash
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/danem"
```

## Запуск backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your_api_key"
uvicorn app.main:app --reload --port 8000
```

## Запуск frontend
```bash
cd frontend
npm install
npm run dev
```

## API
- `POST /deals` — создать сделку и первый анализ
- `GET /deals` — список сделок
- `GET /deals/{id}` — детали сделки
- `POST /deals/{id}/notes` — добавить заметку и пересчитать анализ
- `POST /deals/{id}/reanalyze` — повторный анализ
