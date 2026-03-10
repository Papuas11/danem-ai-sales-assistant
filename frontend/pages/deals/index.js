import Link from 'next/link'
import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'

export default function DealsPage() {
  const [deals, setDeals] = useState([])
  const [form, setForm] = useState({ title: '', client_name: '', contact_name: '', raw_input: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const loadDeals = async () => {
    const res = await fetch(`${API_BASE}/deals`)
    const data = await res.json()
    if (res.ok) setDeals(data)
  }

  useEffect(() => {
    loadDeals()
  }, [])

  const createDeal = async () => {
    setError('')
    if (!form.title || !form.client_name || !form.raw_input) {
      setError('Заполните название, клиента и описание сделки.')
      return
    }
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/deals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Ошибка создания сделки')
      setForm({ title: '', client_name: '', contact_name: '', raw_input: '' })
      await loadDeals()
      window.location.href = `/deals/${data.id}`
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="container">
      <h1>Сделки</h1>
      <Link href="/instruments" className="analyze-button inline-btn">Справочник приборов</Link>

      <section className="result-card">
        <h3>Новая сделка</h3>
        <input placeholder="Название" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <input
          placeholder="Компания клиента"
          value={form.client_name}
          onChange={(e) => setForm({ ...form, client_name: e.target.value })}
        />
        <input
          placeholder="Контактное лицо"
          value={form.contact_name}
          onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
        />
        <textarea
          className="deal-input"
          placeholder="Первичная информация по запросу клиента"
          value={form.raw_input}
          onChange={(e) => setForm({ ...form, raw_input: e.target.value })}
        />
        <button className="analyze-button" onClick={createDeal} disabled={loading}>
          {loading ? 'Создание...' : 'Создать и проанализировать'}
        </button>
        {error ? <div className="error-box">{error}</div> : null}
      </section>

      <section className="cards-grid">
        {deals.map((d) => (
          <article key={d.id} className="result-card">
            <h3>{d.title}</h3>
            <p>Клиент: {d.client_name}</p>
            <p>Вероятность: {d.deal_probability}</p>
            <p>Выручка: {d.potential_revenue}</p>
            <Link href={`/deals/${d.id}`}>Открыть</Link>
          </article>
        ))}
      </section>
    </main>
  )
}
