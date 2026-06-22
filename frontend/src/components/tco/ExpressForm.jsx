import { useEffect, useState } from 'react'
import { Zap, Loader2 } from 'lucide-react'

const inputClass =
  'w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/20 focus:border-[#1a3a5c] bg-slate-50'
const labelClass = 'text-xs font-medium text-slate-600 block mb-1.5'

/**
 * Formulário estruturado do modo TCO Express — substitui a entrada em
 * texto livre como porta de entrada de uma nova análise. Garante que os
 * 9 campos obrigatórios cheguem completos e bem tipados ao agente (SKU
 * validado contra a base em vez de digitado livre, números como número),
 * em vez de depender do vendedor formatar tudo certo num texto corrido.
 *
 * Ao enviar, monta uma mensagem em texto formatada e chama onSubmit(text)
 * — o restante do fluxo (chamada ao agente, dashboard, refinamento) segue
 * exatamente como uma mensagem de chat normal.
 */
export default function ExpressForm({ onSubmit, loading }) {
  const [skus, setSkus] = useState([])
  const [competitors, setCompetitors] = useState([])
  const [productOptions, setProductOptions] = useState([])
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [loadError, setLoadError] = useState(false)

  const [form, setForm] = useState({
    skuGoodpack: '',
    skuConcorrente: '',
    produtoIndex: '',
    leaseDays: '180',
    origem: '',
    destino: '',
    precoGoodpack: '',
    precoConcorrente: '',
    frete: '',
    volume: '',
    regional: 'GLOBAL',
  })

  useEffect(() => {
    Promise.all([
      fetch('/api/kb/skus').then(r => r.json()),
      fetch('/api/kb/competitors').then(r => r.json()),
      fetch('/api/kb/products/full-tree').then(r => r.json()),
    ])
      .then(([skuData, compData, treeData]) => {
        setSkus(skuData.skus ?? [])
        setCompetitors(compData.competitors ?? [])

        const flatProducts = []
        for (const cat of treeData.tree ?? []) {
          for (const p of cat.products ?? []) {
            if (p.types?.length) {
              for (const t of p.types) {
                flatProducts.push({ label: `${p.product_name} — ${t.type_name}`, product: p.product_name, type: t.type_name })
              }
            } else {
              flatProducts.push({ label: p.product_name, product: p.product_name, type: null })
            }
          }
        }
        setProductOptions(flatProducts)

        setForm(f => ({
          ...f,
          skuGoodpack: skuData.skus?.[0]?.sku_code ?? '',
          skuConcorrente: compData.competitors?.[0]?.unit_name ?? '',
        }))
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoadingOptions(false))
  }, [])

  function update(field, value) {
    setForm(f => ({ ...f, [field]: value }))
  }

  const isComplete = Object.entries(form).every(([key, v]) => {
    if (key === 'produtoIndex') return v !== ''
    if (key === 'regional') return true
    return String(v).trim() !== ''
  })

  function handleSubmit(e) {
    e.preventDefault()
    if (!isComplete || loading) return

    const produto = productOptions[Number(form.produtoIndex)]

    onSubmit({
      goodpackSku: form.skuGoodpack,
      competitorName: form.skuConcorrente,
      productName: produto?.product ?? '',
      typeName: produto?.type ?? null,
      origin: form.origem,
      destination: form.destino,
      goodpackUnitPrice: form.precoGoodpack,
      competitorUnitPrice: form.precoConcorrente,
      freightPerContainer: form.frete,
      volumeMt: form.volume,
      leaseDays: form.leaseDays,
      regional: form.regional || 'GLOBAL',
    })
  }

  if (loadingOptions) {
    return (
      <div className="flex items-center justify-center py-12 text-slate-400">
        <Loader2 size={18} className="animate-spin mr-2" />
        <span className="text-sm">Carregando opções da base...</span>
      </div>
    )
  }

  if (loadError || skus.length === 0 || competitors.length === 0) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700">
        Não consegui carregar SKUs/embalagens/produtos da base (backend fora do ar ou base vazia).
        Você ainda pode descrever a oportunidade em texto livre na caixa de chat abaixo.
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-xl p-5 max-w-3xl">
      <div className="flex items-center gap-2 mb-4">
        <Zap size={18} className="text-[#1a3a5c]" />
        <span className="text-base font-medium text-slate-800">TCO express</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3.5">
        <div>
          <label className={labelClass}>SKU Goodpack</label>
          <select className={inputClass} value={form.skuGoodpack} onChange={e => update('skuGoodpack', e.target.value)}>
            {skus.map(s => <option key={s.id} value={s.sku_code}>{s.sku_code}</option>)}
          </select>
        </div>
        <div>
          <label className={labelClass}>SKU concorrente</label>
          <select className={inputClass} value={form.skuConcorrente} onChange={e => update('skuConcorrente', e.target.value)}>
            {competitors.map(c => <option key={c.id} value={c.unit_name}>{c.unit_name}</option>)}
          </select>
        </div>

        <div>
          <label className={labelClass}>Produto</label>
          <select className={inputClass} value={form.produtoIndex} onChange={e => update('produtoIndex', e.target.value)}>
            <option value="">Selecione...</option>
            {productOptions.map((p, i) => <option key={i} value={i}>{p.label}</option>)}
          </select>
        </div>
        <div>
          <label className={labelClass}>Lease days</label>
          <input type="number" step="10" className={inputClass} value={form.leaseDays} onChange={e => update('leaseDays', e.target.value)} />
        </div>

        <div>
          <label className={labelClass}>Origem</label>
          <input type="text" className={inputClass} placeholder="Santos, BR" value={form.origem} onChange={e => update('origem', e.target.value)} />
        </div>
        <div>
          <label className={labelClass}>Destino</label>
          <input type="text" className={inputClass} placeholder="Rotterdam, NL" value={form.destino} onChange={e => update('destino', e.target.value)} />
        </div>

        <div>
          <label className={labelClass}>Preço Goodpack (por unidade)</label>
          <input type="number" step="0.01" className={inputClass} value={form.precoGoodpack} onChange={e => update('precoGoodpack', e.target.value)} />
        </div>
        <div>
          <label className={labelClass}>Preço concorrente (por unidade)</label>
          <input type="number" step="0.01" className={inputClass} value={form.precoConcorrente} onChange={e => update('precoConcorrente', e.target.value)} />
        </div>

        <div>
          <label className={labelClass}>Frete por container</label>
          <input type="number" step="1" className={inputClass} value={form.frete} onChange={e => update('frete', e.target.value)} />
        </div>
        <div>
          <label className={labelClass}>Volume total (MT)</label>
          <input type="number" step="1" className={inputClass} value={form.volume} onChange={e => update('volume', e.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <label className={labelClass}>Regional</label>
          <select className={inputClass} value={form.regional} onChange={e => update('regional', e.target.value)}>
            <option value="GLOBAL">Global</option>
            <option value="BRAZIL">Brasil</option>
            <option value="LATAM">América Latina</option>
            <option value="NAMERICA">América do Norte</option>
            <option value="EUROPE">Europa</option>
            <option value="ASIA">Ásia</option>
          </select>
        </div>
      </div>

      <button
        type="submit"
        disabled={!isComplete || loading}
        className="w-full mt-5 px-4 py-2.5 bg-[#1a3a5c] text-white rounded-xl hover:bg-[#1a3a5c]/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2 text-sm font-medium"
      >
        {loading ? <Loader2 size={15} className="animate-spin" /> : null}
        Gerar TCO draft
      </button>

      <p className="text-[11px] text-slate-400 mt-2 text-center">
        Prefere descrever em texto livre? Use a caixa de chat abaixo em vez do formulário.
      </p>
    </form>
  )
}
