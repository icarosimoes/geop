import io
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HEADERS = [
    "Data",
    "1ª Entrada",
    "1ª Saída",
    "2ª Entrada",
    "2ª Saída",
    "Crédito",
    "Débito",
    "Interv.",
    "Trab.",
    "HE 50%",
    "HE 100%",
    "A.N.",
    "Saldo",
    "Obs.",
]


def _fmt_time(value: datetime | None) -> str:
    return value.strftime("%H:%M") if value else "—"


def _fmt_minutes(value: int) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    return f"{sign}{value // 60:02d}:{value % 60:02d}"


def _day_row(day: dict) -> list[str]:
    return [
        day["date"].strftime("%d/%m/%Y"),
        _fmt_time(day["first_in"]),
        _fmt_time(day["first_out"]),
        _fmt_time(day["second_in"]),
        _fmt_time(day["second_out"]),
        _fmt_minutes(day["credit_minutes"]),
        _fmt_minutes(day["debit_minutes"]),
        _fmt_minutes(day["break_minutes"]),
        _fmt_minutes(day["worked_minutes"]),
        _fmt_minutes(day["overtime_50_minutes"]),
        _fmt_minutes(day["overtime_100_minutes"]),
        _fmt_minutes(day["night_differential_minutes"]),
        _fmt_minutes(day["balance_minutes"]),
        day["notes"],
    ]


def generate_mirror_pdf(
    *,
    company_name: str,
    employee_name: str,
    sector_name: str | None,
    date_from: date,
    date_to: date,
    days: list[dict],
    totals: dict,
) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MirrorTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=6
    )

    elements: list = []
    elements.append(Paragraph(company_name, styles["Heading3"]))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph("Espelho de Ponto", title_style))
    subtitle = f"{employee_name} — {sector_name or 'Sem setor'}"
    period = f"Período: {date_from.strftime('%d/%m/%Y')} a {date_to.strftime('%d/%m/%Y')}"
    elements.append(Paragraph(subtitle, styles["Heading3"]))
    elements.append(Paragraph(period, styles["BodyText"]))
    elements.append(Spacer(1, 0.4 * cm))

    rows = [HEADERS] + [_day_row(day) for day in days]
    rows.append(
        [
            "Totais",
            "",
            "",
            "",
            "",
            _fmt_minutes(totals["credit_minutes"]),
            _fmt_minutes(totals["debit_minutes"]),
            _fmt_minutes(totals["break_minutes"]),
            _fmt_minutes(totals["worked_minutes"]),
            _fmt_minutes(totals["overtime_50_minutes"]),
            _fmt_minutes(totals["overtime_100_minutes"]),
            _fmt_minutes(totals["night_differential_minutes"]),
            _fmt_minutes(totals["balance_minutes"]),
            "",
        ]
    )

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    buf.seek(0)
    return buf
