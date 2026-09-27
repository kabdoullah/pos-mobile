"""Schémas Pydantic du module stores."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validators import validate_e164

_NCC_MIN_LEN = 7
_NCC_MAX_LEN = 13


class StoreCreate(BaseModel):
    """Payload de création d'une boutique."""

    name: str = Field(..., min_length=1, max_length=255)
    address: str | None = None
    ncc: str | None = None
    vat_subject: bool = False
    receipt_footer_text: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=20)

    @field_validator("ncc")
    @classmethod
    def validate_ncc(cls, v: str | None) -> str | None:
        if v is not None and not (_NCC_MIN_LEN <= len(v) <= _NCC_MAX_LEN):
            raise ValueError("ncc must be between 7 and 13 characters")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return validate_e164(v) if v is not None else None


class StoreUpdate(BaseModel):
    """Payload de mise à jour partielle d'une boutique (PATCH)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    address: str | None = None
    ncc: str | None = None
    vat_subject: bool | None = None
    receipt_footer_text: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=20)

    @field_validator("ncc")
    @classmethod
    def validate_ncc(cls, v: str | None) -> str | None:
        if v is not None and not (_NCC_MIN_LEN <= len(v) <= _NCC_MAX_LEN):
            raise ValueError("ncc must be between 7 and 13 characters")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return validate_e164(v) if v is not None else None


class StoreResponse(BaseModel):
    """Représentation d'une boutique en lecture."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    address: str | None
    ncc: str | None
    vat_subject: bool
    receipt_footer_text: str | None
    phone: str | None = None
    # SHA-256 du logo (NULL sans logo) : clé de cache côté app.
    logo_version: str | None = None
    next_receipt_number: int
    created_at: datetime
    updated_at: datetime
