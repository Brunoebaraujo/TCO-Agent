import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, ChevronDown, Loader2, Truck, Package, Layers, Boxes, TrendingUp, RotateCcw, AlertTriangle, Check, SlidersHorizontal } from 'lucide-react'
import ConfidenceBadge from '../ui/ConfidenceBadge'
import {
  recalcPackagingByPrice, recalcCategoryByUnitPrice, recalcCategoriesByQty,
  recalcLogistics, recalcTotals, matchAssumption, computeQtyRealPerUnitKg,
} from './dashboardCalc'

const STACK_COLORS = ['#378ADD', '#888780', '#85B7EB', '#BA7517', '#1D9E75']

function formatCurrency(value, currency = 'USD') {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(value)
}

function formatNumber(value) {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-US').format(Math.round(value))
}

export default function TCODashboard({ result, sessionId, overrides = {}, onOverrideChange = () => {} }) {
  const chartRef = useRef(null)
  const chartInstanceRef = useRef(null)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [exporting, setExporting] = useState(false)

  const [breakdown, setBreakdown] = useState([])
  const [competitorBreakdown, setCompetitorBreakdown] = useState([])
  const [qtyPerUnit, setQtyPerUnit] = useState(null)
  const [confirmedItems, setConfirmedItems] = useState(() => new Set())
  const [confirmedCompetitorItems, setConfirmedCompetitorItems] = useState(() => new Set())
  const [fullCustomization, setFullCustomization] = useState(false)
  const [handlingPackerPerUnit, setHandlingPackerPerUnit] = useState(null)
  const [handlingEnduserPerUnit, setHandlingEnduserPerUnit] = useState(null)

  // Capacidade & quantidade por container, dos dois lados — editável.
  const [goodpackVolumeLiters, setGoodpackVolumeLiters] = useState(null)
  const [goodpackMaxPayloadKg, setGoodpackMaxPayloadKg] = useState(null)
  const [goodpackQtyPerTransport, setGoodpackQtyPerTransport] = useState(null)
  const [competitorVolumeLiters, setCompetitorVolumeLiters] = useState(null)
  const [competitorMaxPayloadKg, setCompetitorMaxPayloadKg] = useState(null)
  const [competitorQtyPerTransport, setCompetitorQtyPerTransport] = useState(null)

  // Quando um TCO_RESULT NOVO chega (o agente recalculou), reaplica por cima
  // dele qualquer valor que o vendedor já tinha confirmado nesta sessão —
  // em vez de resetar tudo pro default do resultado novo e perder a edição.
  useEffect(() => {
    const ov = (key, fallback) => (overrides[key] !== undefined ? overrides[key] : fallback)

    setBreakdown((result?.packaging_breakdown ?? []).map(item => ({
      ...item, value: ov(`breakdown:${item.label}`, item.value),
    })))
    setCompetitorBreakdown((result?.competitor_packaging_breakdown ?? []).map(item => ({
      ...item, value: ov(`compBreakdown:${item.label}`, item.value),
    })))
    setQtyPerUnit(ov('qtyPerUnit', result?.goodpack_qty_per_unit_kg ?? null))
    setConfirmedItems(new Set())
    setConfirmedCompetitorItems(new Set())
    setFullCustomization(false)
    const packerCat = result?.categories?.find(c => c.label === 'Handling packer')
    const enduserCat = result?.categories?.find(c => c.label === 'Handling enduser')
    setHandlingPackerPerUnit(ov('handlingPackerPerUnit', packerCat?.goodpack_per_unit ?? null))
    setHandlingEnduserPerUnit(ov('handlingEnduserPerUnit', enduserCat?.goodpack_per_unit ?? null))

    setGoodpackVolumeLiters(ov('goodpackVolumeLiters', result?.goodpack_volume_liters ?? null))
    setGoodpackMaxPayloadKg(ov('goodpackMaxPayloadKg', result?.goodpack_max_payload_kg ?? null))
    setGoodpackQtyPerTransport(ov('goodpackQtyPerTransport', result?.goodpack_qty_per_transport ?? null))
    setCompetitorVolumeLiters(ov('competitorVolumeLiters', result?.competitor_volume_liters ?? null))
    setCompetitorMaxPayloadKg(ov('competitorMaxPayloadKg', result?.competitor_max_payload_kg ?? null))
    setCompetitorQtyPerTransport(ov('competitorQtyPerTransport', result?.competitor_qty_per_transport ?? null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result])

  const categories = result?.categories ?? []
  const competitorName = result?.competitor_name ?? 'Concorrente'
  const goodpackSku = result?.goodpack_sku ?? 'Goodpack'
  const currency = result?.currency ?? 'USD'

  const packagingCategory = categories.find(c => c.label === 'Packaging')
  const originalPackagingPerUnit = packagingCategory?.goodpack_per_unit ?? 0
  const originalPackagingPerMt = packagingCategory?.goodpack ?? 0
  const originalCompetitorPackagingPerUnit = packagingCategory?.competitor_per_unit ?? 0
  const originalCompetitorPackagingPerMt = packagingCategory?.competitor ?? 0

  const hasEditableBreakdown = breakdown.length > 0
  const hasEditableCompetitorBreakdown = competitorBreakdown.length > 0
  const hasEditableQty = qtyPerUnit != null

  const handlingPackerCategory = categories.find(c => c.label === 'Handling packer')
  const handlingEnduserCategory = categories.find(c => c.label === 'Handling enduser')

  const recalculated = useMemo(() => {
    const density = result?.product_density ?? null

    // --- Lado Goodpack ---
    const origGpQtyKg = result?.goodpack_qty_per_unit_kg ?? null
    const effectiveGpQty = hasEditableQty ? qtyPerUnit : origGpQtyKg
    const gpQtyChanged = hasEditableQty && effectiveGpQty !== origGpQtyKg
    const gpQtyPerTransport = goodpackQtyPerTransport ?? result?.goodpack_qty_per_transport ?? null
    const gpStackFullWarehouse = result?.goodpack_stack_full_warehouse ?? null
    const transportCostPerContainer = result?.goodpack_transport_cost_per_container ?? null
    const gpQtyRatio = gpQtyChanged && origGpQtyKg ? origGpQtyKg / effectiveGpQty : 1

    const recalcedByQtyGoodpack = gpQtyChanged && effectiveGpQty
      ? recalcCategoriesByQty(categories, 'goodpack', effectiveGpQty, origGpQtyKg, gpQtyPerTransport, transportCostPerContainer)
      : null

    // --- Lado Concorrente: qty real derivada de Volume/Peso editados (sem
    // campo "quantidade envasada" próprio — deriva igual o backend faz) ---
    const origCompQtyKg = result?.competitor_qty_per_unit_kg ?? null
    const derivedCompQtyKg = computeQtyRealPerUnitKg(competitorMaxPayloadKg, density, competitorVolumeLiters)
    const compQtyChanged = derivedCompQtyKg != null && derivedCompQtyKg !== origCompQtyKg
    const compQtyPerTransport = competitorQtyPerTransport ?? result?.competitor_qty_per_transport ?? null
    const compStackFullWarehouse = result?.competitor_stack_full_warehouse ?? null

    const recalcedByQtyCompetitor = compQtyChanged && derivedCompQtyKg
      ? recalcCategoriesByQty(categories, 'competitor', derivedCompQtyKg, origCompQtyKg, compQtyPerTransport, transportCostPerContainer)
      : null

    // Cada categoria com preço editável é recalculada pelo preço e depois
    // ajustada pela mesma proporção de qty (se a qty também mudou).
    const categoryOverrides = {}

    if (hasEditableBreakdown || hasEditableCompetitorBreakdown) {
      categoryOverrides.Packaging = categoryOverrides.Packaging || {}
      if (hasEditableBreakdown) {
        const pkg = recalcPackagingByPrice(breakdown, originalPackagingPerUnit, originalPackagingPerMt)
        categoryOverrides.Packaging.perMt = pkg.perMt * gpQtyRatio
      }
      if (hasEditableCompetitorBreakdown) {
        const compPkg = recalcPackagingByPrice(
          competitorBreakdown, originalCompetitorPackagingPerUnit, originalCompetitorPackagingPerMt
        )
        const compRatio = compQtyChanged && origCompQtyKg ? origCompQtyKg / derivedCompQtyKg : 1
        categoryOverrides.Packaging.competitorPerMt = compPkg.perMt * compRatio
      }
    }

    if (fullCustomization && handlingPackerCategory && handlingPackerPerUnit != null) {
      const hp = recalcCategoryByUnitPrice(
        handlingPackerPerUnit, handlingPackerCategory.goodpack_per_unit ?? 0, handlingPackerCategory.goodpack ?? 0
      )
      categoryOverrides['Handling packer'] = { perMt: hp.perMt * gpQtyRatio }
    }
    if (fullCustomization && handlingEnduserCategory && handlingEnduserPerUnit != null) {
      const he = recalcCategoryByUnitPrice(
        handlingEnduserPerUnit, handlingEnduserCategory.goodpack_per_unit ?? 0, handlingEnduserCategory.goodpack ?? 0
      )
      categoryOverrides['Handling enduser'] = { perMt: he.perMt * gpQtyRatio }
    }

    const totals = recalcTotals(result ?? {}, categoryOverrides, recalcedByQtyGoodpack, recalcedByQtyCompetitor)

    // Logística — recalcula os dois lados quando capacidade/qty mudou
    let logistics = result?.logistics
    const newGpLogistics = (effectiveGpQty && gpQtyPerTransport && gpStackFullWarehouse)
      ? recalcLogistics(result.simulated_metric_tonnes, effectiveGpQty, gpQtyPerTransport, gpStackFullWarehouse)
      : null
    const newCompLogistics = (derivedCompQtyKg && compQtyPerTransport)
      ? recalcLogistics(result.simulated_metric_tonnes, derivedCompQtyKg, compQtyPerTransport, compStackFullWarehouse)
      : null
    if (newGpLogistics || newCompLogistics) {
      logistics = {
        goodpack: newGpLogistics ? {
          units_needed: newGpLogistics.unitsNeeded,
          transports_needed: newGpLogistics.transportsNeeded,
          pallet_places: newGpLogistics.palletPlaces,
          full_stacks: newGpLogistics.fullStacks,
        } : result?.logistics?.goodpack,
        competitor: newCompLogistics ? {
          units_needed: newCompLogistics.unitsNeeded,
          transports_needed: newCompLogistics.transportsNeeded,
          pallet_places: newCompLogistics.palletPlaces,
          full_stacks: newCompLogistics.fullStacks,
        } : result?.logistics?.competitor,
      }
    }

    return { totals, logistics }
  }, [
    breakdown, competitorBreakdown, qtyPerUnit, result, hasEditableBreakdown, hasEditableQty,
    hasEditableCompetitorBreakdown, originalPackagingPerUnit, originalPackagingPerMt,
    originalCompetitorPackagingPerUnit, originalCompetitorPackagingPerMt, categories,
    fullCustomization, handlingPackerPerUnit, handlingEnduserPerUnit,
    handlingPackerCategory, handlingEnduserCategory,
    goodpackQtyPerTransport, competitorMaxPayloadKg, competitorVolumeLiters, competitorQtyPerTransport,
  ])

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

  function handleBreakdownChange(index, newValue) {
    setBreakdown(prev => prev.map((item, i) => i === index ? { ...item, value: newValue } : item))
    onOverrideChange(`breakdown:${breakdown[index]?.label}`, newValue)
  }

  function handleConfirmItem(index) {
    setConfirmedItems(prev => new Set(prev).add(index))
  }

  function handleCompetitorBreakdownChange(index, newValue) {
    setCompetitorBreakdown(prev => prev.map((item, i) => i === index ? { ...item, value: newValue } : item))
    onOverrideChange(`compBreakdown:${competitorBreakdown[index]?.label}`, newValue)
  }

  function handleConfirmCompetitorItem(index) {
    setConfirmedCompetitorItems(prev => new Set(prev).add(index))
  }

  function handleQtyPerUnitChange(newValue) {
    setQtyPerUnit(newValue)
    onOverrideChange('qtyPerUnit', newValue)
  }

  function handleHandlingPackerChange(newValue) {
    setHandlingPackerPerUnit(newValue)
    onOverrideChange('handlingPackerPerUnit', newValue)
  }

  function handleHandlingEnduserChange(newValue) {
    setHandlingEnduserPerUnit(newValue)
    onOverrideChange('handlingEnduserPerUnit', newValue)
  }

  function handleGoodpackVolumeChange(newValue) {
    setGoodpackVolumeLiters(newValue)
    onOverrideChange('goodpackVolumeLiters', newValue)
    const newQty = computeQtyRealPerUnitKg(goodpackMaxPayloadKg, result?.product_density, newValue)
    if (newQty != null) handleQtyPerUnitChange(newQty)
  }
  function handleGoodpackMaxPayloadChange(newValue) {
    setGoodpackMaxPayloadKg(newValue)
    onOverrideChange('goodpackMaxPayloadKg', newValue)
    const newQty = computeQtyRealPerUnitKg(newValue, result?.product_density, goodpackVolumeLiters)
    if (newQty != null) handleQtyPerUnitChange(newQty)
  }
  function handleGoodpackQtyPerTransportChange(newValue) {
    setGoodpackQtyPerTransport(newValue)
    onOverrideChange('goodpackQtyPerTransport', newValue)
  }
  function handleCompetitorVolumeChange(newValue) {
    setCompetitorVolumeLiters(newValue)
    onOverrideChange('competitorVolumeLiters', newValue)
  }
  function handleCompetitorMaxPayloadChange(newValue) {
    setCompetitorMaxPayloadKg(newValue)
    onOverrideChange('competitorMaxPayloadKg', newValue)
  }
  function handleCompetitorQtyPerTransportChange(newValue) {
    setCompetitorQtyPerTransport(newValue)
    onOverrideChange('competitorQtyPerTransport', newValue)
  }

  function handleReset() {
    setBreakdown((result?.packaging_breakdown ?? []).map(item => ({ ...item })))
    setCompetitorBreakdown((result?.competitor_packaging_breakdown ?? []).map(item => ({ ...item })))
    setQtyPerUnit(result?.goodpack_qty_per_unit_kg ?? null)
    setConfirmedItems(new Set())
    setConfirmedCompetitorItems(new Set())
    setFullCustomization(false)
    setHandlingPackerPerUnit(handlingPackerCategory?.goodpack_per_unit ?? null)
    setHandlingEnduserPerUnit(handlingEnduserCategory?.goodpack_per_unit ?? null)
    setGoodpackVolumeLiters(result?.goodpack_volume_liters ?? null)
    setGoodpackMaxPayloadKg(result?.goodpack_max_payload_kg ?? null)
    setGoodpackQtyPerTransport(result?.goodpack_qty_per_transport ?? null)
    setCompetitorVolumeLiters(result?.competitor_volume_liters ?? null)
    setCompetitorMaxPayloadKg(result?.competitor_max_payload_kg ?? null)
    setCompetitorQtyPerTransport(result?.competitor_qty_per_transport ?? null)
    onOverrideChange(null, null) // sinaliza pro pai limpar todas as correções confirmadas desta análise
  }

  useEffect(() => {
    if (!result || !chartRef.current || categories.length === 0) return

    if (chartInstanceRef.current) {
      chartInstanceRef.current.destroy()
    }

    const categoriesForChart = recalculated.totals.categoriesRecalced ?? categories
    const goodpackData = categoriesForChart.map(c => c.goodpack)
    const competitorData = categoriesForChart.map(c => c.competitor)

    const goodpackTotal = recalculated.totals.goodpackTotalPerMt
    const competitorTotal = recalculated.totals.competitorTotalPerMt ?? result.competitor_total_per_mt
    const totals = [goodpackTotal, competitorTotal]
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
        labels: [goodpackSku, competitorName],
        datasets: categories.map((c, i) => ({
          label: c.label,
          data: [goodpackData[i], competitorData[i]],
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
            suggestedMax: maxTotal ? maxTotal * 1.15 : undefined,
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
  }, [result, recalculated, categories, goodpackSku, competitorName])

  if (!result) return null

  const {
    customer_name,
    product_name,
    transport_type,
    simulated_metric_tonnes,
    lease_days,
    investment,
    assumptions = [],
  } = result

  const logistics = recalculated.logistics
  const statCards = logistics ? [
    { icon: Truck, label: 'Transports needed', gp: logistics.goodpack?.transports_needed, comp: logistics.competitor?.transports_needed },
    { icon: Package, label: 'Units needed', gp: logistics.goodpack?.units_needed, comp: logistics.competitor?.units_needed },
    { icon: Layers, label: 'Pallet places', gp: logistics.goodpack?.pallet_places, comp: logistics.competitor?.pallet_places },
    { icon: Boxes, label: 'Full stacks', gp: logistics.goodpack?.full_stacks, comp: logistics.competitor?.full_stacks },
  ] : []

  const isEdited = (hasEditableBreakdown && result.packaging_breakdown && (
    breakdown.some((item, i) => item.value !== result.packaging_breakdown[i]?.value)
    || qtyPerUnit !== result.goodpack_qty_per_unit_kg
  )) || (hasEditableCompetitorBreakdown && result.competitor_packaging_breakdown && (
    competitorBreakdown.some((item, i) => item.value !== result.competitor_packaging_breakdown[i]?.value)
  )) || (fullCustomization && (
    handlingPackerPerUnit !== (handlingPackerCategory?.goodpack_per_unit ?? null)
    || handlingEnduserPerUnit !== (handlingEnduserCategory?.goodpack_per_unit ?? null)
  )) || (
    goodpackVolumeLiters !== (result?.goodpack_volume_liters ?? null)
    || goodpackMaxPayloadKg !== (result?.goodpack_max_payload_kg ?? null)
    || goodpackQtyPerTransport !== (result?.goodpack_qty_per_transport ?? null)
    || competitorVolumeLiters !== (result?.competitor_volume_liters ?? null)
    || competitorMaxPayloadKg !== (result?.competitor_max_payload_kg ?? null)
    || competitorQtyPerTransport !== (result?.competitor_qty_per_transport ?? null)
  )

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 max-w-5xl">

      <div className="mb-4 pb-3 border-b border-slate-100 flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-800">{customer_name}</p>
          <p className="text-xs text-slate-400 mt-0.5">
            {product_name} · {simulated_metric_tonnes} MT · {goodpackSku} vs {competitorName}
            {transport_type && ` · ${transport_type}`}
            {lease_days != null && ` · ${lease_days} lease days`}
          </p>
        </div>
        {isEdited && (
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded-md hover:bg-slate-50 transition-colors"
          >
            <RotateCcw size={12} />
            Restaurar valores originais
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-5">

        <div className="flex flex-col gap-3">

          {(hasEditableBreakdown || hasEditableCompetitorBreakdown) && (() => {
            const labels = []
            breakdown.forEach(item => { if (!labels.includes(item.label)) labels.push(item.label) })
            competitorBreakdown.forEach(item => { if (!labels.includes(item.label)) labels.push(item.label) })

            return (
              <div className="bg-slate-50 rounded-lg p-3.5">
                <p className="text-xs font-medium text-slate-700">Packaging — {goodpackSku} vs {competitorName}</p>
                <p className="text-[11px] text-slate-400 mb-2">Editável — afeta o gráfico dos dois lados</p>
                <div className="grid grid-cols-[1fr_56px_56px] gap-x-1.5 gap-y-1 items-center text-[10px] text-slate-400 mb-1">
                  <span></span>
                  <span className="text-center">GP</span>
                  <span className="text-center">Conc.</span>
                </div>
                <div className="flex flex-col gap-1.5">
                  {labels.map((label, rowI) => {
                    const gpIdx = breakdown.findIndex(item => item.label === label)
                    const compIdx = competitorBreakdown.findIndex(item => item.label === label)

                    const gpMatched = gpIdx >= 0 ? matchAssumption(label + ' (Goodpack)', assumptions) ?? matchAssumption(label, assumptions) : null
                    const compMatched = compIdx >= 0 ? matchAssumption(label + ' (Concorrente)', assumptions) ?? matchAssumption(label, assumptions) : null
                    const gpPending = gpMatched?.confidence_level === 'validation_required' && !confirmedItems.has(gpIdx)
                    const compPending = compMatched?.confidence_level === 'validation_required' && !confirmedCompetitorItems.has(compIdx)
                    const gpConfirmed = confirmedItems.has(gpIdx)
                    const compConfirmed = confirmedCompetitorItems.has(compIdx)
                    const rowPending = gpPending || compPending

                    return (
                      <div
                        key={rowI}
                        className={
                          'grid grid-cols-[1fr_56px_56px] gap-x-1.5 items-center rounded-md px-1 py-1 ' +
                          (rowPending ? 'border border-amber-300 bg-amber-50' : '')
                        }
                      >
                        <label className="text-[11px] text-slate-600 flex items-center gap-1 truncate" title={label}>
                          {rowPending && <AlertTriangle size={10} className="text-amber-500 shrink-0" />}
                          {!rowPending && (gpConfirmed || compConfirmed) && <Check size={10} className="text-emerald-500 shrink-0" />}
                          {label}
                        </label>

                        {gpIdx >= 0 ? (
                          <input
                            type="number" step="0.01"
                            value={breakdown[gpIdx].value}
                            onChange={(e) => handleBreakdownChange(gpIdx, parseFloat(e.target.value) || 0)}
                            className={
                              'w-full text-xs border rounded px-1.5 py-1 focus:outline-none focus:ring-1 text-right ' +
                              (gpPending ? 'border-amber-300 focus:ring-amber-300' : 'border-blue-200 focus:ring-blue-300')
                            }
                          />
                        ) : <span className="text-center text-slate-300 text-xs">—</span>}

                        {compIdx >= 0 ? (
                          <input
                            type="number" step="0.01"
                            value={competitorBreakdown[compIdx].value}
                            onChange={(e) => handleCompetitorBreakdownChange(compIdx, parseFloat(e.target.value) || 0)}
                            className={
                              'w-full text-xs border rounded px-1.5 py-1 focus:outline-none focus:ring-1 text-right ' +
                              (compPending ? 'border-amber-300 focus:ring-amber-300' : 'border-blue-200 focus:ring-blue-300')
                            }
                          />
                        ) : <span className="text-center text-slate-300 text-xs">—</span>}
                      </div>
                    )
                  })}
                </div>

                {labels.some((label, rowI) => {
                  const gpIdx = breakdown.findIndex(item => item.label === label)
                  const compIdx = competitorBreakdown.findIndex(item => item.label === label)
                  const gpMatched = gpIdx >= 0 ? matchAssumption(label, assumptions) : null
                  const compMatched = compIdx >= 0 ? matchAssumption(label, assumptions) : null
                  return (gpMatched?.confidence_level === 'validation_required' && !confirmedItems.has(gpIdx))
                    || (compMatched?.confidence_level === 'validation_required' && !confirmedCompetitorItems.has(compIdx))
                }) && (
                  <button
                    onClick={() => {
                      setConfirmedItems(new Set(breakdown.map((_, i) => i)))
                      setConfirmedCompetitorItems(new Set(competitorBreakdown.map((_, i) => i)))
                    }}
                    className="text-[11px] text-amber-700 hover:underline mt-2"
                  >
                    Confirmar todos os valores acima
                  </button>
                )}
              </div>
            )
          })()}

          <div className="bg-slate-50 rounded-lg p-3.5">
            <p className="text-xs font-medium text-slate-700">Capacidade & quantidade por container</p>
            <p className="text-[11px] text-slate-400 mb-2">Editável — afeta logística e custo dos dois lados</p>
            <div className="grid grid-cols-[1fr_70px_70px] gap-x-1.5 gap-y-1 items-center text-[10px] text-slate-400 mb-1">
              <span></span>
              <span className="text-center">GP</span>
              <span className="text-center">Conc.</span>
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="grid grid-cols-[1fr_70px_70px] gap-x-1.5 items-center">
                <label className="text-[11px] text-slate-500">Volume (L)</label>
                <input
                  type="number" step="1"
                  value={goodpackVolumeLiters ?? ''}
                  onChange={(e) => handleGoodpackVolumeChange(parseFloat(e.target.value) || 0)}
                  className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                />
                <input
                  type="number" step="1"
                  value={competitorVolumeLiters ?? ''}
                  onChange={(e) => handleCompetitorVolumeChange(parseFloat(e.target.value) || 0)}
                  className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                />
              </div>
              <div className="grid grid-cols-[1fr_70px_70px] gap-x-1.5 items-center">
                <label className="text-[11px] text-slate-500">Peso nominal (kg)</label>
                <input
                  type="number" step="1"
                  value={goodpackMaxPayloadKg ?? ''}
                  onChange={(e) => handleGoodpackMaxPayloadChange(parseFloat(e.target.value) || 0)}
                  className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                />
                <input
                  type="number" step="1"
                  value={competitorMaxPayloadKg ?? ''}
                  onChange={(e) => handleCompetitorMaxPayloadChange(parseFloat(e.target.value) || 0)}
                  className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                />
              </div>
              <div className="grid grid-cols-[1fr_70px_70px] gap-x-1.5 items-center">
                <label className="text-[11px] text-slate-500">Qtd./container</label>
                <input
                  type="number" step="1"
                  value={goodpackQtyPerTransport ?? ''}
                  onChange={(e) => handleGoodpackQtyPerTransportChange(parseInt(e.target.value) || 0)}
                  className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                />
                <input
                  type="number" step="1"
                  value={competitorQtyPerTransport ?? ''}
                  onChange={(e) => handleCompetitorQtyPerTransportChange(parseInt(e.target.value) || 0)}
                  className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                />
              </div>
            </div>
          </div>

          <button
            onClick={() => setFullCustomization(v => !v)}
            className="flex items-center justify-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 px-2 py-2 rounded-md border border-slate-200 hover:bg-slate-50 transition-colors"
          >
            <SlidersHorizontal size={12} />
            {fullCustomization ? 'Voltar ao modo express' : 'Customização completa'}
          </button>

          {fullCustomization && (
            <div className="bg-slate-50 rounded-lg p-3.5 border border-slate-200">
              <p className="text-xs font-medium text-slate-700">Parâmetros avançados</p>
              <p className="text-[11px] text-slate-400 mb-2.5">Handling — {goodpackSku}</p>
              <div className="flex flex-col gap-2.5">
                {handlingPackerCategory && (
                  <div>
                    <label className="text-[11px] text-slate-500 block mb-1">Handling packer (por unidade)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={handlingPackerPerUnit ?? ''}
                      onChange={(e) => handleHandlingPackerChange(parseFloat(e.target.value) || 0)}
                      className="w-full text-sm border border-blue-200 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-300"
                    />
                  </div>
                )}
                {handlingEnduserCategory && (
                  <div>
                    <label className="text-[11px] text-slate-500 block mb-1">Handling enduser (por unidade)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={handlingEnduserPerUnit ?? ''}
                      onChange={(e) => handleHandlingEnduserChange(parseFloat(e.target.value) || 0)}
                      className="w-full text-sm border border-blue-200 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-300"
                    />
                  </div>
                )}
              </div>
              <p className="text-[10px] text-slate-400 mt-2">
                Tipo de transporte ainda não é editável aqui — depende de dado que falta expor no resultado do agente.
              </p>
            </div>
          )}

          {hasEditableQty && (
            <div className="bg-slate-50 rounded-lg p-3.5">
              <p className="text-xs font-medium text-slate-700">Quantidade envasada</p>
              <p className="text-[11px] text-slate-400 mb-2.5">Editável — recalcula logística</p>
              <label className="text-[11px] text-slate-500 block mb-1">Kg por {goodpackSku}</label>
              <input
                type="number"
                step="10"
                value={qtyPerUnit}
                onChange={(e) => handleQtyPerUnitChange(parseFloat(e.target.value) || 0)}
                className="w-full text-sm border border-blue-200 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-300"
              />
            </div>
          )}

          <div className="bg-slate-50 rounded-lg p-3.5">
            <p className="text-xs font-medium text-slate-700 mb-2.5">Demais categorias</p>
            <div className="flex flex-col gap-1.5 text-[11px]">
              {categories.filter(c => c.label !== 'Packaging').map((c, i) => (
                <div key={i} className="flex justify-between">
                  <span className="text-slate-500">{c.label} ({goodpackSku})</span>
                  <span className="text-slate-700">{formatCurrency(c.goodpack, currency)}/MT</span>
                </div>
              ))}
              <div className="border-t border-slate-200 my-1" />
              <div className="flex justify-between">
                <span className="text-slate-500">{competitorName} — total</span>
                <span className="text-slate-700">{formatCurrency(recalculated.totals.competitorTotalPerMt ?? result.competitor_total_per_mt, currency)}/MT</span>
              </div>
            </div>
          </div>

        </div>

        <div className="flex flex-col">

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
              aria-label={`Gráfico de barras empilhadas comparando custo total por MT entre ${goodpackSku} e ${competitorName}, por categoria`}
            />
          </div>

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

          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-xs text-slate-400">Saving total</p>
              <p className="text-lg font-medium text-emerald-600">{formatCurrency(recalculated.totals.totalSaving, currency)}</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-xs text-slate-400">Redução</p>
              <p className="text-lg font-medium text-slate-800">{recalculated.totals.savingPercentage.toFixed(1)}%</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-xs text-slate-400">Premissas</p>
              <p className="text-lg font-medium text-slate-800">{assumptions.length}</p>
            </div>
          </div>

          {investment && (investment.goodpack_investment_required != null || investment.competitor_investment_required != null) && (
            <div className="mb-4">
              <p className="text-xs text-slate-400 mb-2 flex items-center gap-1.5">
                <TrendingUp size={13} />
                Investimento e payback
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 font-medium mb-1">{goodpackSku}</p>
                  <p className="text-xs text-slate-400">Investimento</p>
                  <p className="text-sm font-medium text-slate-800">{formatCurrency(investment.goodpack_investment_required, currency)}</p>
                  {investment.goodpack_payback_cycles != null && (
                    <p className="text-xs text-slate-500 mt-1">
                      Payback: <span className="font-medium text-slate-700">{investment.goodpack_payback_cycles.toFixed(2)} ciclos</span>
                    </p>
                  )}
                </div>
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 font-medium mb-1">{competitorName}</p>
                  <p className="text-xs text-slate-400">Investimento</p>
                  <p className="text-sm font-medium text-slate-800">{formatCurrency(investment.competitor_investment_required, currency)}</p>
                  {investment.competitor_payback_cycles != null && (
                    <p className="text-xs text-slate-500 mt-1">
                      Payback: <span className="font-medium text-slate-700">{investment.competitor_payback_cycles.toFixed(2)} ciclos</span>
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {assumptions.length > 0 && (
            <div className="mb-4">
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

          {sessionId && (
            <div className="relative">
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
              {isEdited && (
                <p className="text-[11px] text-slate-400 mt-1.5">
                  O PowerPoint exporta os valores originais do agente, não os valores simulados aqui.
                </p>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
