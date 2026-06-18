/**
 * Lógica de recálculo do dashboard editável de TCO.
 *
 * Esse módulo replica em JavaScript um subconjunto BEM PEQUENO e deliberado
 * das fórmulas que o agente Claude usa em prompts.py — apenas o suficiente
 * para o dashboard reagir a edições do vendedor sem precisar chamar a API
 * de novo a cada keystroke.
 *
 * Escopo editável (confirmado com o usuário em 18/06/2026):
 * - Unit cost da SKU Goodpack
 * - Preço de cada acessório do lado Goodpack (packaging_breakdown)
 * - Quantidade envasada por unidade Goodpack (kg)
 *
 * NUNCA editável aqui: lado concorrente, Handling, Transport, Empty
 * Container — esses valores já vêm normalizados por MT no resultado
 * original e são tratados como constantes. Se a estrutura do cálculo
 * precisar mudar (acessório novo, etapa de handling diferente), isso é
 * trabalho do agente na conversa, não deste módulo.
 *
 * ATENÇÃO PARA MANUTENÇÃO: se as fórmulas de Units Needed / Transports
 * Needed / Pallet Places / Full Stacks em prompts.py mudarem, a função
 * recalcLogistics abaixo precisa ser atualizada manualmente para
 * continuar consistente — não há nenhum mecanismo automático de
 * sincronização entre o prompt e este arquivo.
 */

/**
 * Recalcula o total de Packaging (por unidade e por MT) a partir de um
 * packaging_breakdown editado.
 *
 * @param {Array<{label: string, value: number}>} breakdown - breakdown editado
 * @param {number} originalPerUnit - goodpack_per_unit original da categoria Packaging
 * @param {number} originalPerMt - goodpack (per MT) original da categoria Packaging
 * @returns {{ perUnit: number, perMt: number }}
 */
export function recalcPackaging(breakdown, originalPerUnit, originalPerMt) {
  const newPerUnit = breakdown.reduce((sum, item) => sum + (Number(item.value) || 0), 0)

  // Mesma proporção do cálculo original: se o novo total por unidade é X%
  // do original, o custo por MT escala na mesma proporção. Isso assume
  // que a relação per-unit -> per-MT é puramente multiplicativa (verdade
  // quando per-MT = per-unit × constante, que é o caso aqui já que ambos
  // vêm da mesma unidade física dividida pelo mesmo fator de conversão).
  const scaleFactor = originalPerUnit > 0 ? newPerUnit / originalPerUnit : 1
  const newPerMt = originalPerMt * scaleFactor

  return { perUnit: newPerUnit, perMt: newPerMt }
}

/**
 * Recalcula as estatísticas logísticas do lado Goodpack a partir de uma
 * nova quantidade envasada por unidade.
 *
 * Réplica das fórmulas em prompts.py, seção "Estatísticas logísticas":
 * - Units Needed = Volume Simulado (kg) ÷ quantidade por unidade (kg), arredondado para cima
 * - Transports Needed = Units Needed ÷ qty por tipo de transporte, arredondado para cima
 * - Pallet Places = igual a Units Needed (regra padrão; não suporta a
 *   exceção de empilhamento especial mencionada no prompt — esse caso é
 *   raro e fica fora do escopo do dashboard)
 * - Full Stacks = Units Needed ÷ stack_full_warehouse, arredondado para cima
 *
 * @param {number} simulatedMetricTonnes
 * @param {number} qtyPerUnitKg - novo valor editado pelo vendedor
 * @param {number} qtyPerTransport - constante física do transporte escolhido (não editável)
 * @param {number} stackFullWarehouse - constante física da SKU (não editável)
 * @returns {{ unitsNeeded: number, transportsNeeded: number, palletPlaces: number, fullStacks: number }}
 */
export function recalcLogistics(simulatedMetricTonnes, qtyPerUnitKg, qtyPerTransport, stackFullWarehouse) {
  if (!qtyPerUnitKg || qtyPerUnitKg <= 0) {
    return { unitsNeeded: null, transportsNeeded: null, palletPlaces: null, fullStacks: null }
  }

  const simulatedKg = simulatedMetricTonnes * 1000
  const unitsNeeded = Math.ceil(simulatedKg / qtyPerUnitKg)
  const transportsNeeded = qtyPerTransport > 0 ? Math.ceil(unitsNeeded / qtyPerTransport) : null
  const palletPlaces = unitsNeeded
  const fullStacks = stackFullWarehouse > 0 ? Math.ceil(unitsNeeded / stackFullWarehouse) : null

  return { unitsNeeded, transportsNeeded, palletPlaces, fullStacks }
}

/**
 * Recalcula o resultado completo do dashboard (totais, saving) a partir
 * de um novo custo de Packaging do lado Goodpack — propaga a diferença
 * para o total geral, mantendo Handling/Transport/Empty Container
 * inalterados (já vêm em $/MT, não dependem de quantidade por unidade).
 *
 * @param {object} result - TCO_RESULT original (não modificado)
 * @param {number} newPackagingPerMt - novo valor de Packaging por MT
 * @returns {{ goodpackTotalPerMt: number, totalSaving: number, savingPercentage: number }}
 */
export function recalcTotals(result, newPackagingPerMt) {
  const categories = result.categories || []
  const otherCategoriesTotal = categories
    .filter(c => c.label !== 'Packaging')
    .reduce((sum, c) => sum + (Number(c.goodpack) || 0), 0)

  const goodpackTotalPerMt = newPackagingPerMt + otherCategoriesTotal
  const competitorTotalPerMt = result.competitor_total_per_mt || 0
  const simulatedMetricTonnes = result.simulated_metric_tonnes || 0

  const savingPerMt = competitorTotalPerMt - goodpackTotalPerMt
  const totalSaving = savingPerMt * simulatedMetricTonnes
  const savingPercentage = competitorTotalPerMt > 0 ? (savingPerMt / competitorTotalPerMt) * 100 : 0

  return { goodpackTotalPerMt, totalSaving, savingPercentage }
}
