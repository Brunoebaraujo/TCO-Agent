import React, { useEffect, useRef, useState } from 'react'
import { Download, ChevronDown, Loader2, Truck, Package, Layers, Boxes } from 'lucide-react'
import ConfidenceBadge from '../ui/ConfidenceBadge'

const STACK_COLORS = ['#378ADD', '#888780', '#85B7EB', '#BA7517', '#1D9E75']

function formatCurrency(value, currency = 'USD') {
  if (value == null) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(value)
}

function formatNumber(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('en-US').format(Math.round(value))
}

export default function TCOSummaryTable({ result, sessionId }) {
  const chartRef = useRef(null)
  const chartInstanceRef = useRef(null)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [exporting, setExporting] = useState(false)

  const categories = result?.categories ?? []
  const competitorName = result?.competitor_name ?? 'Concorrente'
  const goodpackTotalPerMt = result?.goodpack_total_per_mt
  const competitorTotalPerMt = result?.competitor_total_per_mt
  const logistics = result?.logistics

  async function handleExport(includeAssumptions) {
    if (!sessionId) return
    setExportMenuOpen(false)
    setExporting(true)
    try {
      const url = `/api/tco/${sessionId}/export/pptx?include_assumptions=${includeAssumptions}`
      const res = await fetch(url)
      if (!res.ok) throw new Error('Falha ao exportar')
      const blob = await res.blob()

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

    if (chartInstanceRef.current) {
      chartInstanceRef.current.destroy()
    }

    const totals = [goodpackTotalPerMt, competitorTotalPerMt]
    const maxTotal = Math.max(...totals.filter(t => t != null))

    const totalLabelPlugin = {
      id: 'totalLabel',
      afterDatasetsDraw(chart) {
        const { ctx, scales: { x, y } } = chart
        ctx.save()
        ctx.font = '500 12px sans-serif'
        ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--color-text-primary') || '#1e293b'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        chart.data.labels.forEach((label, i) => {
          const total = totals[i]
          if (total == null) return
          const xPos = x.getPixelForValue(i)
          const yPos = y.getPixelForValue(total)
          ctx.fillText('$' + total.toFixed(2), xPos, yPos - 6)
        })
        ctx.restore()
      },
    }

    chartInstanceRef.current = new window.Chart(chartRef.current, {
      type: 'bar',
      data: {
        labels: [result.goodpack_sku ?? 'Goodpack', competitorName],
        datasets: categories.map((c, i) => ({
          label: c.label,
          data: [c.goodpack, c.competitor],
          backgroundColor: STACK_COLORS[i % STACK_COLORS.length],
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 24 } },
        plugins: { legend: { display: false } },
        scales: {
          x: { stacked: true },
          y: {
            stacked: true,
            suggestedMax: maxTotal ? maxTotal * 1.12 : undefined,
            ticks: { callback: (v) => '$' + v },
          },
        },
      },
      plugins: [totalLabelPlugin],
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
    transport_type,
    simulated_metric_tonnes,
    lease_days,
    currency = 'USD',
    total_saving,
    saving_percentage,
    goodpack_total_per_unit,
    competitor_total_per_unit,
    assumptions = [],
  } = result

  const statCards = logistics ? [
    { icon: Truck, label: 'Transports needed', gp: logistics.goodpack?.transports_needed, comp: logistics.competitor?.transports_needed },
    { icon: Package, label: 'Units needed', gp: logistics.goodpack?.units_needed, comp: logistics.competitor?.units_needed },
    { icon: Layers, label: 'Pallet places', gp: logistics.goodpack?.pallet_places, comp: logistics.competitor?.pallet_places },
    { icon: Boxes, label: 'Full stacks', gp: logistics.goodpack?.full_stacks, comp: logistics.competitor?.full_stacks },
  ] : []

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 max-w-2xl">

      {/* Header da oportunidade */}
      <div className="mb-4 pb-3 border-b border-slate-100">
        <p className="text-sm font-medium text-slate-800">{customer_name}</p>
        <p className="text-xs text-slate-400 mt-0.5">
          {product_name} · {simulated_metric_tonnes} MT · {goodpack_sku} vs {competitor_name}
          {transport_type && ` · ${transport_type}`}
          {lease_days != null && ` · ${lease_days} lease days`}
        </p>
      </div>

      {/* Gráfico empilhado com total no topo */}
      <div className="flex gap-3 text-[11px] text-slate-500 mb-2 flex-wrap justify-center">
        {categories.map((c, i) => (
          <span key={i} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: STACK_COLORS[i % STACK_COLORS.length] }} />
            {c.label}
          </span>
        ))}
      </div>
      <div style={{ position: 'relative', height: '260px' }} className="mb-4">
        <canvas
          ref={chartRef}
          role="img"
          aria-label={`Gráfico de barras empilhadas comparando custo total por MT entre ${goodpack_sku} e ${competitor_name}, por categoria`}
        />
      </div>

      {/* Painel de estatísticas logísticas */}
      {statCards.length > 0 && (
        <div className="grid grid-cols-4 gap-2 mb-4">
          {statCards.map((s, i) => {
            const Icon = s.icon
            return (
              <div key={i} className="bg-slate-50 rounded-lg p-3 text-center">
                <Icon size={18} className="text-slate-400 mx-auto" />
                <p className="text-[11px] text-slate-400 mt-1.5 mb-0.5">{s.label}</p>
                <p className="text-sm font-medium text-slate-800">
                  {formatNumber(s.gp)}
                  <span className="text-[11px] text-slate-400 font-normal"> vs {formatNumber(s.comp)}</span>
                </p>
              </div>
            )
          })}
        </div>
      )}

      {/* Tabela comparativa: Cost/Unit + Cost/MT por categoria */}
      <div className="text-sm overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-400">
              <th className="text-left font-normal pb-1.5"></th>
              {categories.map((c, i) => (
                <th key={i} colSpan={2} className="text-center font-normal pb-1.5 border-l border-slate-100 px-2">
                  {c.label}
                </th>
              ))}
              <th colSpan={2} className="text-center font-normal pb-1.5 border-l border-slate-200 px-2">Total</th>
            </tr>
            <tr className="text-slate-400 border-b border-slate-100">
              <th className="text-left font-normal pb-1.5"></th>
              {categories.map((c, i) => (
                <React.Fragment key={i}>
                  <th className="text-right font-normal pb-1.5 border-l border-slate-100 px-2">Unit</th>
                  <th className="text-right font-normal pb-1.5 px-2">MT</th>
                </React.Fragment>
              ))}
              <th className="text-right font-normal pb-1.5 border-l border-slate-200 px-2">Unit</th>
              <th className="text-right font-normal pb-1.5 px-2">MT</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-slate-50">
              <td className="py-1.5 text-slate-700 font-medium">{goodpack_sku}</td>
              {categories.map((c, i) => (
                <React.Fragment key={i}>
                  <td className="text-right py-1.5 text-slate-600 border-l border-slate-100 px-2">{c.goodpack_per_unit?.toFixed(2) ?? '—'}</td>
                  <td className="text-right py-1.5 text-slate-600 px-2">{c.goodpack?.toFixed(2) ?? '—'}</td>
                </React.Fragment>
              ))}
              <td className="text-right py-1.5 text-slate-800 font-medium border-l border-slate-200 px-2">{goodpack_total_per_unit?.toFixed(2) ?? '—'}</td>
              <td className="text-right py-1.5 text-slate-800 font-medium px-2">{formatCurrency(goodpackTotalPerMt, currency)}</td>
            </tr>
            <tr>
              <td className="py-1.5 text-slate-700 font-medium">{competitor_name}</td>
              {categories.map((c, i) => (
                <React.Fragment key={i}>
                  <td className="text-right py-1.5 text-slate-600 border-l border-slate-100 px-2">{c.competitor_per_unit?.toFixed(2) ?? '—'}</td>
                  <td className="text-right py-1.5 text-slate-600 px-2">{c.competitor?.toFixed(2) ?? '—'}</td>
                </React.Fragment>
              ))}
              <td className="text-right py-1.5 text-slate-800 font-medium border-l border-slate-200 px-2">{competitor_total_per_unit?.toFixed(2) ?? '—'}</td>
              <td className="text-right py-1.5 text-slate-800 font-medium px-2">{formatCurrency(competitorTotalPerMt, currency)}</td>
            </tr>
          </tbody>
        </table>
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
