import { useRouter } from 'next/router'
import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'

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
  estimated_cost: 'Оценочная себестоимость',
  estimated_profit: 'Оценочная прибыль',
  estimated_timeline: 'Оценочный срок',
  recommended_next_step: 'Следующий шаг',
  draft_message_to_client: 'Черновик сообщения клиенту',
}

const fieldOrder = Object.keys(fieldLabels)

export default function DealPage() {
  const router = useRouter()
  const { id } = router.query
  const [deal, setDeal] = useState(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')

  const loadDeal = async () => {
    if (!id) return
    const res = await fetch(`${API_BASE}/deals/${id}`)
    const data = await res.json()
    if (res.ok) setDeal(data)
  }

  useEffect(() => {
    loadDeal()
  }, [id])

  const addNote = async () => {
    setError('')
    if (!note.trim()) return
    const res = await fetch(`${API_BASE}/deals/${id}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: 'manager', content: note }),
    })
    const data = await res.json()
    if (!res.ok) {
      setError(data.detail || 'Ошибка добавления')
      return
    }
    setDeal(data)
    setNote('')
  }

  const reanalyze = async () => {
    const res = await fetch(`${API_BASE}/deals/${id}/reanalyze`, { method: 'POST' })
    const data = await res.json()
    if (res.ok) setDeal(data)
  }

  if (!deal) return <main className="container">Загрузка...</main>

  return (
    <main className="container">
      <h1>{deal.title}</h1>
      <p className="subtitle">{deal.client_name}</p>
      <button className="analyze-button" onClick={reanalyze}>
        Повторный AI-анализ
      </button>

      <section className="result-card">
        <h3>Добавить новую информацию</h3>
        <textarea className="deal-input" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="analyze-button" onClick={addNote}>
          Добавить заметку
        </button>
        {error ? <div className="error-box">{error}</div> : null}
      </section>

      <section className="cards-grid">
        {fieldOrder.map((fieldKey) => {
          const value = deal.analysis[fieldKey] ?? deal[fieldKey]
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

      <section className="result-card">
        <h3>История заметок</h3>
        <ul>
          {deal.notes.map((n) => (
            <li key={n.id}>
              [{n.source}] {n.content}
            </li>
          ))}
        </ul>
      </section>
    </main>
  )
}
