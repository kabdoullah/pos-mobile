"""Validateurs partagés entre modules."""

import re

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def validate_e164(value: str) -> str:
    """Vérifie un numéro au format E.164 (ex. +2250700000000), ou lève ValueError."""
    if not _E164_RE.match(value):
        raise ValueError("Phone number must be in E.164 format (e.g. +2250700000000).")
    return value
