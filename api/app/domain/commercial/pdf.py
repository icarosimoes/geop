import io
from decimal import Decimal

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

from app.models import Quote, QuoteItem, QuoteSignature, Sale, SalesInvoice

SIGNATURE_METHOD_LABELS = {
    "simples": "Assinatura eletrônica simples (código de confirmação por e-mail)",
    "icp_brasil": "Certificado digital ICP-Brasil (MP 2.200-2/2001)",
}

QUOTE_STATUS_LABELS = {
    "rascunho": "Rascunho",
    "enviado": "Enviado",
    "aceito": "Aprovado",
    "recusado": "Recusado",
    "expirado": "Expirado",
    "cancelado": "Cancelado",
}
SALE_STATUS_LABELS = {
    "confirmada": "Confirmada",
    "entregue": "Entregue",
    "concluida": "Concluída",
    "cancelada": "Cancelada",
}
INSTALLATION_STATUS_LABELS = {
    "pendente": "Pendente",
    "agendada": "Agendada",
    "em_andamento": "Em andamento",
    "concluida": "Concluída",
    "cancelada": "Cancelada",
}
INVOICE_STATUS_LABELS = {
    "pendente": "Pendente",
    "faturada": "Faturada",
    "paga": "Paga",
    "atrasada": "Atrasada",
    "cancelada": "Cancelada",
}


def _money(value: Decimal | None) -> str:
    """`R$ 1.234,56` sem depender de `locale` do sistema (não instalado nas imagens
    de container) — mesmo truque de troca de separador usado em relatórios Excel
    do projeto."""
    if value is None:
        return "—"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _base_doc() -> tuple[io.BytesIO, SimpleDocTemplate]:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    return buf, doc


def _styles() -> dict:
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=styles["Heading1"], fontSize=16, spaceAfter=6),
        "h2": ParagraphStyle(
            "H2", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=6
        ),
        "body": styles["BodyText"],
        "heading3": styles["Heading3"],
    }


def _items_table(items: list[QuoteItem]) -> Table:
    header = ["Item", "Qtd", "Preço unit.", "Desc. %", "Total"]
    rows = [header]
    for i in items:
        item_type = "Produto" if i.item_type == "produto" else "Serviço"
        rows.append(
            [
                f"{i.description} ({item_type})",
                f"{i.quantity} {i.unit}",
                _money(i.unit_price),
                f"{i.discount_percent:.2f}%".replace(".", ",") if i.discount_percent else "—",
                _money(i.line_total),
            ]
        )
    t = Table(rows, colWidths=[7 * cm, 3 * cm, 3 * cm, 2 * cm, 3 * cm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, "#999999"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ]
        )
    )
    return t


def _totals_table(subtotal: Decimal, discount_amount: Decimal, total: Decimal) -> Table:
    rows = [
        ["Subtotal", _money(subtotal)],
        ["Desconto", f"-{_money(discount_amount)}"],
        ["Total", _money(total)],
    ]
    t = Table(rows, colWidths=[14 * cm, 4 * cm], hAlign="RIGHT")
    t.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 12),
                ("TOPPADDING", (0, -1), (-1, -1), 6),
                ("LINEABOVE", (0, -1), (-1, -1), 0.5, "#999999"),
            ]
        )
    )
    return t


def _signature_section(signature: QuoteSignature, s: dict) -> list:
    """Página de evidência anexada ao PDF já assinado — mesma prática de
    Clicksign/Autentique. O hash em `document_hash` se refere ao PDF SEM esta
    seção (calculado antes de anexá-la, ver
    commercial/service.py::confirm_signature_otp/start_icp_signature) — ela é
    só um resumo legível pra humano da evidência já registrada, não faz parte
    do conteúdo assinado em si."""
    elements: list = [
        Paragraph("Registro de assinatura eletrônica", s["h2"]),
    ]
    rows = [
        ["Método", SIGNATURE_METHOD_LABELS.get(signature.method, signature.method)],
        ["Signatário", signature.signer_name or "—"],
        ["CPF", signature.signer_document or "—"],
        ["E-mail", signature.signer_email or "—"],
        [
            "Assinado em",
            signature.signed_at.strftime("%d/%m/%Y %H:%M:%S") if signature.signed_at else "—",
        ],
        ["Endereço IP", signature.ip_address or "—"],
        ["Hash SHA-256 do documento", signature.document_hash or "—"],
    ]
    if signature.method == "icp_brasil" and signature.certificate_info:
        rows.append(["Provedor", signature.provider or "—"])
        for key, value in signature.certificate_info.items():
            rows.append([f"Certificado — {key}", str(value)])
    t = Table(rows, colWidths=[5 * cm, 11 * cm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(t)
    return elements


def generate_quote_pdf(
    *,
    company_name: str,
    quote: Quote,
    customer_name: str,
    items: list[QuoteItem],
    signature: QuoteSignature | None = None,
) -> io.BytesIO:
    buf, doc = _base_doc()
    s = _styles()
    elements: list = []

    elements.append(Paragraph(company_name, s["heading3"]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(f"Orçamento {quote.number or f'#{quote.id}'}", s["title"]))
    elements.append(Paragraph(quote.title, s["body"]))
    elements.append(Spacer(1, 0.3 * cm))

    meta = [
        ["Cliente", customer_name],
        ["Status", QUOTE_STATUS_LABELS.get(quote.status, quote.status)],
        ["Emitido em", quote.issued_at.strftime("%d/%m/%Y") if quote.issued_at else "—"],
        ["Válido até", quote.valid_until.strftime("%d/%m/%Y") if quote.valid_until else "—"],
    ]
    meta_table = Table(meta, colWidths=[4 * cm, 12 * cm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 0.4 * cm))

    if quote.description:
        elements.append(Paragraph("Descrição", s["h2"]))
        elements.append(Paragraph(quote.description, s["body"]))

    elements.append(Paragraph("Itens", s["h2"]))
    elements.append(_items_table(items))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(_totals_table(quote.subtotal, quote.discount_amount, quote.total))

    if quote.conditions:
        elements.append(Paragraph("Condições", s["h2"]))
        elements.append(Paragraph(quote.conditions, s["body"]))

    if quote.notes:
        elements.append(Paragraph("Observações", s["h2"]))
        elements.append(Paragraph(quote.notes, s["body"]))

    if signature and signature.status == "assinado":
        elements.extend(_signature_section(signature, s))

    doc.build(elements)
    buf.seek(0)
    return buf


def generate_sale_pdf(
    *,
    company_name: str,
    sale: Sale,
    customer_name: str,
    quote_items: list[QuoteItem],
    invoices: list[tuple[SalesInvoice, Decimal]],
) -> io.BytesIO:
    buf, doc = _base_doc()
    s = _styles()
    elements: list = []

    elements.append(Paragraph(company_name, s["heading3"]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(f"Venda {sale.number or f'#{sale.id}'}", s["title"]))
    elements.append(Spacer(1, 0.3 * cm))

    meta = [
        ["Cliente", customer_name],
        ["Status", SALE_STATUS_LABELS.get(sale.status, sale.status)],
        ["Entregue em", sale.delivered_at.strftime("%d/%m/%Y") if sale.delivered_at else "—"],
        [
            "Instalação",
            INSTALLATION_STATUS_LABELS.get(sale.installation_status, sale.installation_status),
        ],
        ["Valor total", _money(sale.total_value)],
    ]
    meta_table = Table(meta, colWidths=[4 * cm, 12 * cm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 0.4 * cm))

    if quote_items:
        elements.append(Paragraph("Itens", s["h2"]))
        elements.append(_items_table(quote_items))
        elements.append(Spacer(1, 0.3 * cm))

    if sale.installation_notes:
        elements.append(Paragraph("Observações da instalação", s["h2"]))
        elements.append(Paragraph(sale.installation_notes, s["body"]))

    if invoices:
        elements.append(Paragraph("Faturamento e cobrança", s["h2"]))
        rows = [["Fatura", "Status", "Valor", "Recebido", "Vencimento"]]
        for inv, paid_total in invoices:
            rows.append(
                [
                    inv.number or f"#{inv.id}",
                    INVOICE_STATUS_LABELS.get(inv.status, inv.status),
                    _money(inv.amount),
                    _money(paid_total),
                    inv.due_date.strftime("%d/%m/%Y") if inv.due_date else "—",
                ]
            )
        t = Table(rows, colWidths=[4 * cm, 3 * cm, 3 * cm, 3 * cm, 3 * cm])
        t.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, "#999999"),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ]
            )
        )
        elements.append(t)

    doc.build(elements)
    buf.seek(0)
    return buf
