"""Tests des images produit et du logo boutique (ADR-0008)."""

import hashlib
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.images import MAX_UPLOAD_BYTES
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.stores.models import Store

_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdGhhc2g"
_GPS_IFD = 0x8825
_MAKE_TAG = 0x010F


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _store(db: AsyncSession, email: str) -> tuple[User, Store]:
    user = User(
        email=email, password_hash=_DUMMY_HASH, phone_number=f"+225{abs(hash(email)) % 10**9:09d}"
    )
    db.add(user)
    await db.flush()
    store = Store(owner_id=user.id, name=f"Boutique {email}")
    db.add(store)
    await db.flush()
    await db.commit()
    return user, store


def _headers(user: User, store: Store) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, store.id)}"}


async def _product(db: AsyncSession, store: Store, updated_at: datetime | None = None) -> Product:
    product = Product(store_id=store.id, name="Coca", unit_price=Decimal("500"))
    if updated_at is not None:
        product.updated_at = updated_at
    db.add(product)
    await db.flush()
    await db.refresh(product)
    await db.commit()
    return product


def _jpeg_with_gps(width: int = 2000, height: int = 1500) -> bytes:
    """Photo de téléphone : grande, avec marque de l'appareil et position GPS."""
    image = Image.new("RGB", (width, height), (200, 30, 30))
    exif = image.getexif()
    exif[_MAKE_TAG] = "TestPhone"
    gps = exif.get_ifd(_GPS_IFD)
    gps[1] = "N"
    gps[2] = (5.0, 20.0, 0.0)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def _png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _file(content: bytes, name: str = "photo.jpg") -> dict[str, tuple[str, bytes, str]]:
    return {"file": (name, content, "application/octet-stream")}


# ---------------------------------------------------------------------------
# Image produit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_product_image_is_reencoded_resized_and_stripped(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "img-reencode@test.com")
    product = await _product(db_session, store)
    headers = _headers(user, store)

    raw = _jpeg_with_gps()
    assert Image.open(io.BytesIO(raw)).getexif().get_ifd(_GPS_IFD), "précondition : GPS présent"

    r = await client.put(f"/api/v1/products/{product.id}/image", files=_file(raw), headers=headers)
    assert r.status_code == 200
    version = r.json()["image_version"]
    assert version is not None

    r = await client.get(f"/api/v1/products/{product.id}/image", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/webp"
    assert r.headers["etag"] == f'"{version}"'
    assert "immutable" in r.headers["cache-control"]
    assert hashlib.sha256(r.content).hexdigest() == version

    stored = Image.open(io.BytesIO(r.content))
    assert stored.format == "WEBP"
    assert max(stored.size) == 512
    # Ratio conservé (2000 par 1500 → 512 par 384).
    assert stored.size == (512, 384)
    # Plus aucune métadonnée : ni marque de l'appareil, ni GPS.
    assert len(stored.getexif()) == 0
    assert "exif" not in stored.info


@pytest.mark.asyncio
async def test_product_image_etag_gives_304(client: AsyncClient, db_session: AsyncSession) -> None:
    user, store = await _store(db_session, "img-etag@test.com")
    product = await _product(db_session, store)
    headers = _headers(user, store)
    version = (
        await client.put(
            f"/api/v1/products/{product.id}/image", files=_file(_png(40, 40)), headers=headers
        )
    ).json()["image_version"]

    r = await client.get(
        f"/api/v1/products/{product.id}/image",
        headers={**headers, "If-None-Match": f'"{version}"'},
    )
    assert r.status_code == 304
    assert r.content == b""


@pytest.mark.asyncio
async def test_small_png_with_transparency_is_accepted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "img-png@test.com")
    product = await _product(db_session, store)
    headers = _headers(user, store)

    r = await client.put(
        f"/api/v1/products/{product.id}/image", files=_file(_png(100, 50)), headers=headers
    )
    assert r.status_code == 200
    content = (await client.get(f"/api/v1/products/{product.id}/image", headers=headers)).content
    # Petite image : jamais agrandie.
    assert Image.open(io.BytesIO(content)).size == (100, 50)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        b"%PDF-1.7 pas une image",
        b"\xff\xd8\xff" + b"faux jpeg" * 20,
        b"RIFF\x00\x00\x00\x00WAVEfmt ",
    ],
    ids=["pdf", "faux-jpeg", "riff-non-webp"],
)
async def test_non_images_are_rejected(
    client: AsyncClient, db_session: AsyncSession, content: bytes
) -> None:
    user, store = await _store(db_session, "img-reject@test.com")
    product = await _product(db_session, store)
    r = await client.put(
        f"/api/v1/products/{product.id}/image", files=_file(content), headers=_headers(user, store)
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_too_large_upload_is_413(client: AsyncClient, db_session: AsyncSession) -> None:
    user, store = await _store(db_session, "img-413@test.com")
    product = await _product(db_session, store)
    content = b"\xff\xd8\xff" + b"0" * MAX_UPLOAD_BYTES
    r = await client.put(
        f"/api/v1/products/{product.id}/image", files=_file(content), headers=_headers(user, store)
    )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_image_change_bumps_product_for_sync(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La nouvelle version arrive aux autres appareils via /sync/changes."""
    user, store = await _store(db_session, "img-sync@test.com")
    old = datetime.now(UTC) - timedelta(days=1)
    product = await _product(db_session, store, updated_at=old)
    headers = _headers(user, store)

    version = (
        await client.put(
            f"/api/v1/products/{product.id}/image", files=_file(_png(40, 40)), headers=headers
        )
    ).json()["image_version"]

    since = (old + timedelta(seconds=1)).isoformat()
    data = (
        await client.get("/api/v1/sync/changes", params={"since": since}, headers=headers)
    ).json()
    assert [p["image_version"] for p in data["products"]] == [version]


@pytest.mark.asyncio
async def test_delete_product_image(client: AsyncClient, db_session: AsyncSession) -> None:
    user, store = await _store(db_session, "img-delete@test.com")
    product = await _product(db_session, store)
    headers = _headers(user, store)
    await client.put(
        f"/api/v1/products/{product.id}/image", files=_file(_png(40, 40)), headers=headers
    )

    r = await client.delete(f"/api/v1/products/{product.id}/image", headers=headers)
    assert r.status_code == 204
    r = await client.get(f"/api/v1/products/{product.id}/image", headers=headers)
    assert r.status_code == 404
    r = await client.get(f"/api/v1/products/{product.id}", headers=headers)
    assert r.json()["image_version"] is None


@pytest.mark.asyncio
async def test_image_of_unknown_product_is_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "img-unknown@test.com")
    r = await client.put(
        "/api/v1/products/00000000-0000-4000-8000-000000000000/image",
        files=_file(_png(10, 10)),
        headers=_headers(user, store),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Isolation RLS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_cannot_read_or_replace_image_of_another_store(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_a, store_a = await _store(db_session, "img-rls-a@test.com")
    user_b, store_b = await _store(db_session, "img-rls-b@test.com")
    product_a = await _product(db_session, store_a)
    await client.put(
        f"/api/v1/products/{product_a.id}/image",
        files=_file(_png(40, 40)),
        headers=_headers(user_a, store_a),
    )

    headers_b = _headers(user_b, store_b)
    r = await client.get(f"/api/v1/products/{product_a.id}/image", headers=headers_b)
    assert r.status_code == 404
    r = await client.put(
        f"/api/v1/products/{product_a.id}/image", files=_file(_png(20, 20)), headers=headers_b
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_rls_hides_product_images_and_logos_of_other_stores(
    db_session: AsyncSession,
) -> None:
    _, store_a = await _store(db_session, "img-rls-sql-a@test.com")
    _, store_b = await _store(db_session, "img-rls-sql-b@test.com")
    product_b = await _product(db_session, store_b)
    await db_session.execute(
        text(
            "INSERT INTO product_images "
            "(product_id, store_id, content, content_type, width, height, sha256) "
            "VALUES (:pid, :sid, '\\x00', 'image/webp', 1, 1, 'x')"
        ),
        {"pid": str(product_b.id), "sid": str(store_b.id)},
    )
    await db_session.execute(
        text(
            "INSERT INTO store_logos (store_id, content, content_type, width, height, sha256) "
            "VALUES (:sid, '\\x00', 'image/webp', 1, 1, 'x')"
        ),
        {"sid": str(store_b.id)},
    )

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_a.id}'"))
    images = await db_session.execute(text("SELECT product_id FROM product_images"))
    logos = await db_session.execute(text("SELECT store_id FROM store_logos"))
    assert images.fetchall() == []
    assert logos.fetchall() == []


# ---------------------------------------------------------------------------
# Logo boutique
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_logo_upload_get_delete(client: AsyncClient, db_session: AsyncSession) -> None:
    user, store = await _store(db_session, "logo-flow@test.com")
    headers = _headers(user, store)

    # Logo large : ramené à la largeur d'impression 58 mm (384 px).
    r = await client.put("/api/v1/stores/me/logo", files=_file(_png(1000, 300)), headers=headers)
    assert r.status_code == 200
    version = r.json()["logo_version"]
    assert version is not None

    r = await client.get("/api/v1/stores/me", headers=headers)
    assert r.json()["logo_version"] == version

    r = await client.get("/api/v1/stores/me/logo", headers=headers)
    assert r.status_code == 200
    assert r.headers["etag"] == f'"{version}"'
    assert Image.open(io.BytesIO(r.content)).size == (384, 115)

    r = await client.delete("/api/v1/stores/me/logo", headers=headers)
    assert r.status_code == 204
    r = await client.get("/api/v1/stores/me/logo", headers=headers)
    assert r.status_code == 404
    r = await client.get("/api/v1/stores/me", headers=headers)
    assert r.json()["logo_version"] is None
