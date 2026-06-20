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
export function recalcCategoriesByQty(categories, newQtyKg, origQtyKg, qtyPerTransport, transportCostPerContainer) {
  const ratio = (origQtyKg && newQtyKg) ? origQtyKg / newQtyKg : 1
  const result = {}

  for (const cat of categories) {
    if (cat.label === 'Transport') {
      if (transportCostPerContainer && qtyPerTransport && newQtyKg) {
        const liquidMtPerContainer = (newQtyKg / 1000) * qtyPerTransport
        result[cat.label] = { perMt: transportCostPerContainer / liquidMtPerContainer }
      } else {
        // Sem custo por container: usa a mesma proporção das demais categorias
        result[cat.label] = { perMt: cat.goodpack * ratio }
      }
    } else {
      // Packaging, Handling, Empty: custo per_unit fixo ÷ nova qty em MT
      // Usamos proporção sobre o $/MT original para manter consistência
      result[cat.label] = { perMt: cat.goodpack * ratio }
    }
  }

  return result
}

/**
 * Recalcula estatísticas logísticas Goodpack.
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
 * demais por qty) e calcula os totais finais.
 *
 * @param {object} result - TCO_RESULT original
 * @param {Object} categoryOverrides - mapa label → { perMt } para categorias com preço editado
 *   (ex: { Packaging: {perMt}, 'Handling packer': {perMt} }) — aceita também o formato antigo
 *   (number) para manter compatibilidade com chamadas existentes que passavam só o Packaging.
 * @param {Object|null} recalcedByQty - mapa de categorias recalculadas por qty, ou null
 * @returns {{ goodpackTotalPerMt, totalSaving, savingPercentage, categoriesRecalced }}
 */
export function recalcTotals(result, categoryOverrides, recalcedByQty) {
  const categories = result.categories || []

  // Compatibilidade: chamadas antigas passavam newPackagingPerMt (number) direto.
  const overrides = typeof categoryOverrides === 'number'
    ? { Packaging: { perMt: categoryOverrides } }
    : (categoryOverrides || {})

  const categoriesRecalced = categories.map(cat => {
    const override = overrides[cat.label]
    if (override) {
      return { ...cat, goodpack: override.perMt ?? cat.goodpack }
    }
    const rc = recalcedByQty?.[cat.label]
    return rc ? { ...cat, goodpack: rc.perMt ?? cat.goodpack } : cat
  })

  const goodpackTotalPerMt = categoriesRecalced.reduce(
    (sum, c) => sum + (Number(c.goodpack) || 0), 0
  )
  const competitorTotalPerMt = result.competitor_total_per_mt || 0
  const simulatedMt = result.simulated_metric_tonnes || 0
  const savingPerMt = competitorTotalPerMt - goodpackTotalPerMt
  const totalSaving = savingPerMt * simulatedMt
  const savingPercentage = competitorTotalPerMt > 0 ? (savingPerMt / competitorTotalPerMt) * 100 : 0

  return { goodpackTotalPerMt, totalSaving, savingPercentage, categoriesRecalced }
}
