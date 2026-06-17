import { useState } from 'react'
import PricingTab from '../components/kb/PricingTab'
import AccessoriesTab from '../components/kb/AccessoriesTab'
import ProductsTab from '../components/kb/ProductsTab'

const TABS = [
  { id: 'pricing', label: 'Preços de embalagens' },
  { id: 'accessories', label: 'Acessórios por embalagem' },
  { id: 'products', label: 'Produtos' },
]

export default function KnowledgeBasePage() {
  const [activeTab, setActiveTab] = useState('pricing')

  return (
    <div className="px-6 py-8 max-w-5xl">
      <h1 className="text-lg font-semibold text-slate-800">Knowledge Base</h1>
      <p className="text-sm text-slate-400 mt-1">
        Manage competitor pricing, packaging accessories, and product structure used by the agent.
      </p>

      <div className="flex gap-1 mt-6 border-b border-slate-200">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'border-[#1a3a5c] text-[#1a3a5c] font-medium'
                : 'border-transparent text-slate-400 hover:text-slate-600'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {activeTab === 'pricing' && <PricingTab />}
        {activeTab === 'accessories' && <AccessoriesTab />}
        {activeTab === 'products' && <ProductsTab />}
      </div>
    </div>
  )
}
