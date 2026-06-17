"""
Gera um arquivo .pptx a partir de um resultado de TCO estruturado.

Produz 1 ou 2 slides:
- Slide 1 (sempre): resumo executivo — tabela comparativa, gráfico, saving total.
- Slide 2 (opcional): premissas usadas, com nível de confiança e fonte.
"""
import io
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
GRAY_COMPETITOR = RGBColor(0x88, 0x87, 0x80)

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


def _build_summary_slide(prs, tco):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # layout em branco
    _set_background(slide, WHITE)

    currency = tco.get("currency", "USD")
    categories = tco.get("categories", [])
    competitor_name = tco.get("competitor_name", "Concorrente")

    # Header navy
    header = slide.shapes.add_shape(1, 0, 0, SLIDE_W, Inches(1.1))  # 1 = rectangle
    header.fill.solid()
    header.fill.fore_color.rgb = NAVY
    header.line.fill.background()
    header.shadow.inherit = False

    _add_text(slide, Inches(0.5), Inches(0.15), Inches(8), Inches(0.4),
              f"{tco.get('customer_name', '')} — TCO Analysis", size=22, color=WHITE, bold=True)
    _add_text(slide, Inches(0.5), Inches(0.58), Inches(10), Inches(0.4),
              f"{tco.get('product_name', '')} · {tco.get('simulated_metric_tonnes', '')} MT · "
              f"{tco.get('goodpack_sku', '')} vs {competitor_name}",
              size=12, color=RGBColor(0xC8, 0xD4, 0xE0))

    # --- Tabela comparativa ---
    rows = len(categories) + 2  # header + categorias + total
    cols = 4
    table_left, table_top = Inches(0.5), Inches(1.45)
    table_width, table_height = Inches(7.4), Inches(0.42) * rows

    table_shape = slide.shapes.add_table(rows, cols, table_left, table_top, table_width, table_height)
    table = table_shape.table
    table.columns[0].width = Inches(2.8)
    table.columns[1].width = Inches(1.55)
    table.columns[2].width = Inches(1.55)
    table.columns[3].width = Inches(1.5)

    headers = ["Categoria", "Goodpack", competitor_name, "Saving"]
    for c, h in enumerate(headers):
        cell = table.cell(0, c)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        para = cell.text_frame.paragraphs[0]
        para.font.size = Pt(11)
        para.font.color.rgb = WHITE
        para.font.bold = True
        para.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT

    def _fmt(v):
        return f"${v:,.2f}"

    for r, cat in enumerate(categories, start=1):
        saving = cat["competitor"] - cat["goodpack"]
        values = [cat["label"], _fmt(cat["goodpack"]), _fmt(cat["competitor"]), _fmt(saving)]
        for c, val in enumerate(values):
            cell = table.cell(r, c)
            cell.text = val
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE
            para = cell.text_frame.paragraphs[0]
            para.font.size = Pt(10.5)
            para.font.color.rgb = EMERALD if c == 3 else SLATE_700
            para.font.bold = (c == 3)
            para.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT

    total_row = rows - 1
    goodpack_total = tco.get("goodpack_total_per_mt", 0)
    competitor_total = tco.get("competitor_total_per_mt", 0)
    total_values = ["Total por MT", _fmt(goodpack_total), _fmt(competitor_total),
                     _fmt(competitor_total - goodpack_total)]
    for c, val in enumerate(total_values):
        cell = table.cell(total_row, c)
        cell.text = val
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(0xF1, 0xF5, 0xF9)
        para = cell.text_frame.paragraphs[0]
        para.font.size = Pt(11)
        para.font.bold = True
        para.font.color.rgb = EMERALD if c == 3 else SLATE_700
        para.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT

    # --- Gráfico comparativo ---
    chart_data = CategoryChartData()
    chart_data.categories = [c["label"] for c in categories]
    chart_data.add_series("Goodpack", [c["goodpack"] for c in categories])
    chart_data.add_series(competitor_name, [c["competitor"] for c in categories])

    chart_left, chart_top = Inches(8.2), Inches(1.45)
    chart_width, chart_height = Inches(4.6), Inches(3.1)
    graphic_frame = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, chart_left, chart_top, chart_width, chart_height, chart_data
    )
    chart = graphic_frame.chart
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = Pt(10)

    plot = chart.plots[0]
    plot.series[0].format.fill.solid()
    plot.series[0].format.fill.fore_color.rgb = NAVY
    plot.series[1].format.fill.solid()
    plot.series[1].format.fill.fore_color.rgb = GRAY_COMPETITOR

    chart.category_axis.tick_labels.font.size = Pt(8)
    chart.value_axis.tick_labels.font.size = Pt(8)

    # --- Métricas-resumo ---
    metrics_top = table_top + table_height + Inches(0.35)
    metrics = [
        ("Saving total", f"${tco.get('total_saving', 0):,.0f}", EMERALD),
        ("Redução", f"{tco.get('saving_percentage', 0)}%", SLATE_700),
        ("Premissas", str(len(tco.get("assumptions", []))), SLATE_700),
    ]
    card_width = Inches(2.35)
    for i, (label, value, color) in enumerate(metrics):
        card_left = Inches(0.5) + i * (card_width + Inches(0.15))
        card = slide.shapes.add_shape(1, card_left, metrics_top, card_width, Inches(0.95))
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(0xF8, 0xFA, 0xFC)
        card.line.fill.background()
        card.shadow.inherit = False
        _add_text(slide, card_left + Inches(0.12), metrics_top + Inches(0.08),
                   card_width - Inches(0.24), Inches(0.3), label, size=10, color=SLATE_400)
        _add_text(slide, card_left + Inches(0.12), metrics_top + Inches(0.4),
                   card_width - Inches(0.24), Inches(0.45), value, size=20, color=color, bold=True)

    # Footer
    _add_text(slide, Inches(0.5), Inches(7.1), Inches(8), Inches(0.3),
               f"Gerado em {datetime.now().strftime('%d/%m/%Y')} · TCO Engine — Goodpack",
               size=9, color=SLATE_400)

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
    if include_assumptions and tco.get("assumptions"):
        _build_assumptions_slide(prs, tco)

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer.read()
