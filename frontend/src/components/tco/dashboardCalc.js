/**
 * Lógica de recálculo do dashboard editável de TCO.
 *
 * Escopo editável confirmado (18/06/2026):
 * - Preços do breakdown Goodpack (unit cost + acessórios) → afeta Packaging $/MT
 * - Quantidade envasada por unidade (kg) → afeta TODAS as categorias $/MT
 *
 * Quando qty_per_unit muda, todas as categorias mudam:
 *   Packaging / Handling / Empty container: per_unit_original ÷ (nova_qty / 1000)
 *   Transport: custo_por_container ÷ (nova_qty × qty_por_container / 1000)
 *
 * Quando só os preços do breakdown mudam (sem alterar qty):
 *   Packaging $/MT: (nova_soma_breakdown / soma_original) × packaging_perMt_original
 *   Demais categorias: inalteradas
 *
 * ATENÇÃO: qualquer mudança nas fórmulas de prompts.py precisa ser
 * replicada manualmente aqui — não há sincronização automática.
 */

/**
 * Recalcula uma categoria a partir de um novo valor por unidade, escalando
 * o $/MT original pela mesma proporção (delta de preço escala o $/MT
 * original) para não divergir dos cálculos do agente por diferenças de
 * arredondamento. Usado tanto para Packaging (breakdown somado) quanto
 * para Handling packer/enduser (valor único editável no modo Customização
 * completa).
 *
 * @param {number} newPerUnit
 * @param {number} originalPerUnit
 * @param {number} originalPerMt
 * @returns {{ perUnit: number, perMt: number }}
 */
export function recalcCategoryByUnitPrice(newPerUnit, originalPerUnit, originalPerMt) {
  const scaleFactor = originalPerUnit > 0 ? newPerUnit / originalPerUnit : 1
  return { perUnit: newPerUnit, perMt: originalPerMt * scaleFactor }
}

/**
 * Recalcula Packaging a partir do breakdown editado (soma os itens e
 * delega para recalcCategoryByUnitPrice).
 *
 * @param {Array<{label, value}>} breakdown - itens editados
 * @param {number} originalPerUnit - soma original do breakdown (goodpack_per_unit de Packaging)
 * @param {number} originalPerMt  - $/MT original de Packaging
 * @returns {{ perUnit: number, perMt: number }}
 */
export function recalcPackagingByPrice(breakdown, originalPerUnit, originalPerMt) {
  const newPerUnit = breakdown.reduce((sum, item) => sum + (Number(item.value) || 0), 0)
  return recalcCategoryByUnitPrice(newPerUnit, originalPerUnit, originalPerMt)
}

/**
 * Encontra a premissa (assumptions) correspondente a um item do
 * packaging_breakdown, por correspondência de texto no label (ex: item
 * "Aseptic Bag" casa com a premissa "Acessório Aseptic Bag (Goodpack)").
 * Usado para decidir se um item de Packaging deve aparecer como pendente
 * de confirmação (confidence_level "validation_required") no dashboard.
 *
 * @param {string} itemLabel
 * @param {Array<{label, confidence_level, source}>} assumptions
 * @returns {{label, confidence_level, source}|null}
 */
export function matchAssumption(itemLabel, assumptions = []) {
  if (!itemLabel) return null
  const needle = itemLabel.toLowerCase()
  return assumptions.find(a => (a.label || '').toLowerCase().includes(needle)) || null
}

/**
 * Recalcula o $/MT de TODAS as categorias Goodpack quando qty_per_unit muda.
 * Packaging, Handling e Empty container usam per_unit ÷ (nova_qty / 1000).
 * Transport usa custo fixo por container ÷ produto líquido por container.
 *
 * @param {Array} categories - categories do TCO_RESULT original
 * @param {number} newQtyKg
 * @param {number} origQtyKg  - quantidade original usada pelo agente (goodpack_qty_per_unit_kg)
 * @param {number} qtyPerTransport
 * @param {number} transportCostPerContainer
 * @returns {Object} mapa label → { perMt }
 */
/**
 * Carga real por unidade (kg) = MÍNIMO entre peso nominal e densidade×volume.
 * Mesma lógica do backend (app/calculator/engine.py) — produto de baixa
 * densidade enche o volume antes de bater no peso nominal.
 */
export function computeQtyRealPerUnitKg(maxPayloadKg, densityKgPerLiter, volumeLiters) {
  const candidates = []
  if (maxPayloadKg != null) candidates.push(Number(maxPayloadKg))
  if (densityKgPerLiter != null && volumeLiters != null) candidates.push(Number(densityKgPerLiter) * Number(volumeLiters))
  return candidates.length ? Math.min(...candidates) : null
}

/**
 * Recalcula $/MT de todas as categorias de UM lado (goodpack ou competitor)
 * quando a qty real por unidade daquele lado muda (por edição direta de
 * "Quantidade envasada", ou por edição de Volume/Peso nominal que altera a
 * qty real calculada).
 *
 * @param {Array} categories
 * @param {'goodpack'|'competitor'} side
 * @param {number} newQtyKg
 * @param {number} origQtyKg
 * @param {number} qtyPerTransport
 * @param {number} transportCostPerContainer
 */
export function recalcCategoriesByQty(categories, side, newQtyKg, origQtyKg, qtyPerTransport, transportCostPerContainer) {
  const ratio = (origQtyKg && newQtyKg) ? origQtyKg / newQtyKg : 1
  const result = {}

  for (const cat of categories) {
    const original = cat[side]
    if (cat.label === 'Transport') {
      if (transportCostPerContainer && qtyPerTransport && newQtyKg) {
        const liquidMtPerContainer = (newQtyKg / 1000) * qtyPerTransport
        result[cat.label] = { perMt: transportCostPerContainer / liquidMtPerContainer }
      } else {
        result[cat.label] = { perMt: original * ratio }
      }
    } else {
      result[cat.label] = { perMt: original * ratio }
    }
  }

  return result
}

/**
 * Recalcula estatísticas logísticas de um lado (goodpack ou competitor) —
 * função genérica, mesma fórmula para os dois.
 *
 * @param {number} simulatedMt
 * @param {number} qtyPerUnitKg
 * @param {number} qtyPerTransport
 * @param {number} stackFullWarehouse
 */
export function recalcLogistics(simulatedMt, qtyPerUnitKg, qtyPerTransport, stackFullWarehouse) {
  if (!qtyPerUnitKg || qtyPerUnitKg <= 0) {
    return { unitsNeeded: null, transportsNeeded: null, palletPlaces: null, fullStacks: null }
  }
  const unitsNeeded = Math.ceil((simulatedMt * 1000) / qtyPerUnitKg)
  const transportsNeeded = qtyPerTransport > 0 ? Math.ceil(unitsNeeded / qtyPerTransport) : null
  const fullStacks = stackFullWarehouse > 0 ? Math.ceil(unitsNeeded / stackFullWarehouse) : null
  return { unitsNeeded, transportsNeeded, palletPlaces: unitsNeeded, fullStacks }
}

/**
 * Combina os custos recalculados (categorias com override de preço +
 * demais por qty, dos dois lados) e calcula os totais finais.
 *
 * @param {object} result - TCO_RESULT original
 * @param {Object} categoryOverrides - mapa label → { perMt, competitorPerMt } para categorias com preço editado
 *   (aceita também o formato antigo (number) para manter compatibilidade com chamada passando só Packaging)
 * @param {Object|null} recalcedByQtyGoodpack - mapa de categorias recalculadas por qty, lado Goodpack
 * @param {Object|null} recalcedByQtyCompetitor - mesmo, lado concorrente
 * @returns {{ goodpackTotalPerMt, competitorTotalPerMt, totalSaving, savingPercentage, categoriesRecalced }}
 */
export function recalcTotals(result, categoryOverrides, recalcedByQtyGoodpack, recalcedByQtyCompetitor) {
  const categories = result.categories || []

  // Compatibilidade: chamadas antigas passavam newPackagingPerMt (number) direto.
  const overrides = typeof categoryOverrides === 'number'
    ? { Packaging: { perMt: categoryOverrides } }
    : (categoryOverrides || {})

  const categoriesRecalced = categories.map(cat => {
    const override = overrides[cat.label]
    const rcGp = recalcedByQtyGoodpack?.[cat.label]
    const rcComp = recalcedByQtyCompetitor?.[cat.label]
    return {
      ...cat,
      goodpack: override?.perMt ?? rcGp?.perMt ?? cat.goodpack,
      competitor: override?.competitorPerMt ?? rcComp?.perMt ?? cat.competitor,
    }
  })

  const goodpackTotalPerMt = categoriesRecalced.reduce(
    (sum, c) => sum + (Number(c.goodpack) || 0), 0
  )
  const hasCompetitorOverride = Object.values(overrides).some(o => o?.competitorPerMt != null) || !!recalcedByQtyCompetitor
  const competitorTotalPerMt = hasCompetitorOverride
    ? categoriesRecalced.reduce((sum, c) => sum + (Number(c.competitor) || 0), 0)
    : (result.competitor_total_per_mt || 0)
  const simulatedMt = result.simulated_metric_tonnes || 0
  const savingPerMt = competitorTotalPerMt - goodpackTotalPerMt
  const totalSaving = savingPerMt * simulatedMt
  const savingPercentage = competitorTotalPerMt > 0 ? (savingPerMt / competitorTotalPerMt) * 100 : 0

  return { goodpackTotalPerMt, competitorTotalPerMt, totalSaving, savingPercentage, categoriesRecalced }
}

const OVERRIDE_LABELS = {
  qtyPerUnit: 'Quantidade envasada Goodpack (kg/unidade)',
  handlingPackerPerUnit: 'Handling packer Goodpack (por unidade)',
  handlingEnduserPerUnit: 'Handling enduser Goodpack (por unidade)',
  goodpackVolumeLiters: 'Volume Goodpack (L)',
  goodpackMaxPayloadKg: 'Peso nominal Goodpack (kg)',
  goodpackQtyPerTransport: 'Quantidade Goodpack por container',
  competitorVolumeLiters: 'Volume concorrente (L)',
  competitorMaxPayloadKg: 'Peso nominal concorrente (kg)',
  competitorQtyPerTransport: 'Quantidade concorrente por container',
}

/**
 * Formata o mapa de overrides confirmados pelo vendedor (editados no
 * dashboard) num bloco de texto que vai colado na próxima mensagem enviada
 * ao agente — ver seção CONFIRMED_OVERRIDES do system prompt. Sem isso, uma
 * correção feita no dashboard se perderia na próxima vez que o agente
 * chamasse calculate_tco (a tool não tem memória própria).
 *
 * @param {Object} overrides - mapa { key: value }
 * @returns {string} bloco formatado, ou string vazia se não houver overrides
 */
export function formatOverridesBlock(overrides) {
  const entries = Object.entries(overrides || {}).filter(([, v]) => v != null)
  if (entries.length === 0) return ''

  const lines = entries.map(([key, value]) => {
    if (key.startsWith('breakdown:')) return `- Acessório/Item "${key.slice(10)}" (Goodpack): ${value}`
    if (key.startsWith('compBreakdown:')) return `- Acessório/Item "${key.slice(14)}" (Concorrente): ${value}`
    return `- ${OVERRIDE_LABELS[key] || key}: ${value}`
  })

  return `[VALORES CONFIRMADOS NESTA SESSÃO — use estes em vez de buscar benchmark para estes campos específicos:\n${lines.join('\n')}]\n\n`
}
