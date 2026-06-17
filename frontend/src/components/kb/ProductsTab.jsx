import { useState, useEffect } from 'react'
import { Plus, Loader2, Trash2, ChevronRight } from 'lucide-react'

export default function ProductsTab() {
  const [tree, setTree] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedCategories, setExpandedCategories] = useState({})
  const [addingTo, setAddingTo] = useState(null)
  const [newName, setNewName] = useState('')

  function load() {
    setLoading(true)
    fetch('/api/kb/products/full-tree')
      .then(r => r.json())
      .then(data => setTree(data.tree ?? []))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  function toggleCategory(id) {
    setExpandedCategories(prev => ({ ...prev, [id]: !prev[id] }))
  }

  async function handleAddCategory() {
    if (!newName.trim()) return
    await fetch('/api/kb/product-categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category_name: newName }),
    })
    setNewName('')
    setAddingTo(null)
    load()
  }

  async function handleAddProduct(categoryId) {
    if (!newName.trim()) return
    await fetch('/api/kb/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category_id: categoryId, product_name: newName }),
    })
    setNewName('')
    setAddingTo(null)
    load()
  }

  async function handleAddType(productId) {
    if (!newName.trim()) return
    await fetch('/api/kb/product-types', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: productId, type_name: newName }),
    })
    setNewName('')
    setAddingTo(null)
    load()
  }

  async function handleDelete(level, id) {
    const endpoint = level === 'category' ? 'product-categories' : level === 'product' ? 'products' : 'product-types'
    await fetch(`/api/kb/${endpoint}/${id}`, { method: 'DELETE' })
    load()
  }

  if (loading) {
    return <div className="flex justify-center py-10"><Loader2 size={18} className="animate-spin text-slate-400" /></div>
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-slate-800">Categoria → Produto → Tipo</h3>
        <button
          onClick={() => setAddingTo({ level: 'category' })}
          className="flex items-center gap-1 text-xs text-[#1a3a5c] hover:underline"
        >
          <Plus size={13} /> Nova categoria
        </button>
      </div>

      {addingTo?.level === 'category' && (
        <InlineAddForm
          placeholder="Ex: Citrus"
          value={newName}
          onChange={setNewName}
          onSave={handleAddCategory}
          onCancel={() => { setAddingTo(null); setNewName('') }}
        />
      )}

      <div className="space-y-1 mt-2">
        {tree.map(category => (
          <div key={category.id} className="border-t border-slate-50 pt-2">
            <div className="flex items-center justify-between group">
              <button
                onClick={() => toggleCategory(category.id)}
                className="flex items-center gap-1.5 text-sm font-medium text-slate-700"
              >
                <ChevronRight
                  size={14}
                  className={`text-slate-400 transition-transform ${expandedCategories[category.id] ? 'rotate-90' : ''}`}
                />
                {category.category_name}
              </button>
              <div className="flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => setAddingTo({ level: 'product', parentId: category.id })}
                  className="text-xs text-[#1a3a5c] hover:underline"
                >
                  + produto
                </button>
                <button onClick={() => handleDelete('category', category.id)} className="text-slate-300 hover:text-red-500">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>

            {expandedCategories[category.id] && (
              <div className="ml-5 mt-1.5 space-y-1.5">
                {addingTo?.level === 'product' && addingTo.parentId === category.id && (
                  <InlineAddForm
                    placeholder="Ex: Orange"
                    value={newName}
                    onChange={setNewName}
                    onSave={() => handleAddProduct(category.id)}
                    onCancel={() => { setAddingTo(null); setNewName('') }}
                  />
                )}

                {category.products.map(product => (
                  <div key={product.id} className="text-sm">
                    <div className="flex items-center justify-between group">
                      <span className="text-slate-600">{product.product_name}</span>
                      <div className="flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => setAddingTo({ level: 'type', parentId: product.id })}
                          className="text-xs text-[#1a3a5c] hover:underline"
                        >
                          + tipo
                        </button>
                        <button onClick={() => handleDelete('product', product.id)} className="text-slate-300 hover:text-red-500">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>

                    {addingTo?.level === 'type' && addingTo.parentId === product.id && (
                      <div className="ml-4 mt-1">
                        <InlineAddForm
                          placeholder="Ex: NFC"
                          value={newName}
                          onChange={setNewName}
                          onSave={() => handleAddType(product.id)}
                          onCancel={() => { setAddingTo(null); setNewName('') }}
                        />
                      </div>
                    )}

                    {product.types.length > 0 && (
                      <div className="ml-4 mt-1 flex flex-wrap gap-1.5">
                        {product.types.map(type => (
                          <span
                            key={type.id}
                            className="group flex items-center gap-1 text-xs bg-slate-50 text-slate-500 px-2 py-1 rounded-md"
                          >
                            {type.type_name}
                            <button
                              onClick={() => handleDelete('type', type.id)}
                              className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-500"
                            >
                              <Trash2 size={10} />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function InlineAddForm({ placeholder, value, onChange, onSave, onCancel }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <input
        type="text"
        autoFocus
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') onSave(); if (e.key === 'Escape') onCancel() }}
        placeholder={placeholder}
        className="px-2 py-1 text-sm border border-slate-200 rounded-md"
      />
      <button onClick={onSave} className="text-xs text-[#1a3a5c] font-medium">Salvar</button>
      <button onClick={onCancel} className="text-xs text-slate-400">Cancelar</button>
    </div>
  )
}
