import { useState } from 'react'
import { Database, Check, Trash2, Package } from 'lucide-react'

/**
 * Painel interativo exibido quando o agente emite um bloco KB_OFFER.
 * Mostra checkboxes para cada item elegível e um botão de confirmação.
 */
export default function KBOfferPanel({ offer, sessionId }) {
  const [checked, setChecked] = useState(
    () => Object.fromEntries((offer.items ?? []).map((item, i) => [i, item.checked ?? true]))
  )
  const [status, setStatus] = useState('idle') // idle | saving | done | error
  const [result, setResult] = useState(null)

  const toggle = (i) => setChecked(prev => ({ ...prev, [i]: !prev[i] }))

  const selectedItems = (offer.items ?? []).filter((_, i) => checked[i])

  async function handleConfirm() {
    if (selectedItems.length === 0) return
    setStatus('saving')
    try {
      const res = await fetch('/api/kb/apply-offer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: selectedItems }),
      })
      const data = await res.json()
      setResult(data)
      setStatus('done')
    } catch {
      setStatus('error')
    }
  }

  const iconForType = (type) => {
    if (type === 'remove_accessory') return <Trash2 size={12} className="text-rose-400 shrink-0" />
    if (type === 'qty') return <Package size={12} className="text-blue-400 shrink-0" />
    return <Database size={12} className="text-emerald-400 shrink-0" />
  }

  if (status === 'done') {
    return (
      <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Check size={14} className="text-emerald-600" />
          <span className="text-sm font-medium text-emerald-800">Base de conhecimento atualizada</span>
        </div>
        {result?.saved?.length > 0 && (
          <ul className="text-xs text-emerald-700 space-y-0.5 ml-5 list-disc">
            {result.saved.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        )}
        {result?.skipped?.length > 0 && (
          <p className="text-xs text-slate-400 mt-1">Não encontrados: {result.skipped.join(', ')}</p>
        )}
      </div>
    )
  }

  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Database size={14} className="text-[#1a3a5c]" />
        <span className="text-sm font-medium text-slate-800">Atualizar base de conhecimento</span>
      </div>

      {offer.intro && (
        <p className="text-xs text-slate-500 mb-3">{offer.intro}</p>
      )}

      <div className="space-y-2 mb-4">
        {(offer.items ?? []).map((item, i) => (
          <label
            key={i}
            className={`flex items-center gap-2.5 cursor-pointer rounded-lg px-3 py-2 border transition-colors ${
              checked[i]
                ? 'border-[#1a3a5c]/20 bg-white'
                : 'border-transparent bg-transparent opacity-50'
            }`}
          >
            <input
              type="checkbox"
              checked={!!checked[i]}
              onChange={() => toggle(i)}
              className="accent-[#1a3a5c] w-3.5 h-3.5 shrink-0"
            />
            {iconForType(item.type)}
            <span className="text-xs text-slate-700 flex-1">{item.label}</span>
            {item.value != null && (
              <span className="text-xs font-medium text-slate-500 shrink-0">
                {item.type === 'qty' ? `${item.value} un` : `$${Number(item.value).toFixed(2)}`}
              </span>
            )}
          </label>
        ))}
      </div>

      {status === 'error' && (
        <p className="text-xs text-rose-500 mb-2">Erro ao salvar. Tente novamente.</p>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleConfirm}
          disabled={selectedItems.length === 0 || status === 'saving'}
          className="flex-1 py-2 text-sm font-medium text-white bg-[#1a3a5c] rounded-lg hover:bg-[#1a3a5c]/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {status === 'saving' ? 'Salvando…' : `Confirmar selecionados (${selectedItems.length})`}
        </button>
        <button
          onClick={() => setStatus('done')}
          className="px-4 py-2 text-sm text-slate-500 hover:text-slate-700 transition-colors"
        >
          Pular
        </button>
      </div>
    </div>
  )
}
