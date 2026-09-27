"""Génération du reçu PDF d'une vente (format ticket de caisse 80mm)."""

from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from app.modules.sales.models import Sale, SaleItem
from app.modules.stores.models import Store

_TZ_ABIDJAN = ZoneInfo("Africa/Abidjan")

_PAGE_WIDTH = 80 * mm
_MARGIN = 4 * mm
_LINE_HEIGHT = 4.5 * mm
_TOP_PADDING = 8 * mm
_BOTTOM_PADDING = 10 * mm
_CENTER_X = _PAGE_WIDTH / 2
# Logo : largeur maximale imprimée, hauteur plafonnée (logos très hauts).
_LOGO_MAX_WIDTH = 40 * mm
_LOGO_MAX_HEIGHT = 20 * mm


def _logo_size(logo: ImageReader) -> tuple[float, float]:
    """Dimensions imprimées du logo, ratio conservé, dans le cadre maximal."""
    width_px, height_px = logo.getSize()
    scale = min(_LOGO_MAX_WIDTH / width_px, _LOGO_MAX_HEIGHT / height_px)
    return width_px * scale, height_px * scale


_PAYMENT_METHOD_LABELS = {
    "cash": "Espèces",
    "mobile_money_orange": "Orange Money",
    "mobile_money_mtn": "MTN Money",
    "mobile_money_wave": "Wave",
    "mixed": "Mixte (Espèces + Mobile Money)",
}


def _fmt_amount(amount: Decimal) -> str:
    """Formate un montant FCFA avec espace comme séparateur de milliers, sans décimales."""
    return f"{amount:,.0f}".replace(",", " ") + " FCFA"


def _estimate_height(
    items: list[SaleItem],
    store: Store,
    logo: ImageReader | None,
    seller_name: str | None,
) -> float:
    lines = 6  # en-tête boutique + n° reçu + date
    if store.address:
        lines += 1
    if store.phone:
        lines += 1
    if store.ncc:
        lines += 1
    if seller_name:
        lines += 1
    lines += len(items) * 2  # chaque article : nom, puis qté x prix = total
    lines += 4  # séparateur + total + tva + moyen de paiement
    if store.receipt_footer_text:
        lines += 2
    logo_height = _logo_size(logo)[1] + _LINE_HEIGHT if logo is not None else 0.0
    return _TOP_PADDING + _BOTTOM_PADDING + lines * _LINE_HEIGHT + logo_height


def _draw_header(
    pdf: Canvas,
    sale: Sale,
    store: Store,
    y: float,
    logo: ImageReader | None,
    seller_name: str | None,
) -> float:
    if logo is not None:
        width, height = _logo_size(logo)
        pdf.drawImage(logo, _CENTER_X - width / 2, y - height, width, height, mask="auto")
        y -= height + _LINE_HEIGHT

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(_CENTER_X, y, store.name)
    y -= _LINE_HEIGHT

    pdf.setFont("Helvetica", 8)
    if store.address:
        pdf.drawCentredString(_CENTER_X, y, store.address)
        y -= _LINE_HEIGHT
    if store.phone:
        pdf.drawCentredString(_CENTER_X, y, f"Tél. {store.phone}")
        y -= _LINE_HEIGHT
    if store.ncc:
        pdf.drawCentredString(_CENTER_X, y, f"NCC: {store.ncc}")
        y -= _LINE_HEIGHT

    y -= _LINE_HEIGHT / 2
    pdf.setFont("Helvetica-Bold", 9)
    receipt_label = f"Reçu n° {sale.receipt_number}" if sale.receipt_number else "Reçu"
    pdf.drawCentredString(_CENTER_X, y, receipt_label)
    y -= _LINE_HEIGHT

    pdf.setFont("Helvetica", 8)
    local_created_at = sale.created_at.astimezone(_TZ_ABIDJAN)
    pdf.drawCentredString(_CENTER_X, y, local_created_at.strftime("%d/%m/%Y %H:%M"))
    y -= _LINE_HEIGHT
    if seller_name:
        pdf.drawCentredString(_CENTER_X, y, f"Vendeur : {seller_name}")
        y -= _LINE_HEIGHT

    y -= _LINE_HEIGHT / 2
    pdf.line(_MARGIN, y, _PAGE_WIDTH - _MARGIN, y)
    return y - _LINE_HEIGHT


def _draw_items(pdf: Canvas, items: list[SaleItem], y: float) -> float:
    pdf.setFont("Helvetica", 8)
    for item in items:
        pdf.drawString(_MARGIN, y, item.product_name_at_sale[:38])
        y -= _LINE_HEIGHT
        detail = f"  {item.quantity} x {_fmt_amount(item.unit_price_at_sale)}"
        pdf.drawString(_MARGIN, y, detail)
        pdf.drawRightString(_PAGE_WIDTH - _MARGIN, y, _fmt_amount(item.line_total))
        y -= _LINE_HEIGHT

    pdf.line(_MARGIN, y, _PAGE_WIDTH - _MARGIN, y)
    return y - _LINE_HEIGHT


def _draw_totals(pdf: Canvas, sale: Sale, store: Store, y: float) -> float:
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(_MARGIN, y, "TOTAL")
    pdf.drawRightString(_PAGE_WIDTH - _MARGIN, y, _fmt_amount(sale.total_amount))
    y -= _LINE_HEIGHT

    if store.vat_subject:
        pdf.setFont("Helvetica", 8)
        pdf.drawString(_MARGIN, y, "dont TVA")
        pdf.drawRightString(_PAGE_WIDTH - _MARGIN, y, _fmt_amount(sale.vat_amount))
        y -= _LINE_HEIGHT

    pdf.setFont("Helvetica", 8)
    payment_label = _PAYMENT_METHOD_LABELS.get(sale.payment_method, sale.payment_method)
    pdf.drawString(_MARGIN, y, f"Paiement: {payment_label}")
    y -= _LINE_HEIGHT

    if sale.payment_method == "mixed":
        pdf.drawString(_MARGIN, y, f"  Espèces: {_fmt_amount(sale.cash_amount or Decimal('0'))}")
        y -= _LINE_HEIGHT
        pdf.drawString(
            _MARGIN, y, f"  Mobile Money: {_fmt_amount(sale.mobile_money_amount or Decimal('0'))}"
        )
        y -= _LINE_HEIGHT

    return y


def build_receipt_pdf(
    sale: Sale,
    store: Store,
    *,
    logo: bytes | None = None,
    seller_name: str | None = None,
) -> bytes:
    """Génère le PDF d'un reçu de vente au format ticket de caisse (80mm de large).

    La hauteur de page s'adapte au nombre d'articles, comme un vrai rouleau
    d'imprimante thermique. [logo] : image WebP de la boutique (ADR-0008) ;
    [seller_name] : nom affiché du vendeur, s'il est connu.
    """
    logo_reader = ImageReader(BytesIO(logo)) if logo is not None else None
    height = _estimate_height(sale.items, store, logo_reader, seller_name)
    buffer = BytesIO()
    # Sans compression : reçus de quelques Ko, et contenu vérifiable en test.
    pdf = Canvas(buffer, pagesize=(_PAGE_WIDTH, height), pageCompression=0)

    y = height - _TOP_PADDING
    y = _draw_header(pdf, sale, store, y, logo_reader, seller_name)
    y = _draw_items(pdf, sale.items, y)
    y = _draw_totals(pdf, sale, store, y)

    if store.receipt_footer_text:
        y -= _LINE_HEIGHT / 2
        pdf.setFont("Helvetica-Oblique", 8)
        pdf.drawCentredString(_CENTER_X, y, store.receipt_footer_text)

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
