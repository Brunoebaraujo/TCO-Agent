import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, ChevronDown, Loader2, Truck, Package, Layers, Boxes, TrendingUp, RotateCcw, AlertTriangle, Check, Pencil } from 'lucide-react'
import ConfidenceBadge from '../ui/ConfidenceBadge'
import {
  recalcPackagingByPrice, recalcCategoryByUnitPrice, recalcCategoriesByQty,
  recalcLogistics, recalcTotals, matchAssumption,
  computeHandlingPacker, computeHandlingEnduser, getOverrideValue,
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
  const [competitorQtyPerUnit, setCompetitorQtyPerUnit] = useState(null)
  const [confirmedItems, setConfirmedItems] = useState(() => new Set())
  const [confirmedCompetitorItems, setConfirmedCompetitorItems] = useState(() => new Set())

  // Premissas editáveis direto na lista (ver assumptions[].override_key) —
  // substitui o antigo botão "Customização completa": Handling agora edita
  // por parâmetro individual (recalcula a soma na hora, mesma fórmula do
  // backend portada pra JS), e densidade/tipo de transporte/frete ficam
  // confirmáveis ali também.
  const [handlingBenchmarks, setHandlingBenchmarks] = useState({})
  const [confirmedAssumptionKeys, setConfirmedAssumptionKeys] = useState(() => new Set())
  const [density, setDensity] = useState(null)
  const [transportType, setTransportType] = useState(null)
  const [transportCostPerContainer, setTransportCostPerContainer] = useState(null)

  // Capacidade & quantidade por container — só os 2 parâmetros que de fato
  // variam por negócio: peso envasado (kg real por unidade) e qtd/container.
  // Volume e peso nominal são specs de catálogo fixas, não editáveis aqui.
  const [goodpackQtyPerTransport, setGoodpackQtyPerTransport] = useState(null)
  const [competitorQtyPerTransport, setCompetitorQtyPerTransport] = useState(null)
  const [roadWeightLimit, setRoadWeightLimit] = useState(23000)

  // Quando um TCO_RESULT NOVO chega (o agente recalculou), reaplica por cima
  // dele qualquer valor que o vendedor já tinha confirmado nesta sessão —
  // em vez de resetar tudo pro default do resultado novo e perder a edição.
  useEffect(() => {
    const ov = (key, fallback) => getOverrideValue(overrides, key, fallback)

    setBreakdown((result?.packaging_breakdown ?? []).map(item => ({
      ...item, value: ov(`breakdown:${item.label}`, item.value),
    })))
    setCompetitorBreakdown((result?.competitor_packaging_breakdown ?? []).map(item => ({
      ...item, value: ov(`compBreakdown:${item.label}`, item.value),
    })))
    setQtyPerUnit(ov('qtyPerUnit', result?.goodpack_qty_per_unit_kg ?? null))
    setCompetitorQtyPerUnit(ov('competitorQtyPerUnit', result?.competitor_qty_per_unit_kg ?? null))
    setConfirmedItems(new Set())
    setConfirmedCompetitorItems(new Set())

    // Handling: parte do dict que o agente devolveu, reaplica por cima
    // qualquer parâmetro individual já validado (hb:<param_key>).
    const baseHb = result?.handling_benchmarks ?? {}
    const mergedHb = {}
    for (const key of Object.keys(baseHb)) {
      mergedHb[key] = ov(`hb:${key}`, baseHb[key])
    }
    setHandlingBenchmarks(mergedHb)
    setConfirmedAssumptionKeys(new Set())

    setDensity(ov('density', result?.product_density ?? null))
    setTransportType(ov('transport_type', result?.transport_type ?? null))
    setTransportCostPerContainer(ov('transport_cost_per_container', result?.goodpack_transport_cost_per_container ?? null))

    setGoodpackQtyPerTransport(ov('goodpackQtyPerTransport', result?.goodpack_qty_per_transport ?? null))
    setCompetitorQtyPerTransport(ov('competitorQtyPerTransport', result?.competitor_qty_per_transport ?? null))
    setRoadWeightLimit(ov('roadWeightLimit', 23000))
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
  const hasEditableCompetitorQty = competitorQtyPerUnit != null

  const handlingPackerCategory = categories.find(c => c.label === 'Handling packer')
  const handlingEnduserCategory = categories.find(c => c.label === 'Handling enduser')

  const recalculated = useMemo(() => {
    // --- Lado Goodpack ---
    const origGpQtyKg = result?.goodpack_qty_per_unit_kg ?? null
    const effectiveGpQty = hasEditableQty ? qtyPerUnit : origGpQtyKg
    const gpQtyChanged = hasEditableQty && effectiveGpQty !== origGpQtyKg
    const gpQtyPerTransport = goodpackQtyPerTransport ?? result?.goodpack_qty_per_transport ?? null
    const gpStackFullWarehouse = result?.goodpack_stack_full_warehouse ?? null
    const effectiveTransportCost = transportCostPerContainer ?? result?.goodpack_transport_cost_per_container ?? null
    const gpQtyRatio = gpQtyChanged && origGpQtyKg ? origGpQtyKg / effectiveGpQty : 1

    const recalcedByQtyGoodpack = gpQtyChanged && effectiveGpQty
      ? recalcCategoriesByQty(categories, 'goodpack', effectiveGpQty, origGpQtyKg, gpQtyPerTransport, effectiveTransportCost,
          breakdown.reduce((s, i) => s + (Number(i.value) || 0), 0) || null)
      : null

    // --- Lado Concorrente: mesmo padrão do Goodpack — campo direto de
    // peso envasado, sem derivar de volume/peso nominal (removidos do painel).
    const origCompQtyKg = result?.competitor_qty_per_unit_kg ?? null
    const effectiveCompQty = hasEditableCompetitorQty ? competitorQtyPerUnit : origCompQtyKg
    const compQtyChanged = hasEditableCompetitorQty && effectiveCompQty !== origCompQtyKg
    const compQtyPerTransport = competitorQtyPerTransport ?? result?.competitor_qty_per_transport ?? null
    const compStackFullWarehouse = result?.competitor_stack_full_warehouse ?? null

    const recalcedByQtyCompetitor = compQtyChanged && effectiveCompQty
      ? recalcCategoriesByQty(categories, 'competitor', effectiveCompQty, origCompQtyKg, compQtyPerTransport, effectiveTransportCost,
          competitorBreakdown.reduce((s, i) => s + (Number(i.value) || 0), 0) || null)
      : null

    // Cada categoria com preço editável é recalculada pelo preço e depois
    // ajustada pela mesma proporção de qty (se a qty também mudou).
    const categoryOverrides = {}

    if (hasEditableBreakdown || hasEditableCompetitorBreakdown) {
      categoryOverrides.Packaging = categoryOverrides.Packaging || {}
      if (hasEditableBreakdown) {
        const newPerUnit = breakdown.reduce((s, i) => s + (Number(i.value) || 0), 0)
        // Fórmula direta: evita ampliar erros do perMt original gerado pelo LLM
        categoryOverrides.Packaging.perMt = effectiveGpQty > 0
          ? (newPerUnit * 1000) / effectiveGpQty
          : recalcPackagingByPrice(breakdown, originalPackagingPerUnit, originalPackagingPerMt).perMt
      }
      if (hasEditableCompetitorBreakdown) {
        const newCompPerUnit = competitorBreakdown.reduce((s, i) => s + (Number(i.value) || 0), 0)
        categoryOverrides.Packaging.competitorPerMt = effectiveCompQty > 0
          ? (newCompPerUnit * 1000) / effectiveCompQty
          : recalcPackagingByPrice(competitorBreakdown, originalCompetitorPackagingPerUnit, originalCompetitorPackagingPerMt).perMt
      }
    }

    // Transport: se o frete por container foi editado, recalcula igual o
    // backend faz (custo por container ÷ qty real que cabe em MT).
    if (transportCostPerContainer != null && effectiveGpQty) {
      const liquidMtPerContainerGp = (effectiveGpQty / 1000) * gpQtyPerTransport
      if (liquidMtPerContainerGp) {
        categoryOverrides.Transport = categoryOverrides.Transport || {}
        categoryOverrides.Transport.perMt = transportCostPerContainer / liquidMtPerContainerGp
      }
    }
    if (transportCostPerContainer != null && effectiveCompQty && compQtyPerTransport) {
      const liquidMtPerContainerComp = (effectiveCompQty / 1000) * compQtyPerTransport
      if (liquidMtPerContainerComp) {
        categoryOverrides.Transport = categoryOverrides.Transport || {}
        categoryOverrides.Transport.competitorPerMt = transportCostPerContainer / liquidMtPerContainerComp
      }
    }

    // Handling: sempre computado ao vivo a partir do dict de parâmetros —
    // sem isso ser "editado" tecnicamente, o resultado bate com o que o
    // agente já tinha calculado (mesma fórmula, portada fielmente pro JS).
    if (Object.keys(handlingBenchmarks).length > 0 && handlingPackerCategory) {
      const hpPerUnit = computeHandlingPacker(handlingBenchmarks, gpStackFullWarehouse)
      const hp = recalcCategoryByUnitPrice(hpPerUnit, handlingPackerCategory.goodpack_per_unit ?? 0, handlingPackerCategory.goodpack ?? 0)
      categoryOverrides['Handling packer'] = { perMt: hp.perMt * gpQtyRatio }
    }
    if (Object.keys(handlingBenchmarks).length > 0 && handlingEnduserCategory) {
      const hePerUnit = computeHandlingEnduser(handlingBenchmarks, gpStackFullWarehouse)
      const he = recalcCategoryByUnitPrice(hePerUnit, handlingEnduserCategory.goodpack_per_unit ?? 0, handlingEnduserCategory.goodpack ?? 0)
      categoryOverrides['Handling enduser'] = { perMt: he.perMt * gpQtyRatio }
    }

    const totals = recalcTotals(result ?? {}, categoryOverrides, recalcedByQtyGoodpack, recalcedByQtyCompetitor)

    // Logística — recalcula os dois lados quando capacidade/qty mudou
    let logistics = result?.logistics
    const newGpLogistics = (effectiveGpQty && gpQtyPerTransport && gpStackFullWarehouse)
      ? recalcLogistics(result.simulated_metric_tonnes, effectiveGpQty, gpQtyPerTransport, gpStackFullWarehouse)
      : null
    const newCompLogistics = (effectiveCompQty && compQtyPerTransport)
      ? recalcLogistics(result.simulated_metric_tonnes, effectiveCompQty, compQtyPerTransport, compStackFullWarehouse)
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
    handlingBenchmarks, handlingPackerCategory, handlingEnduserCategory, transportCostPerContainer,
    goodpackQtyPerTransport, competitorQtyPerUnit, hasEditableCompetitorQty, competitorQtyPerTransport,
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
    onOverrideChange(`breakdown:${breakdown[index]?.label}`, newValue, `${breakdown[index]?.label} (Goodpack)`)
  }

  function handleConfirmItem(index) {
    setConfirmedItems(prev => new Set(prev).add(index))
  }

  function handleCompetitorBreakdownChange(index, newValue) {
    setCompetitorBreakdown(prev => prev.map((item, i) => i === index ? { ...item, value: newValue } : item))
    onOverrideChange(`compBreakdown:${competitorBreakdown[index]?.label}`, newValue, `${competitorBreakdown[index]?.label} (Concorrente)`)
  }

  function handleConfirmCompetitorItem(index) {
    setConfirmedCompetitorItems(prev => new Set(prev).add(index))
  }

  function handleQtyPerUnitChange(newValue) {
    setQtyPerUnit(newValue)
    onOverrideChange('qtyPerUnit', newValue, 'Peso envasado Goodpack (kg/unidade)')
  }

  function handleCompetitorQtyPerUnitChange(newValue) {
    setCompetitorQtyPerUnit(newValue)
    onOverrideChange('competitorQtyPerUnit', newValue, 'Peso envasado concorrente (kg/unidade)')
  }

  function handleGoodpackQtyPerTransportChange(newValue) {
    setGoodpackQtyPerTransport(newValue)
    onOverrideChange('goodpackQtyPerTransport', newValue, 'Quantidade Goodpack por container')
  }
  function handleCompetitorQtyPerTransportChange(newValue) {
    setCompetitorQtyPerTransport(newValue)
    onOverrideChange('competitorQtyPerTransport', newValue, 'Quantidade concorrente por container')
  }
  function handleRoadWeightLimitChange(newValue) {
    setRoadWeightLimit(newValue)
    onOverrideChange('roadWeightLimit', newValue, 'Limite de rodagem (kg)')
  }

  // --- Validação inline na lista de premissas (assumptions[].override_key) ---
  function handleHandlingParamChange(paramKey, newValue) {
    setHandlingBenchmarks(prev => ({ ...prev, [paramKey]: newValue }))
  }
  function handleDensityChange(newValue) {
    setDensity(newValue)
  }
  function handleTransportTypeChange(newValue) {
    setTransportType(newValue)
  }
  function handleTransportCostChange(newValue) {
    setTransportCostPerContainer(newValue)
  }

  function handleValidateAssumption(assumptionKey, overrideKey, value, label) {
    setConfirmedAssumptionKeys(prev => new Set(prev).add(assumptionKey))
    onOverrideChange(overrideKey, value, label)
  }

  function handleReset() {
    setBreakdown((result?.packaging_breakdown ?? []).map(item => ({ ...item })))
    setCompetitorBreakdown((result?.competitor_packaging_breakdown ?? []).map(item => ({ ...item })))
    setQtyPerUnit(result?.goodpack_qty_per_unit_kg ?? null)
    setCompetitorQtyPerUnit(result?.competitor_qty_per_unit_kg ?? null)
    setConfirmedItems(new Set())
    setConfirmedCompetitorItems(new Set())
    setConfirmedAssumptionKeys(new Set())
    setHandlingBenchmarks(result?.handling_benchmarks ?? {})
    setDensity(result?.product_density ?? null)
    setTransportType(result?.transport_type ?? null)
    setTransportCostPerContainer(result?.goodpack_transport_cost_per_container ?? null)
    setGoodpackQtyPerTransport(result?.goodpack_qty_per_transport ?? null)
    setCompetitorQtyPerTransport(result?.competitor_qty_per_transport ?? null)
    setRoadWeightLimit(23000)
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
  )) || (
    JSON.stringify(handlingBenchmarks) !== JSON.stringify(result?.handling_benchmarks ?? {})
    || density !== (result?.product_density ?? null)
    || transportType !== (result?.transport_type ?? null)
    || transportCostPerContainer !== (result?.goodpack_transport_cost_per_container ?? null)
    || competitorQtyPerUnit !== (result?.competitor_qty_per_unit_kg ?? null)
    || goodpackQtyPerTransport !== (result?.goodpack_qty_per_transport ?? null)
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

            {/* Limite de rodagem */}
            <div className="flex items-center justify-between mb-2.5">
              <label className="text-[11px] text-slate-500">Limite rodagem (kg)</label>
              <input
                type="number" step="100"
                value={roadWeightLimit}
                onChange={(e) => handleRoadWeightLimitChange(parseInt(e.target.value) || 23000)}
                className="w-[70px] text-xs border border-amber-200 bg-amber-50 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-amber-300 text-right"
              />
            </div>

            <div className="grid grid-cols-[1fr_70px_70px] gap-x-1.5 gap-y-1 items-center text-[10px] text-slate-400 mb-1">
              <span></span>
              <span className="text-center">GP</span>
              <span className="text-center">Conc.</span>
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="grid grid-cols-[1fr_70px_70px] gap-x-1.5 items-center">
                <label className="text-[11px] text-slate-500">Peso envasado (kg)</label>
                <input
                  type="number" step="1"
                  value={qtyPerUnit ?? ''}
                  onChange={(e) => handleQtyPerUnitChange(parseFloat(e.target.value) || 0)}
                  className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                />
                <input
                  type="number" step="1"
                  value={competitorQtyPerUnit ?? ''}
                  onChange={(e) => handleCompetitorQtyPerUnitChange(parseFloat(e.target.value) || 0)}
                  className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                />
              </div>
              <div className="grid grid-cols-[1fr_70px_70px] gap-x-1.5 items-center">
                <label className="text-[11px] text-slate-500">Qtd./container</label>
                {(() => {
                  const gpTare = result?.goodpack_tare_weight_kg ?? null
                  const compTare = result?.competitor_tare_weight_kg ?? null
                  const gpSuggested = (gpTare != null && qtyPerUnit)
                    ? Math.floor(roadWeightLimit / (qtyPerUnit + gpTare))
                    : null
                  const compSuggested = (compTare != null && competitorQtyPerUnit)
                    ? Math.floor(roadWeightLimit / (competitorQtyPerUnit + compTare))
                    : null
                  const gpTotalWeight = (qtyPerUnit != null && gpTare != null && goodpackQtyPerTransport != null)
                    ? (qtyPerUnit + gpTare) * goodpackQtyPerTransport
                    : null
                  const compTotalWeight = (competitorQtyPerUnit != null && compTare != null && competitorQtyPerTransport != null)
                    ? (competitorQtyPerUnit + compTare) * competitorQtyPerTransport
                    : null
                  const gpOverLimit = gpTotalWeight != null && gpTotalWeight > roadWeightLimit
                  const compOverLimit = compTotalWeight != null && compTotalWeight > roadWeightLimit

                  return (
                    <>
                      <input
                        type="number" step="1"
                        value={goodpackQtyPerTransport ?? ''}
                        placeholder={gpSuggested != null ? String(gpSuggested) : ''}
                        onChange={(e) => handleGoodpackQtyPerTransportChange(parseInt(e.target.value) || 0)}
                        className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                      />
                      <input
                        type="number" step="1"
                        value={competitorQtyPerTransport ?? ''}
                        placeholder={compSuggested != null ? String(compSuggested) : ''}
                        onChange={(e) => handleCompetitorQtyPerTransportChange(parseInt(e.target.value) || 0)}
                        className="w-full text-xs border border-blue-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300 text-right"
                      />
                      {/* Peso total por container */}
                      <label className="text-[11px] text-slate-400 col-start-1">Peso total/container (kg)</label>
                      <span className={`text-[11px] text-right font-medium ${gpOverLimit ? 'text-red-500' : 'text-slate-600'}`}>
                        {gpTotalWeight != null ? Math.round(gpTotalWeight).toLocaleString('en-US') : '—'}
                      </span>
                      <span className={`text-[11px] text-right font-medium ${compOverLimit ? 'text-red-500' : 'text-slate-600'}`}>
                        {compTotalWeight != null ? Math.round(compTotalWeight).toLocaleString('en-US') : '—'}
                      </span>
                      {/* Avisos de sobrepeso */}
                      {(gpOverLimit || compOverLimit) && (
                        <p className="col-span-3 text-[10px] text-red-500 mt-0.5">
                          ⚠ Peso acima do limite de rodagem ({roadWeightLimit.toLocaleString('en-US')} kg)
                        </p>
                      )}
                    </>
                  )
                })()}
              </div>
            </div>
            <p className="text-[10px] text-slate-400 mt-2">
              Volume e peso nominal não aparecem aqui — são specs de catálogo fixas, não variam por negócio.
            </p>
          </div>


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

          {assumptions.length > 0 && (() => {
            const getAccessor = (overrideKey) => {
              if (!overrideKey) return null
              if (overrideKey.startsWith('hb:')) {
                const paramKey = overrideKey.slice(3)
                return { value: handlingBenchmarks[paramKey], setValue: (v) => handleHandlingParamChange(paramKey, v) }
              }
              if (overrideKey === 'density') return { value: density, setValue: handleDensityChange }
              if (overrideKey === 'transport_type') return { value: transportType, setValue: handleTransportTypeChange }
              if (overrideKey === 'transport_cost_per_container') return { value: transportCostPerContainer, setValue: handleTransportCostChange }
              return null
            }

            return (
              <div className="mb-4">
                <p className="text-xs text-slate-400 mb-2">Premissas usadas neste cálculo</p>
                <div className="space-y-2">
                  {assumptions.map((a, i) => {
                    const accessor = getAccessor(a.override_key)
                    const isConfirmed = confirmedAssumptionKeys.has(i)
                    const showInput = accessor && !isConfirmed

                    return (
                      <div key={i} className={'rounded-lg px-3 py-2 ' + (isConfirmed ? 'bg-emerald-50' : 'bg-slate-50')}>
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-xs text-slate-700 leading-relaxed flex-1">{a.label}</p>
                          <div className="flex-shrink-0">
                            <ConfidenceBadge level={isConfirmed ? 'verified' : a.confidence_level} />
                          </div>
                        </div>
                        {a.source && (
                          <p className="text-[11px] text-slate-400 mt-1">Fonte: {a.source}</p>
                        )}
                        {showInput && (
                          <div className="flex gap-1.5 mt-2">
                            <input
                              type={a.value_type === 'text' ? 'text' : 'number'}
                              step="0.01"
                              value={accessor.value ?? ''}
                              onChange={(e) => accessor.setValue(
                                a.value_type === 'text' ? e.target.value : (parseFloat(e.target.value) || 0)
                              )}
                              className="flex-1 text-xs border border-blue-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300"
                            />
                            <button
                              onClick={() => handleValidateAssumption(i, a.override_key, accessor.value, a.label)}
                              className="flex items-center gap-1 text-[11px] px-2 rounded-md border border-blue-200 text-blue-700 hover:bg-blue-50 transition-colors whitespace-nowrap"
                            >
                              <Pencil size={10} /> Validar
                            </button>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })()}

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
