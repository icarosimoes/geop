import io
from datetime import datetime

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

from app.domain.work_orders.service import STATUS_LABELS


def generate_work_order_pdf(
    *,
    company_name: str,
    order,
    sector_name: str | None,
    assigned_name: str | None,
    participants: list[tuple[int, str]],
    timeline: list[dict],
) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "WOTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
    )
    body = styles["BodyText"]

    elements: list = []

    elements.append(Paragraph(company_name, styles["Heading3"]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(order.title, title_style))
    elements.append(Spacer(1, 0.3 * cm))

    meta = [
        ["Status", STATUS_LABELS.get(order.status, "—")],
        ["Setor", sector_name or "—"],
        ["Responsável", assigned_name or "—"],
        ["Unidade", order.unit or "—"],
        [
            "Prazo",
            order.deadline.strftime("%d/%m/%Y") if order.deadline else "—",
        ],
        [
            "Criado em",
            order.created_at.strftime("%d/%m/%Y %H:%M") if order.created_at else "—",
        ],
    ]
    t = Table(meta, colWidths=[4 * cm, 12 * cm])
    t.setStyle(
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
    elements.append(t)

    if order.description:
        elements.append(Paragraph("Descrição", h2))
        elements.append(Paragraph(order.description, body))

    if order.comments:
        elements.append(Paragraph("Comentários", h2))
        elements.append(Paragraph(order.comments, body))

    if participants:
        elements.append(Paragraph("Participantes", h2))
        names = ", ".join(name for _, name in participants)
        elements.append(Paragraph(names, body))

    if timeline:
        elements.append(Paragraph("Histórico", h2))
        for entry in timeline:
            ts = entry.get("created_at", "")
            if isinstance(ts, datetime):
                ts = ts.strftime("%d/%m/%Y %H:%M")
            user = entry.get("user", "Sistema")
            etype = entry.get("event_type", "")
            msg = entry.get("message", "")
            if etype == "comment" and msg:
                elements.append(Paragraph(f"<b>{user}</b> ({ts}): {msg}", body))
            elif etype == "create":
                elements.append(
                    Paragraph(
                        f"<b>{user}</b> ({ts}): criou a ordem de serviço",
                        body,
                    )
                )
            elif etype == "update":
                diff = entry.get("diff", {})
                changes = "; ".join(f"{k}: {v}" for k, v in diff.items())
                elements.append(Paragraph(f"<b>{user}</b> ({ts}): {changes}", body))

    doc.build(elements)
    buf.seek(0)
    return buf
