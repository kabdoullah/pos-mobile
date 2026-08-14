"""Tests unitaires du parsing d'import en masse (pas de DB)."""

import io
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.core.exceptions import ValidationError
from app.modules.catalog.bulk_import import (
    build_csv_template,
    build_xlsx_template,
    parse_bulk_import_file,
)


def _xlsx_bytes(rows: list[tuple]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_csv_comma_delimiter_dot_decimal() -> None:
    """CSV standard : virgule comme séparateur, point comme décimale."""
    content = b"name,barcode,unit_price,current_stock\nRiz,1234567890,3500.00,50\nHuile,,1500.50,\n"

    rows = parse_bulk_import_file("produits.csv", content)

    assert len(rows) == 2
    _, product0, error0 = rows[0]
    assert error0 is None
    assert product0 is not None
    assert product0.name == "Riz"
    assert product0.barcode == "1234567890"
    assert product0.unit_price == Decimal("3500.00")
    assert product0.current_stock == 50

    _, product1, error1 = rows[1]
    assert error1 is None
    assert product1 is not None
    assert product1.barcode is None
    assert product1.current_stock is None


def test_csv_semicolon_delimiter_comma_decimal() -> None:
    """Export Excel FR : point-virgule + virgule décimale (500,00)."""
    content = b"name;barcode;unit_price;current_stock\nSavon;6191234567890;500,00;120\n"

    rows = parse_bulk_import_file("produits_fr.csv", content)

    assert len(rows) == 1
    _, product, error = rows[0]
    assert error is None
    assert product is not None
    assert product.unit_price == Decimal("500.00")
    assert product.current_stock == 120


def test_csv_utf8_bom() -> None:
    """BOM UTF-8 ajouté par Excel -> décodage correct, pas de caractère parasite."""
    content = "﻿name,barcode,unit_price,current_stock\nCafé moulu,,2000.00,30\n".encode()

    rows = parse_bulk_import_file("produits.csv", content)

    assert len(rows) == 1
    _, product, error = rows[0]
    assert error is None
    assert product is not None
    assert product.name == "Café moulu"


def test_xlsx_typed_cells() -> None:
    """Cellules Excel déjà typées (int/float) -> pas de souci de séparateur décimal."""
    content = _xlsx_bytes(
        [
            ("name", "barcode", "unit_price", "current_stock"),
            ("Sucre", None, 800.0, 25),
        ]
    )

    rows = parse_bulk_import_file("produits.xlsx", content)

    assert len(rows) == 1
    _, product, error = rows[0]
    assert error is None
    assert product is not None
    assert product.unit_price == Decimal("800.0")
    assert product.current_stock == 25
    assert product.barcode is None


def test_invalid_unit_price_row_fails_without_raising() -> None:
    """Ligne avec unit_price non numérique -> cette ligne en échec, pas d'exception."""
    content = (
        b"name,barcode,unit_price,current_stock\nValide,,500.00,10\nInvalide,,pas-un-prix,10\n"
    )

    rows = parse_bulk_import_file("produits.csv", content)

    assert len(rows) == 2
    _, product0, error0 = rows[0]
    assert product0 is not None
    assert error0 is None

    _, product1, error1 = rows[1]
    assert product1 is None
    assert error1 is not None


def test_missing_required_name_fails_row_only() -> None:
    """name vide -> ligne en échec (validation Pydantic), pas d'exception globale."""
    content = b"name,barcode,unit_price,current_stock\n,,500.00,10\n"

    rows = parse_bulk_import_file("produits.csv", content)

    assert len(rows) == 1
    _, product, error = rows[0]
    assert product is None
    assert error is not None


def test_unsupported_extension_raises() -> None:
    """Extension non .csv/.xlsx -> ValidationError globale au fichier."""
    with pytest.raises(ValidationError):
        parse_bulk_import_file("produits.txt", b"name,unit_price\nA,1\n")


def test_file_too_large_raises() -> None:
    """Fichier > 5 Mo -> ValidationError avant même de tenter le parsing."""
    oversized = b"a" * (5 * 1024 * 1024 + 1)
    with pytest.raises(ValidationError):
        parse_bulk_import_file("produits.csv", oversized)


def test_csv_template_round_trips() -> None:
    """Le template CSV généré est lui-même un fichier valide pour le parser."""
    content = build_csv_template()

    rows = parse_bulk_import_file("template-import-produits.csv", content)

    assert len(rows) == 2
    for _, product, error in rows:
        assert error is None
        assert product is not None


def test_xlsx_template_round_trips() -> None:
    """Le template Excel généré est lui-même un fichier valide pour le parser."""
    content = build_xlsx_template()

    rows = parse_bulk_import_file("template-import-produits.xlsx", content)

    assert len(rows) == 2
    for _, product, error in rows:
        assert error is None
        assert product is not None
