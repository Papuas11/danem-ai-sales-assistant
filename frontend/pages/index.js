import Link from 'next/link'

export default function HomePage() {
  return (
    <main className="container">
      <h1>DANEM AI Sales Assistant MVP v2</h1>
      <p className="subtitle">Управление сделками и AI-анализ метрологических запросов</p>
      <div className="result-card">
        <h3>Быстрый старт</h3>
        <p>Перейдите в раздел сделок для создания и обновления информации по клиенту.</p>
        <Link href="/deals" className="analyze-button inline-btn">
          Открыть сделки
        </Link>
        <Link href="/instruments" className="analyze-button inline-btn">
          Справочник приборов
        </Link>
      </div>
    </main>
  )
}
