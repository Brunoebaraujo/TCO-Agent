"""
Gera um arquivo .pptx a partir de um resultado de TCO estruturado.

Produz 1, 2 ou 3 slides:
- Slide 1 (sempre): gráfico empilhado com totais, estatísticas logísticas,
  tabela Cost/Unit + Cost/MT, métricas-resumo.
- Slide 2 (opcional): investimento e payback, se a oportunidade tiver isso.
- Slide 3 (opcional): premissas usadas, com nível de confiança e fonte.
"""
import io
import math
from datetime import datetime
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION

NAVY = RGBColor(0x1A, 0x3A, 0x5C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SLATE_700 = RGBColor(0x33, 0x41, 0x55)
SLATE_400 = RGBColor(0x94, 0xA3, 0xB8)
EMERALD = RGBColor(0x05, 0x96, 0x69)

STACK_COLORS = [
    RGBColor(0x37, 0x8A, 0xDD),
    RGBColor(0x88, 0x87, 0x80),
    RGBColor(0x85, 0xB7, 0xEB),
    RGBColor(0xBA, 0x75, 0x17),
    RGBColor(0x1D, 0x9E, 0x75),
]

CONFIDENCE_COLORS = {
    "verified": RGBColor(0x05, 0x96, 0x69),
    "high_confidence": RGBColor(0xB4, 0x55, 0x0B),
    "validation_required": RGBColor(0xDC, 0x26, 0x26),
}
CONFIDENCE_LABELS = {
    "verified": "Verified",
    "high_confidence": "High confidence",
    "validation_required": "Validation required",
}

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def _set_background(slide, color):
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = color


def _add_text(slide, left, top, width, height, text, size=14, color=SLATE_700,
               bold=False, align=PP_ALIGN.LEFT, font_name="Calibri"):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.name = font_name
    return box


def _fmt_currency(v):
    return f"${v:,.2f}"


def _fmt_number(v):
    if v is None:
        return "—"
    return f"{round(v):,}"


def _build_summary_slide(prs, tco):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # layout em branco
    _set_background(slide, WHITE)

    currency = tco.get("currency", "USD")
    categories = tco.get("categories", [])
    competitor_name = tco.get("competitor_name", "Concorrente")
    goodpack_sku = tco.get("goodpack_sku", "Goodpack")
    logistics = tco.get("logistics") or {}

    # Header navy
    header = slide.shapes.add_shape(1, 0, 0, SLIDE_W, Inches(1.0))  # 1 = rectangle
    header.fill.solid()
    header.fill.fore_color.rgb = NAVY
    header.line.fill.background()
    header.shadow.inherit = False

    subtitle_parts = [
        tco.get("product_name", ""),
        f"{tco.get('simulated_metric_tonnes', '')} MT",
        f"{goodpack_sku} vs {competitor_name}",
    ]
    if tco.get("transport_type"):
        subtitle_parts.append(tco["transport_type"])
    if tco.get("lease_days") is not None:
        subtitle_parts.append(f"{tco['lease_days']} lease days")

    _add_text(slide, Inches(0.4), Inches(0.12), Inches(9), Inches(0.4),
              f"{tco.get('customer_name', '')} — TCO Analysis", size=20, color=WHITE, bold=True)
    _add_text(slide, Inches(0.4), Inches(0.54), Inches(11), Inches(0.4),
              " · ".join(subtitle_parts), size=11, color=RGBColor(0xC8, 0xD4, 0xE0))

    # --- Gráfico empilhado (lado esquerdo) ---
    chart_left, chart_top = Inches(0.4), Inches(1.25)
    chart_width, chart_height = Inches(6.6), Inches(3.1)

    chart_data = CategoryChartData()
    chart_data.categories = [goodpack_sku, competitor_name]
    for cat in categories:
        chart_data.add_series(cat["label"], [cat["goodpack"], cat["competitor"]])

    graphic_frame = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_STACKED, chart_left, chart_top, chart_width, chart_height, chart_data
    )
    chart = graphic_frame.chart
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = Pt(8)

    plot = chart.plots[0]
    for i, series in enumerate(plot.series):
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = STACK_COLORS[i % len(STACK_COLORS)]

    chart.category_axis.tick_labels.font.size = Pt(9)
    chart.value_axis.tick_labels.font.size = Pt(8)

    # Totais sobrepostos no topo de cada coluna — python-pptx não tem um
    # recurso nativo de "data label de total" em gráfico empilhado, então
    # desenhamos caixas de texto posicionadas manualmente acima de cada
    # barra, escaladas pela altura do gráfico e o valor máximo do eixo Y.
    goodpack_total = tco.get("goodpack_total_per_mt") or 0
    competitor_total = tco.get("competitor_total_per_mt") or 0
    max_total = max(goodpack_total, competitor_total, 1)
    axis_max = max_total * 1.15  # mesma margem de 12-15% usada no Chart.js do frontend

    plot_area_top = chart_top + Inches(0.15)
    plot_area_height = chart_height - Inches(0.85)  # desconta legenda + margens
    plot_area_left = chart_left + Inches(0.55)
    plot_area_width = chart_width - Inches(0.7)

    bar_centers_x = [
        plot_area_left + plot_area_width * 0.27,
        plot_area_left + plot_area_width * 0.73,
    ]
    totals = [goodpack_total, competitor_total]

    for x_center, total in zip(bar_centers_x, totals):
        bar_top_y = plot_area_top + plot_area_height * (1 - total / axis_max)
        label_box = slide.shapes.add_textbox(
            Emu(int(x_center - Inches(0.6))), Emu(int(bar_top_y - Inches(0.28))),
            Inches(1.2), Inches(0.25),
        )
        tf = label_box.text_frame
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = _fmt_currency(total)
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = SLATE_700

    # --- Painel de estatísticas logísticas (lado direito, topo) ---
    stats_left = Inches(7.3)
    stats_top = Inches(1.25)
    stats_width = Inches(5.6)

    stat_defs = [
        ("Transports needed", "transports_needed"),
        ("Units needed", "units_needed"),
        ("Pallet places", "pallet_places"),
        ("Full stacks", "full_stacks"),
    ]
    card_w = (stats_width - Inches(0.3)) / 2
    card_h = Inches(0.85)
    for i, (label, key) in enumerate(stat_defs):
        col = i % 2
        row = i // 2
        card_left = stats_left + col * (card_w + Inches(0.15))
        card_top = stats_top + row * (card_h + Inches(0.12))

        card = slide.shapes.add_shape(1, card_left, card_top, card_w, card_h)
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(0xF8, 0xFA, 0xFC)
        card.line.fill.background()
        card.shadow.inherit = False

        gp_val = (logistics.get("goodpack") or {}).get(key)
        comp_val = (logistics.get("competitor") or {}).get(key)

        _add_text(slide, card_left + Inches(0.1), card_top + Inches(0.06),
                   card_w - Inches(0.2), Inches(0.22), label, size=8.5, color=SLATE_400)
        _add_text(slide, card_left + Inches(0.1), card_top + Inches(0.32),
                   card_w - Inches(0.2), Inches(0.4),
                   f"{_fmt_number(gp_val)} vs {_fmt_number(comp_val)}", size=13, color=SLATE_700, bold=True)

    # --- Tabela Cost/Unit + Cost/MT (parte inferior, largura total) ---
    table_top = Inches(4.55)
    n_cat_cols = len(categories)
    cols = 1 + (n_cat_cols * 2) + 2  # rótulo + (unit+mt por categoria) + total unit/mt
    rows = 3  # header categoria, header unit/mt, + 2 linhas de dados (vamos adicionar mais abaixo)
    rows = 4  # header categoria, header unit/mt, linha goodpack, linha competitor

    table_width = Inches(12.5)
    table_height = Inches(1.4)
    table_shape = slide.shapes.add_table(rows, cols, Inches(0.4), table_top, table_width, table_height)
    table = table_shape.table

    label_col_width = Inches(1.4)
    remaining_width = table_width - label_col_width
    other_col_width = int(remaining_width / (cols - 1))
    table.columns[0].width = label_col_width
    for c in range(1, cols):
        table.columns[c].width = Emu(other_col_width)

    def _style_header_cell(cell, text, size=9):
        cell.text = text
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        para = cell.text_frame.paragraphs[0]
        para.font.size = Pt(size)
        para.font.color.rgb = WHITE
        para.font.bold = True
        para.alignment = PP_ALIGN.CENTER

    # Linha 0: nomes das categorias (mescladas visualmente via texto centralizado, sem merge real)
    table.cell(0, 0).text = ""
    table.cell(0, 0).fill.solid()
    table.cell(0, 0).fill.fore_color.rgb = NAVY
    for i, cat in enumerate(categories):
        col_start = 1 + i * 2
        table.cell(0, col_start).merge(table.cell(0, col_start + 1))
        _style_header_cell(table.cell(0, col_start), cat["label"])
    table.cell(0, cols - 2).merge(table.cell(0, cols - 1))
    _style_header_cell(table.cell(0, cols - 2), "Total")

    # Linha 1: sub-headers Unit / MT
    _style_header_cell(table.cell(1, 0), "", size=8)
    for i in range(n_cat_cols):
        col_start = 1 + i * 2
        _style_header_cell(table.cell(1, col_start), "Unit", size=8)
        _style_header_cell(table.cell(1, col_start + 1), "MT", size=8)
    _style_header_cell(table.cell(1, cols - 2), "Unit", size=8)
    _style_header_cell(table.cell(1, cols - 1), "MT", size=8)

    def _fill_data_row(row_idx, label, per_unit_key, per_mt_key, total_per_unit, total_per_mt):
        cell = table.cell(row_idx, 0)
        cell.text = label
        cell.fill.solid()
        cell.fill.fore_color.rgb = WHITE
        cell.text_frame.paragraphs[0].font.size = Pt(9.5)
        cell.text_frame.paragraphs[0].font.bold = True
        cell.text_frame.paragraphs[0].font.color.rgb = SLATE_700

        for i, cat in enumerate(categories):
            col_start = 1 + i * 2
            for offset, key in enumerate([per_unit_key, per_mt_key]):
                val = cat.get(key)
                c = table.cell(row_idx, col_start + offset)
                c.text = f"{val:.2f}" if val is not None else "—"
                c.fill.solid()
                c.fill.fore_color.rgb = WHITE
                c.text_frame.paragraphs[0].font.size = Pt(9)
                c.text_frame.paragraphs[0].font.color.rgb = SLATE_700
                c.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT

        for offset, val in enumerate([total_per_unit, total_per_mt]):
            c = table.cell(row_idx, cols - 2 + offset)
            c.text = f"{val:.2f}" if val is not None else "—"
            c.fill.solid()
            c.fill.fore_color.rgb = RGBColor(0xF1, 0xF5, 0xF9)
            c.text_frame.paragraphs[0].font.size = Pt(9.5)
            c.text_frame.paragraphs[0].font.bold = True
            c.text_frame.paragraphs[0].font.color.rgb = SLATE_700
            c.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT

    _fill_data_row(2, goodpack_sku, "goodpack_per_unit", "goodpack",
                   tco.get("goodpack_total_per_unit"), tco.get("goodpack_total_per_mt"))
    _fill_data_row(3, competitor_name, "competitor_per_unit", "competitor",
                   tco.get("competitor_total_per_unit"), tco.get("competitor_total_per_mt"))

    # --- Métricas-resumo (canto inferior direito) ---
    metrics_top = table_top + table_height + Inches(0.25)
    metrics = [
        ("Saving total", _fmt_currency(tco.get("total_saving", 0)), EMERALD),
        ("Redução", f"{tco.get('saving_percentage', 0)}%", SLATE_700),
        ("Premissas", str(len(tco.get("assumptions", []))), SLATE_700),
    ]
    card_width = Inches(2.6)
    for i, (label, value, color) in enumerate(metrics):
        card_left = Inches(0.4) + i * (card_width + Inches(0.15))
        card = slide.shapes.add_shape(1, card_left, metrics_top, card_width, Inches(0.85))
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(0xF8, 0xFA, 0xFC)
        card.line.fill.background()
        card.shadow.inherit = False
        _add_text(slide, card_left + Inches(0.12), metrics_top + Inches(0.06),
                   card_width - Inches(0.24), Inches(0.28), label, size=9.5, color=SLATE_400)
        _add_text(slide, card_left + Inches(0.12), metrics_top + Inches(0.34),
                   card_width - Inches(0.24), Inches(0.42), value, size=18, color=color, bold=True)

    # Footer
    _add_text(slide, Inches(0.4), Inches(7.15), Inches(8), Inches(0.3),
               f"Gerado em {datetime.now().strftime('%d/%m/%Y')} · TCO Engine — Goodpack",
               size=8.5, color=SLATE_400)

    return slide


def _build_investment_slide(prs, tco):
    """Slide opcional — só é chamado se tco tiver um bloco 'investment'."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_background(slide, WHITE)

    header = slide.shapes.add_shape(1, 0, 0, SLIDE_W, Inches(0.85))
    header.fill.solid()
    header.fill.fore_color.rgb = NAVY
    header.line.fill.background()
    header.shadow.inherit = False
    _add_text(slide, Inches(0.5), Inches(0.2), Inches(8), Inches(0.45),
               "Investimento e payback", size=18, color=WHITE, bold=True)

    investment = tco.get("investment", {})
    currency = tco.get("currency", "USD")
    goodpack_sku = tco.get("goodpack_sku", "Goodpack")
    competitor_name = tco.get("competitor_name", "Concorrente")

    sides = [
        (goodpack_sku, investment.get("goodpack_investment_required"), investment.get("goodpack_payback_cycles")),
        (competitor_name, investment.get("competitor_investment_required"), investment.get("competitor_payback_cycles")),
    ]

    card_width = Inches(5.8)
    card_top = Inches(1.4)
    for i, (label, inv, payback) in enumerate(sides):
        if inv is None:
            continue
        card_left = Inches(0.5) + i * (card_width + Inches(0.3))
        card = slide.shapes.add_shape(1, card_left, card_top, card_width, Inches(1.8))
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(0xF8, 0xFA, 0xFC)
        card.line.fill.background()
        card.shadow.inherit = False

        _add_text(slide, card_left + Inches(0.25), card_top + Inches(0.18),
                   card_width - Inches(0.5), Inches(0.35), label, size=14, color=SLATE_700, bold=True)
        _add_text(slide, card_left + Inches(0.25), card_top + Inches(0.6),
                   card_width - Inches(0.5), Inches(0.3), "Investimento necessário", size=10, color=SLATE_400)
        _add_text(slide, card_left + Inches(0.25), card_top + Inches(0.9),
                   card_width - Inches(0.5), Inches(0.4), _fmt_currency(inv), size=22, color=SLATE_700, bold=True)

        if payback is not None:
            _add_text(slide, card_left + Inches(0.25), card_top + Inches(1.4),
                       card_width - Inches(0.5), Inches(0.3),
                       f"Payback: {payback:.2f} ciclos de lease", size=11, color=EMERALD, bold=True)

    return slide


def _build_assumptions_slide(prs, tco):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_background(slide, WHITE)

    header = slide.shapes.add_shape(1, 0, 0, SLIDE_W, Inches(0.85))
    header.fill.solid()
    header.fill.fore_color.rgb = NAVY
    header.line.fill.background()
    header.shadow.inherit = False
    _add_text(slide, Inches(0.5), Inches(0.2), Inches(8), Inches(0.45),
               "Premissas utilizadas neste cálculo", size=18, color=WHITE, bold=True)

    assumptions = tco.get("assumptions", [])
    top = Inches(1.1)
    row_height = Inches(0.62)
    max_rows_per_col = 9
    col_width = Inches(6.1)

    for i, a in enumerate(assumptions):
        col = i // max_rows_per_col
        row = i % max_rows_per_col
        left = Inches(0.5) + col * (col_width + Inches(0.3))
        item_top = top + row * row_height

        confidence = a.get("confidence_level", "validation_required")
        color = CONFIDENCE_COLORS.get(confidence, CONFIDENCE_COLORS["validation_required"])
        label_text = CONFIDENCE_LABELS.get(confidence, confidence)

        card = slide.shapes.add_shape(1, left, item_top, col_width, Inches(0.56))
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(0xF8, 0xFA, 0xFC)
        card.line.fill.background()
        card.shadow.inherit = False

        _add_text(slide, left + Inches(0.1), item_top + Inches(0.04),
                   col_width - Inches(1.6), Inches(0.3), a.get("label", ""), size=9.5, color=SLATE_700)
        if a.get("source"):
            _add_text(slide, left + Inches(0.1), item_top + Inches(0.3),
                       col_width - Inches(1.6), Inches(0.22), f"Fonte: {a['source']}", size=8, color=SLATE_400)

        badge = slide.shapes.add_shape(1, left + col_width - Inches(1.45), item_top + Inches(0.13),
                                         Inches(1.3), Inches(0.3))
        badge.fill.solid()
        badge.fill.fore_color.rgb = color
        badge.line.fill.background()
        badge.shadow.inherit = False
        tf = badge.text_frame
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = label_text
        run.font.size = Pt(8.5)
        run.font.color.rgb = WHITE
        run.font.bold = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    return slide


def generate_tco_pptx(tco: dict, include_assumptions: bool = True) -> bytes:
    """
    Gera o arquivo .pptx em memória e retorna os bytes — para ser enviado
    diretamente como resposta HTTP, sem precisar gravar em disco.
    """
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    _build_summary_slide(prs, tco)

    investment = tco.get("investment")
    if investment and (investment.get("goodpack_investment_required") is not None
                        or investment.get("competitor_investment_required") is not None):
        _build_investment_slide(prs, tco)

    if include_assumptions and tco.get("assumptions"):
        _build_assumptions_slide(prs, tco)

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer.read()
