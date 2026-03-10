# DANEM AI Sales Assistant (MVP)

Минимально рабочая версия AI-инструмента для менеджера по продажам метрологических услуг.

## Структура

- `backend/` — FastAPI API
- `frontend/` — Next.js UI

## Что умеет MVP

- Одна страница с большим текстовым полем
- Кнопка `Анализировать`
- Запрос на backend endpoint: `POST /ai/analyze-deal`
- Анализ сделки через OpenAI API
- Отображение результата в карточках
- Базовая обработка ошибок

## Требования

- Python 3.10+
- Node.js 18+
- `OPENAI_API_KEY` в переменных окружения

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

Приложение frontend будет доступно на `http://localhost:3000`.

## Endpoint

### `POST /ai/analyze-deal`

Пример body:

```json
{
  "deal_text": "Клиенту нужна поверка 120 манометров в течение 2 недель..."
}
```

Ответ возвращается строго в JSON с полями:

- `summary`
- `known_info`
- `missing_info`
- `questions_for_client`
- `recommended_services`
- `upsell_suggestions`
- `action_plan`
- `deal_probability`
- `potential_revenue`
- `estimated_timeline`
- `recommended_next_step`
- `draft_message_to_client`
