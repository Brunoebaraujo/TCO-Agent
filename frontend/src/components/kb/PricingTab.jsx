import { useState, useEffect } from 'react'
import { Plus, Loader2 } from 'lucide-react'
import ConfidenceBadge from '../ui/ConfidenceBadge'

export default function PricingTab() {
  const [competitors, setCompetitors] = useState([])
  const [pricingByCompetitor, setPricingByCompetitor] = useState({})
  const [loading, setLoading] = useState(true)
  const [addingFor, setAddingFor] = useState(null)
  const [form, setForm] = useState({ unit_price: '', region: 'GLOBAL', source_detail: '' })

  async function loadAll() {
    setLoading(true)
    const res = await fetch('/api/kb/competitors')
    const data = await res.json()
    setCompetitors(data.competitors ?? [])

    const pricingMap = {}
    for (const c of data.competitors ?? []) {
      const pRes = await fetch(`/api/kb/competitors/${c.id}/pricing`)
      const pData = await pRes.json()
      pricingMap[c.id] = pData.pricing ?? []
    }
    setPricingByCompetitor(pricingMap)
    setLoading(false)
  }

  useEffect(() => { loadAll() }, [])

  async function handleAddPrice(competitorId) {
    if (!form.unit_price) return
    await fetch(`/api/kb/competitors/${competitorId}/pricing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        unit_price: parseFloat(form.unit_price),
        region: form.region,
        source_type: 'cliente',
        source_detail: form.source_detail || null,
        confidence_level: 'verified',
      }),
    })
    setAddingFor(null)
    setForm({ unit_price: '', region: 'GLOBAL', source_detail: '' })
    loadAll()
  }

  if (loading) {
    return <div className="flex justify-center py-10"><Loader2 size={18} className="animate-spin text-slate-400" /></div>
  }

  return (
    <div className="space-y-4">
      {competitors.map(competitor => (
        <div key={competitor.id} className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-800">{competitor.unit_name}</h3>
            <button
              onClick={() => setAddingFor(addingFor === competitor.id ? null : competitor.id)}
              className="flex items-center gap-1 text-xs text-[#1a3a5c] hover:underline"
            >
              <Plus size={13} /> Novo preço
            </button>
          </div>

          {(pricingByCompetitor[competitor.id] ?? []).length === 0 ? (
            <p className="text-xs text-slate-400 mt-2">Nenhum preço cadastrado ainda.</p>
          ) : (
            <div className="mt-3 space-y-1.5">
              {pricingByCompetitor[competitor.id].map(p => (
                <div key={p.id} className="flex items-center justify-between text-sm py-1.5 border-t border-slate-50">
                  <div>
                    <span className="text-slate-700">${p.unit_price.toFixed(2)} {p.currency}</span>
                    <span className="text-xs text-slate-400 ml-2">
                      {p.region ?? 'GLOBAL'} · {p.collected_at}
                      {p.source_detail && ` · ${p.source_detail}`}
                    </span>
                  </div>
                  <ConfidenceBadge level={p.confidence_level} />
                </div>
              ))}
            </div>
          )}

          {addingFor === competitor.id && (
            <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap items-end gap-2">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Preço (USD)</label>
                <input
                  type="number"
                  step="0.01"
                  value={form.unit_price}
                  onChange={e => setForm(f => ({ ...f, unit_price: e.target.value }))}
                  className="w-28 px-2 py-1.5 text-sm border border-slate-200 rounded-md"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Região</label>
                <select
                  value={form.region}
                  onChange={e => setForm(f => ({ ...f, region: e.target.value }))}
                  className="px-2 py-1.5 text-sm border border-slate-200 rounded-md"
                >
                  <option value="GLOBAL">Global</option>
                  <option value="LATAM">LATAM</option>
                  <option value="EUROPE">Europe</option>
                  <option value="ASIA">Asia</option>
                  <option value="NAMERICA">North America</option>
                  <option value="MEA">Middle East & Africa</option>
                </select>
              </div>
              <div className="flex-1 min-w-[160px]">
                <label className="block text-xs text-slate-400 mb-1">Fonte (opcional)</label>
                <input
                  type="text"
                  value={form.source_detail}
                  onChange={e => setForm(f => ({ ...f, source_detail: e.target.value }))}
                  placeholder="Ex: informado pelo cliente X"
                  className="w-full px-2 py-1.5 text-sm border border-slate-200 rounded-md"
                />
              </div>
              <button
                onClick={() => handleAddPrice(competitor.id)}
                className="px-3 py-1.5 text-sm bg-[#1a3a5c] text-white rounded-md hover:bg-[#1a3a5c]/90"
              >
                Salvar
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
