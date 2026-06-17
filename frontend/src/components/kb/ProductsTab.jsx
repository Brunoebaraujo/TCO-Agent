import { useState, useEffect } from 'react'
import { Plus, Loader2, Trash2 } from 'lucide-react'

export default function ProductsTab() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [form, setForm] = useState({ product_name: '', category_name: '' })

  function load() {
    setLoading(true)
    fetch('/api/kb/products')
      .then(r => r.json())
      .then(data => setProducts(data.products ?? []))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleAdd() {
    if (!form.product_name.trim()) return
    await fetch('/api/kb/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_name: form.product_name, category_name: form.category_name || null }),
    })
    setForm({ product_name: '', category_name: '' })
    setShowAddForm(false)
    load()
  }

  async function handleDelete(id) {
    await fetch(`/api/kb/products/${id}`, { method: 'DELETE' })
    load()
  }

  if (loading) {
    return <div className="flex justify-center py-10"><Loader2 size={18} className="animate-spin text-slate-400" /></div>
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-slate-800">Produtos transportados</h3>
        <button
          onClick={() => setShowAddForm(s => !s)}
          className="flex items-center gap-1 text-xs text-[#1a3a5c] hover:underline"
        >
          <Plus size={13} /> Novo produto
        </button>
      </div>

      {showAddForm && (
        <div className="mb-4 pb-4 border-b border-slate-100 flex flex-wrap items-end gap-2">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Nome do produto</label>
            <input
              type="text"
              value={form.product_name}
              onChange={e => setForm(f => ({ ...f, product_name: e.target.value }))}
              placeholder="Ex: FCOJ"
              className="px-2 py-1.5 text-sm border border-slate-200 rounded-md"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Categoria (opcional)</label>
            <input
              type="text"
              value={form.category_name}
              onChange={e => setForm(f => ({ ...f, category_name: e.target.value }))}
              placeholder="Ex: Citrus Juice"
              className="px-2 py-1.5 text-sm border border-slate-200 rounded-md"
            />
          </div>
          <button
            onClick={handleAdd}
            className="px-3 py-1.5 text-sm bg-[#1a3a5c] text-white rounded-md hover:bg-[#1a3a5c]/90"
          >
            Adicionar
          </button>
        </div>
      )}

      <div className="space-y-1.5">
        {products.map(p => (
          <div key={p.id} className="flex items-center justify-between text-sm py-1.5 border-t border-slate-50">
            <div>
              <span className="text-slate-700">{p.product_name}</span>
              {p.category_name && <span className="text-xs text-slate-400 ml-2">{p.category_name}</span>}
            </div>
            <button onClick={() => handleDelete(p.id)} className="text-slate-300 hover:text-red-500">
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
