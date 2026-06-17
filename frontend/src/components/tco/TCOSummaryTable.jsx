import { useEffect, useRef, useState } from 'react'
import { Download, ChevronDown, Loader2 } from 'lucide-react'
import ConfidenceBadge from '../ui/ConfidenceBadge'

function formatCurrency(value, currency = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(value)
}

export default function TCOSummaryTable({ result, sessionId }) {
  const chartRef = useRef(null)
  const chartInstanceRef = useRef(null)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [exporting, setExporting] = useState(false)

  const categories = result?.categories ?? []
  const competitorName = result?.competitor_name ?? 'Concorrente'

  async function handleExport(includeAssumptions) {
    if (!sessionId) return
    setExportMenuOpen(false)
    setExporting(true)
    try {
      const url = `/api/tco/${sessionId}/export/pptx?include_assumptions=${includeAssumptions}`
      const res = await fetch(url)
      if (!res.ok) throw new Error('Falha ao exportar')
      const blob = await res.blob()

      // Extrai o nome do arquivo sugerido pelo backend, com fallback
      const disposition = res.headers.get('Content-Disposition') || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : 'TCO.pptx'

      const downloadUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(downloadUrl)
    } catch (err) {
      console.error('Erro ao exportar PPTX:', err)
      alert('Não foi possível exportar o arquivo. Tente novamente.')
    } finally {
      setExporting(false)
    }
  }

  useEffect(() => {
    if (!result || !chartRef.current || categories.length === 0) return

    // Destroi gráfico anterior antes de criar um novo (evita memory leak em re-renders)
    if (chartInstanceRef.current) {
      chartInstanceRef.current.destroy()
    }

    chartInstanceRef.current = new window.Chart(chartRef.current, {
      type: 'bar',
      data: {
        labels: categories.map(c => c.label),
        datasets: [
          {
            label: 'Goodpack',
            data: categories.map(c => c.goodpack),
            backgroundColor: '#1D9E75',
          },
          {
            label: competitorName,
            data: categories.map(c => c.competitor),
            backgroundColor: '#888780',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            ticks: { callback: (v) => '$' + v },
          },
        },
      },
    })

    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy()
        chartInstanceRef.current = null
      }
    }
  }, [result])

  if (!result) return null

  const {
    customer_name,
    product_name,
    goodpack_sku,
    competitor_name,
    simulated_metric_tonnes,
    currency = 'USD',
    goodpack_total_per_mt,
    competitor_total_per_mt,
    total_saving,
    saving_percentage,
    assumptions = [],
  } = result

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 max-w-2xl">

      {/* Header da oportunidade */}
      <div className="mb-4 pb-3 border-b border-slate-100">
        <p className="text-sm font-medium text-slate-800">{customer_name}</p>
        <p className="text-xs text-slate-400 mt-0.5">
          {product_name} · {simulated_metric_tonnes} MT · {goodpack_sku} vs {competitor_name}
        </p>
      </div>

      {/* Tabela comparativa */}
      <div className="text-sm">
        <div className="grid grid-cols-[2fr_1fr_1fr_1fr] gap-2 text-xs text-slate-400 mb-1">
          <div>Categoria</div>
          <div className="text-right">Goodpack</div>
          <div className="text-right">{competitor_name}</div>
          <div className="text-right">Saving</div>
        </div>

        <div className="border-t border-slate-100 my-1.5" />

        {categories.map((cat, i) => {
          const saving = cat.competitor - cat.goodpack
          return (
            <div key={i} className="grid grid-cols-[2fr_1fr_1fr_1fr] gap-2 py-1.5">
              <div className="text-slate-700">{cat.label}</div>
              <div className="text-right text-slate-700">{formatCurrency(cat.goodpack, currency)}</div>
              <div className="text-right text-slate-700">{formatCurrency(cat.competitor, currency)}</div>
              <div className={`text-right font-medium ${saving >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                {formatCurrency(saving, currency)}
              </div>
            </div>
          )
        })}

        <div className="border-t border-slate-200 my-1.5" />

        <div className="grid grid-cols-[2fr_1fr_1fr_1fr] gap-2 py-1.5 font-medium">
          <div className="text-slate-800">Total por MT</div>
          <div className="text-right text-slate-800">{formatCurrency(goodpack_total_per_mt, currency)}</div>
          <div className="text-right text-slate-800">{formatCurrency(competitor_total_per_mt, currency)}</div>
          <div className="text-right text-emerald-600">
            {formatCurrency(competitor_total_per_mt - goodpack_total_per_mt, currency)}
          </div>
        </div>
      </div>

      {/* Gráfico comparativo */}
      <div className="mt-4 pt-4 border-t border-slate-100">
        <div className="flex gap-4 text-xs text-slate-500 mb-2">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: '#1D9E75' }} />
            Goodpack
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: '#888780' }} />
            {competitor_name}
          </span>
        </div>
        <div style={{ position: 'relative', height: '220px' }}>
          <canvas
            ref={chartRef}
            role="img"
            aria-label={`Gráfico de barras comparando custo por categoria entre Goodpack e ${competitor_name}`}
          />
        </div>
      </div>

      {/* Métricas-resumo */}
      <div className="grid grid-cols-3 gap-3 mt-4">
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-xs text-slate-400">Saving total</p>
          <p className="text-lg font-medium text-emerald-600">{formatCurrency(total_saving, currency)}</p>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-xs text-slate-400">Redução</p>
          <p className="text-lg font-medium text-slate-800">{saving_percentage}%</p>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-xs text-slate-400">Premissas</p>
          <p className="text-lg font-medium text-slate-800">{assumptions.length}</p>
        </div>
      </div>

      {/* Premissas usadas */}
      {assumptions.length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-100">
          <p className="text-xs text-slate-400 mb-2">Premissas usadas neste cálculo</p>
          <div className="space-y-2">
            {assumptions.map((a, i) => (
              <div key={i} className="bg-slate-50 rounded-lg px-3 py-2">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-xs text-slate-700 leading-relaxed flex-1">{a.label}</p>
                  <div className="flex-shrink-0">
                    <ConfidenceBadge level={a.confidence_level} />
                  </div>
                </div>
                {a.source && (
                  <p className="text-[11px] text-slate-400 mt-1">Fonte: {a.source}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Export */}
      {sessionId && (
        <div className="mt-4 pt-3 border-t border-slate-100 relative">
          <button
            onClick={() => setExportMenuOpen(o => !o)}
            disabled={exporting}
            className="flex items-center gap-2 px-3 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            <span>Exportar PowerPoint</span>
            <ChevronDown size={14} className="text-slate-400" />
          </button>

          {exportMenuOpen && (
            <div className="absolute bottom-full left-0 mb-1 bg-white border border-slate-200 rounded-lg shadow-sm py-1 w-64 z-10">
              <button
                onClick={() => handleExport(false)}
                className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                Apenas resumo
                <span className="block text-xs text-slate-400">Tabela, gráfico e saving total</span>
              </button>
              <button
                onClick={() => handleExport(true)}
                className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                Resumo + premissas
                <span className="block text-xs text-slate-400">Inclui slide com fontes e confiança</span>
              </button>
            </div>
          )}
        </div>
      )}

    </div>
  )
}
