import { useState, useEffect } from 'react'
import { Plus, Loader2, Pencil } from 'lucide-react'
import ConfidenceBadge from '../ui/ConfidenceBadge'

export default function AccessoriesTab() {
  const [skus, setSkus] = useState([])
  const [competitors, setCompetitors] = useState([])
  const [accessoryTypes, setAccessoryTypes] = useState([])
  const [products, setProducts] = useState([])
  const [selectedPackaging, setSelectedPackaging] = useState(null) // { type, id, label }
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [form, setForm] = useState({ accessory_type_id: '', product_id: '', default_unit_price: '' })

  useEffect(() => {
    Promise.all([
      fetch('/api/kb/skus').then(r => r.json()),
      fetch('/api/kb/competitors').then(r => r.json()),
      fetch('/api/kb/accessory-types').then(r => r.json()),
      fetch('/api/kb/products').then(r => r.json()),
    ]).then(([skuData, compData, accData, prodData]) => {
      setSkus(skuData.skus ?? [])
      setCompetitors(compData.competitors ?? [])
      setAccessoryTypes(accData.accessory_types ?? [])
      setProducts(prodData.products ?? [])
      setLoading(false)
      if (skuData.skus?.length) {
        setSelectedPackaging({ type: 'goodpack', id: skuData.skus[0].id, label: skuData.skus[0].sku_code })
      }
    })
  }, [])

  useEffect(() => {
    if (!selectedPackaging) return
    const param = selectedPackaging.type === 'goodpack' ? 'goodpack_sku_id' : 'competitor_unit_id'
    fetch(`/api/kb/packaging-accessories?${param}=${selectedPackaging.id}`)
      .then(r => r.json())
      .then(data => setItems(data.packaging_accessories ?? []))
  }, [selectedPackaging])

  function reload() {
    if (!selectedPackaging) return
    const param = selectedPackaging.type === 'goodpack' ? 'goodpack_sku_id' : 'competitor_unit_id'
    fetch(`/api/kb/packaging-accessories?${param}=${selectedPackaging.id}`)
      .then(r => r.json())
      .then(data => setItems(data.packaging_accessories ?? []))
  }

  async function handleSavePrice(itemId, price) {
    const item = items.find(i => i.id === itemId)
    if (!item) return
    await fetch(`/api/kb/packaging-accessories/${itemId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        packaging_type: item.packaging_type,
        goodpack_sku_id: item.goodpack_sku_id,
        competitor_unit_id: item.competitor_unit_id,
        product_id: item.product_id,
        accessory_type_id: item.accessory_type_id,
        default_unit_price: parseFloat(price),
        confidence_level: 'verified',
        source_type: 'interno',
        source_detail: 'Atualizado manualmente via Knowledge Base',
      }),
    })
    setEditingId(null)
    reload()
  }

  async function handleAddAccessory() {
    if (!form.accessory_type_id) return
    await fetch('/api/kb/packaging-accessories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        packaging_type: selectedPackaging.type,
        goodpack_sku_id: selectedPackaging.type === 'goodpack' ? selectedPackaging.id : null,
        competitor_unit_id: selectedPackaging.type === 'competitor' ? selectedPackaging.id : null,
        product_id: form.product_id ? parseInt(form.product_id) : null,
        accessory_type_id: parseInt(form.accessory_type_id),
        default_unit_price: form.default_unit_price ? parseFloat(form.default_unit_price) : null,
        confidence_level: form.default_unit_price ? 'verified' : 'validation_required',
        source_type: 'interno',
        source_detail: 'Adicionado manualmente via Knowledge Base',
      }),
    })
    setShowAddForm(false)
    setForm({ accessory_type_id: '', product_id: '', default_unit_price: '' })
    reload()
  }

  if (loading) {
    return <div className="flex justify-center py-10"><Loader2 size={18} className="animate-spin text-slate-400" /></div>
  }

  const genericItems = items.filter(i => !i.product_id)
  const specializedItems = items.filter(i => i.product_id)

  return (
    <div>
      {/* Seletor de embalagem */}
      <div className="flex flex-wrap gap-2 mb-5">
        {skus.map(sku => (
          <button
            key={`gp-${sku.id}`}
            onClick={() => setSelectedPackaging({ type: 'goodpack', id: sku.id, label: sku.sku_code })}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              selectedPackaging?.type === 'goodpack' && selectedPackaging?.id === sku.id
                ? 'bg-[#1a3a5c] text-white border-[#1a3a5c]'
                : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
            }`}
          >
            {sku.sku_code}
          </button>
        ))}
        {competitors.map(c => (
          <button
            key={`comp-${c.id}`}
            onClick={() => setSelectedPackaging({ type: 'competitor', id: c.id, label: c.unit_name })}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              selectedPackaging?.type === 'competitor' && selectedPackaging?.id === c.id
                ? 'bg-[#1a3a5c] text-white border-[#1a3a5c]'
                : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
            }`}
          >
            {c.unit_name}
          </button>
        ))}
      </div>

      {selectedPackaging && (
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-slate-800">
              Acessórios — {selectedPackaging.label}
            </h3>
            <button
              onClick={() => setShowAddForm(s => !s)}
              className="flex items-center gap-1 text-xs text-[#1a3a5c] hover:underline"
            >
              <Plus size={13} /> Adicionar acessório
            </button>
          </div>

          {showAddForm && (
            <div className="mb-4 pb-4 border-b border-slate-100 flex flex-wrap items-end gap-2">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Acessório</label>
                <select
                  value={form.accessory_type_id}
                  onChange={e => setForm(f => ({ ...f, accessory_type_id: e.target.value }))}
                  className="px-2 py-1.5 text-sm border border-slate-200 rounded-md"
                >
                  <option value="">Selecione...</option>
                  {accessoryTypes.map(a => (
                    <option key={a.id} value={a.id}>{a.accessory_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Produto (opcional)</label>
                <select
                  value={form.product_id}
                  onChange={e => setForm(f => ({ ...f, product_id: e.target.value }))}
                  className="px-2 py-1.5 text-sm border border-slate-200 rounded-md"
                >
                  <option value="">Default (qualquer produto)</option>
                  {products.map(p => (
                    <option key={p.id} value={p.id}>{p.product_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Preço (USD)</label>
                <input
                  type="number"
                  step="0.01"
                  value={form.default_unit_price}
                  onChange={e => setForm(f => ({ ...f, default_unit_price: e.target.value }))}
                  placeholder="opcional"
                  className="w-28 px-2 py-1.5 text-sm border border-slate-200 rounded-md"
                />
              </div>
              <button
                onClick={handleAddAccessory}
                className="px-3 py-1.5 text-sm bg-[#1a3a5c] text-white rounded-md hover:bg-[#1a3a5c]/90"
              >
                Adicionar
              </button>
            </div>
          )}

          <p className="text-xs text-slate-400 mb-2">Default (qualquer produto)</p>
          <AccessoryList
            items={genericItems}
            editingId={editingId}
            setEditingId={setEditingId}
            onSavePrice={handleSavePrice}
          />

          {specializedItems.length > 0 && (
            <>
              <p className="text-xs text-slate-400 mb-2 mt-4">Específico por produto</p>
              <AccessoryList
                items={specializedItems}
                editingId={editingId}
                setEditingId={setEditingId}
                onSavePrice={handleSavePrice}
                showProduct
              />
            </>
          )}

          {items.length === 0 && (
            <p className="text-xs text-slate-400">Nenhum acessório cadastrado para esta embalagem ainda.</p>
          )}
        </div>
      )}
    </div>
  )
}

function AccessoryList({ items, editingId, setEditingId, onSavePrice, showProduct }) {
  const [tempPrice, setTempPrice] = useState('')

  if (items.length === 0) {
    return <p className="text-xs text-slate-300 mb-3">Nenhum.</p>
  }

  return (
    <div className="space-y-1.5 mb-2">
      {items.map(item => (
        <div key={item.id} className="flex items-center justify-between text-sm py-1.5 border-t border-slate-50">
          <div className="flex items-center gap-2">
            <span className="text-slate-700">{item.accessory_name}</span>
            {showProduct && (
              <span className="text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
                {item.product_name}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {editingId === item.id ? (
              <>
                <input
                  type="number"
                  step="0.01"
                  autoFocus
                  defaultValue={item.default_unit_price ?? ''}
                  onChange={e => setTempPrice(e.target.value)}
                  className="w-24 px-2 py-1 text-sm border border-slate-200 rounded-md"
                />
                <button
                  onClick={() => onSavePrice(item.id, tempPrice)}
                  className="text-xs text-[#1a3a5c] font-medium"
                >
                  Salvar
                </button>
              </>
            ) : (
              <>
                <span className="text-slate-700">
                  {item.default_unit_price != null ? `$${item.default_unit_price.toFixed(2)}` : '— sem preço —'}
                </span>
                <button onClick={() => { setEditingId(item.id); setTempPrice('') }} className="text-slate-300 hover:text-slate-500">
                  <Pencil size={13} />
                </button>
              </>
            )}
            <ConfidenceBadge level={item.confidence_level} />
          </div>
        </div>
      ))}
    </div>
  )
}
