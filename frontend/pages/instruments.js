import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'

const emptyForm = {
  instrument_name: '',
  aliases: '',
  category: 'general',
  service_type: 'Поверка',
  price: 0,
  cost: 0,
  duration_days: 0,
  duration_hours: 0,
  rush_markup_percent: 0,
  on_site_markup_percent: 0,
  is_on_site_available: false,
}

export default function InstrumentsPage() {
  const [rows, setRows] = useState([])
  const [serviceTypes, setServiceTypes] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState('')

  const loadData = async () => {
    const [rulesRes, servicesRes] = await Promise.all([
      fetch(`${API_BASE}/instruments`),
      fetch(`${API_BASE}/service-types`),
    ])
    const [rulesData, servicesData] = await Promise.all([rulesRes.json(), servicesRes.json()])
    if (rulesRes.ok) setRows(rulesData)
    if (servicesRes.ok) setServiceTypes(servicesData)
  }

  useEffect(() => {
    loadData()
  }, [])

  const saveRow = async (row) => {
    setError('')
    const res = await fetch(`${API_BASE}/instruments/${row.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(row),
    })
    const data = await res.json()
    if (!res.ok) return setError(data.detail || 'Ошибка сохранения')
    setRows((prev) => prev.map((item) => (item.id === row.id ? data : item)))
  }

  const addInstrument = async () => {
    setError('')
    const res = await fetch(`${API_BASE}/instruments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    const data = await res.json()
    if (!res.ok) return setError(data.detail || 'Ошибка добавления')
    setRows((prev) => [...prev, data])
    setForm(emptyForm)
    if (!serviceTypes.find((s) => s.name === data.service_type)) {
      setServiceTypes((prev) => [...prev, { id: Date.now(), name: data.service_type }])
    }
  }

  const updateCell = (id, key, value) => {
    setRows((prev) => prev.map((row) => (row.id === id ? { ...row, [key]: value } : row)))
  }

  return (
    <main className="container">
      <h1>Справочник приборов</h1>
      <p className="subtitle">Редактируйте цены, себестоимость, сроки, коэффициенты и aliases</p>
      {error ? <div className="error-box">{error}</div> : null}

      <section className="result-card">
        <h3>Добавить прибор</h3>
        <div className="form-grid">
          {Object.keys(emptyForm).map((key) => (
            <label key={key}>
              {key}
              {key === 'is_on_site_available' ? (
                <input
                  type="checkbox"
                  checked={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.checked })}
                />
              ) : (
                <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
              )}
            </label>
          ))}
        </div>
        <button className="analyze-button" onClick={addInstrument}>Добавить прибор</button>
      </section>

      <section className="result-card">
        <h3>Таблица правил</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Прибор</th><th>Aliases</th><th>Категория</th><th>Услуга</th><th>Цена</th><th>Себестоимость</th>
                <th>Дни</th><th>Часы</th><th>Rush %</th><th>On-site %</th><th>Выезд</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td><input value={row.instrument_name} onChange={(e) => updateCell(row.id, 'instrument_name', e.target.value)} /></td>
                  <td><input value={row.aliases} onChange={(e) => updateCell(row.id, 'aliases', e.target.value)} /></td>
                  <td><input value={row.category} onChange={(e) => updateCell(row.id, 'category', e.target.value)} /></td>
                  <td>
                    <input list="service-types" value={row.service_type} onChange={(e) => updateCell(row.id, 'service_type', e.target.value)} />
                  </td>
                  <td><input value={row.price} onChange={(e) => updateCell(row.id, 'price', Number(e.target.value || 0))} /></td>
                  <td><input value={row.cost} onChange={(e) => updateCell(row.id, 'cost', Number(e.target.value || 0))} /></td>
                  <td><input value={row.duration_days} onChange={(e) => updateCell(row.id, 'duration_days', Number(e.target.value || 0))} /></td>
                  <td><input value={row.duration_hours} onChange={(e) => updateCell(row.id, 'duration_hours', Number(e.target.value || 0))} /></td>
                  <td><input value={row.rush_markup_percent} onChange={(e) => updateCell(row.id, 'rush_markup_percent', Number(e.target.value || 0))} /></td>
                  <td><input value={row.on_site_markup_percent} onChange={(e) => updateCell(row.id, 'on_site_markup_percent', Number(e.target.value || 0))} /></td>
                  <td><input type="checkbox" checked={row.is_on_site_available} onChange={(e) => updateCell(row.id, 'is_on_site_available', e.target.checked)} /></td>
                  <td><button className="analyze-button" onClick={() => saveRow(row)}>Сохранить</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <datalist id="service-types">
          {serviceTypes.map((s) => (
            <option key={s.id} value={s.name} />
          ))}
        </datalist>
      </section>
    </main>
  )
}
