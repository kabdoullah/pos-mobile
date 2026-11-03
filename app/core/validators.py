"""Validateurs partagés entre modules."""

import re

import phonenumbers
from phonenumbers import PhoneNumberType

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")

# Types acceptés pour un compte : il doit pouvoir recevoir SMS/WhatsApp.
_MOBILE_TYPES = {PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE}


def validate_e164(value: str) -> str:
    """Vérifie un numéro au format E.164 (ex. +2250700000000), ou lève ValueError."""
    if not _E164_RE.match(value):
        raise ValueError("Phone number must be in E.164 format (e.g. +2250700000000).")
    return value


def validate_mobile_number(value: str) -> str:
    """Vérifie qu'un numéro E.164 est un numéro mobile attribuable, ou lève ValueError.

    S'appuie sur les plans de numérotation de libphonenumber (indicatif, longueur,
    préfixes opérateurs). Ne prouve pas que l'utilisateur possède le numéro :
    seule une vérification OTP le peut.
    """
    validate_e164(value)
    parsed = phonenumbers.parse(value, None)
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Phone number does not exist (check the number of digits and prefix).")
    if phonenumbers.number_type(parsed) not in _MOBILE_TYPES:
        raise ValueError("Phone number must be a mobile number.")
    return value
