import { useState } from 'react'

const fieldLabels = {
  summary: 'Краткое резюме',
  known_info: 'Известная информация',
  missing_info: 'Недостающая информация',
  questions_for_client: 'Вопросы клиенту',
  recommended_services: 'Рекомендуемые услуги',
  upsell_suggestions: 'Upsell-предложения',
  action_plan: 'План действий',
  deal_probability: 'Вероятность сделки',
  potential_revenue: 'Потенциальная выручка',
  estimated_timeline: 'Оценочный срок',
  recommended_next_step: 'Следующий шаг',
  draft_message_to_client: 'Черновик сообщения клиенту',
}

const fieldOrder = Object.keys(fieldLabels)

export default function HomePage() {
  const [dealText, setDealText] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const onAnalyze = async () => {
    setError('')
    setResult(null)

    if (!dealText.trim()) {
      setError('Пожалуйста, заполните описание сделки.')
      return
    }

    try {
      setLoading(true)
      const response = await fetch('http://localhost:8000/ai/analyze-deal', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ deal_text: dealText }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Ошибка запроса к backend.')
      }

      setResult(data)
    } catch (e) {
      setError(e.message || 'Неизвестная ошибка.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="container">
      <h1>DANEM AI Sales Assistant</h1>
      <p className="subtitle">AI-инструмент для анализа сделок по метрологическим услугам</p>

      <textarea
        value={dealText}
        onChange={(e) => setDealText(e.target.value)}
        placeholder="Вставьте описание сделки, переписку или бриф клиента..."
        className="deal-input"
      />

      <button onClick={onAnalyze} disabled={loading} className="analyze-button">
        {loading ? 'Анализ...' : 'Анализировать'}
      </button>

      {error ? <div className="error-box">{error}</div> : null}

      {result ? (
        <section className="cards-grid">
          {fieldOrder.map((fieldKey) => {
            const value = result[fieldKey]
            return (
              <article className="result-card" key={fieldKey}>
                <h3>{fieldLabels[fieldKey]}</h3>
                {Array.isArray(value) ? (
                  value.length ? (
                    <ul>
                      {value.map((item, idx) => (
                        <li key={`${fieldKey}-${idx}`}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>—</p>
                  )
                ) : (
                  <p>{value || '—'}</p>
                )}
              </article>
            )
          })}
        </section>
      ) : null}
    </main>
  )
}
