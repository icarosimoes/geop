import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.discrepancy_reports.service import DiscrepancyReportDetail, code_summary

STATUS_LABELS = {
    "draft": "Rascunho",
    "submitted": "Enviada",
    "closed": "Fechada",
}


def generate_discrepancy_report_pdf(
    *,
    company_name: str,
    detail: DiscrepancyReportDetail,
    checked_by_name: str | None,
    received_by_name: str | None,
) -> io.BytesIO:
    report = detail.report
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DRTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=6
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=6)
    body = styles["BodyText"]

    elements: list = []
    elements.append(Paragraph(company_name, styles["Heading3"]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph("Conferência de discrepâncias", title_style))
    elements.append(Spacer(1, 0.3 * cm))

    meta = [
        ["Data", report.report_date.strftime("%d/%m/%Y")],
        ["Status", STATUS_LABELS.get(report.status, report.status)],
        ["Preparado por", detail.prepared_by_name or "—"],
        ["Conferido por", checked_by_name or "—"],
        ["Recebido por", received_by_name or "—"],
    ]
    meta_table = Table(meta, colWidths=[4 * cm, 12.5 * cm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(meta_table)

    if detail.entries:
        elements.append(Paragraph("Locais conferidos", h2))
        rows = [["Local", "1ª verificação", "2ª verificação", "Observações"]]
        for entry, location_name in detail.entries:
            rows.append(
                [
                    location_name,
                    entry.first_code or "—",
                    entry.second_code or "—",
                    entry.notes or "—",
                ]
            )
        entries_table = Table(rows, colWidths=[4.5 * cm, 3 * cm, 3 * cm, 6 * cm], repeatRows=1)
        style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for i, (entry, _) in enumerate(detail.entries, start=1):
            if bool(entry.first_code) and entry.first_code != entry.second_code:
                style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FEF2F2")))
        entries_table.setStyle(TableStyle(style))
        elements.append(entries_table)

    summary = code_summary(detail.entries)
    if summary:
        elements.append(Paragraph("Resumo por código", h2))
        summary_rows = [["Código", "Ocorrências"]] + [
            [code, str(count)] for code, count in sorted(summary.items())
        ]
        summary_table = Table(summary_rows, colWidths=[4 * cm, 4 * cm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ]
            )
        )
        elements.append(summary_table)

    if report.observations:
        elements.append(Paragraph("Observações", h2))
        elements.append(Paragraph(report.observations, body))

    doc.build(elements)
    buf.seek(0)
    return buf
