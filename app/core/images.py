"""Normalisation des images envoyées par les clients (ADR-0008).

Toute image (photo produit, logo) est ré-encodée en WebP avant stockage :
- type vérifié sur le contenu (magic bytes), pas sur l'extension ni l'en-tête ;
- taille brute limitée, et garde-fou contre les « bombes de décompression » ;
- orientation EXIF appliquée puis métadonnées supprimées (GPS du téléphone…) ;
- dimensions réduites (le mobile affiche des vignettes, l'imprimante 58 mm
  imprime 384 px de large).
"""

import hashlib
import io
from dataclasses import dataclass

from fastapi import Response
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import PayloadTooLargeError, ValidationError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
"""Taille brute maximale acceptée (5 Mo)."""

PRODUCT_IMAGE_MAX_SIDE = 512
"""Côté maximal d'une image produit (px)."""

LOGO_MAX_WIDTH = 384
"""Largeur maximale d'un logo : largeur d'impression d'une imprimante 58 mm."""

WEBP_CONTENT_TYPE = "image/webp"

_WEBP_QUALITY = 75
# Au-delà, l'image décodée occuperait trop de mémoire (bombe de décompression).
_MAX_PIXELS = 40_000_000

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class ProcessedImage:
    """Image normalisée, prête à être stockée."""

    content: bytes
    width: int
    height: int
    sha256: str
    content_type: str = WEBP_CONTENT_TYPE


def _has_supported_signature(raw: bytes) -> bool:
    """JPEG, PNG ou WebP (« RIFF » + taille + « WEBP »), d'après le contenu."""
    if raw.startswith((_JPEG_MAGIC, _PNG_MAGIC)):
        return True
    return raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"


def normalize_image(raw: bytes, *, max_width: int, max_height: int) -> ProcessedImage:
    """Valide et ré-encode [raw] en WebP, dans un cadre de max_width par max_height.

    Lève PayloadTooLargeError (413) au-delà de 5 Mo, ValidationError (422) si le
    fichier n'est pas une image JPEG, PNG ou WebP valide.
    """
    if len(raw) > MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError("Image too large (max 5 MB).", field="file")
    if not _has_supported_signature(raw):
        raise ValidationError("Unsupported image type (JPEG, PNG or WebP).", field="file")

    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > _MAX_PIXELS:
                raise ValidationError("Image dimensions too large.", field="file")
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            # Aucun paramètre exif/icc transmis : le fichier produit est vierge.
            image.save(output, format="WEBP", quality=_WEBP_QUALITY, method=4)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("Invalid image file.", field="file") from exc

    content = output.getvalue()
    return ProcessedImage(
        content=content,
        width=image.width,
        height=image.height,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def image_response(
    content: bytes, content_type: str, sha256: str, if_none_match: str | None
) -> Response:
    """Réponse HTTP d'une image, cachée longtemps côté client.

    L'ETag est le SHA-256 : une image ne change jamais sous une même version,
    d'où `immutable`. 304 si le client a déjà cette version.
    """
    etag = f'"{sha256}"'
    headers = {"ETag": etag, "Cache-Control": "private, max-age=31536000, immutable"}
    if if_none_match is not None and etag in {tag.strip() for tag in if_none_match.split(",")}:
        return Response(status_code=304, headers=headers)
    return Response(content=content, media_type=content_type, headers=headers)
