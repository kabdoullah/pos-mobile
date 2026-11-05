"""Tests de la validation stricte du numéro à l'inscription."""

import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import RegisterRequest


@pytest.mark.parametrize(
    "phone", ["+2250700000001", "+2250500000000", "+2250102030405", "+33612345678"]
)
def test_register_accepts_real_mobile_numbers(phone: str) -> None:
    assert (
        RegisterRequest(
            phone_number=phone, password="secret123", email="user@example.com"
        ).phone_number
        == phone
    )


@pytest.mark.parametrize(
    "phone",
    [
        "+225010101010",  # ancien format CI à 8 chiffres
        "+2250000000000",  # préfixe inexistant
        "+2251234567890",  # préfixe inexistant
        "+22507000000001",  # trop long
        "+2252721000000",  # ligne fixe : ne reçoit pas de SMS
        "0700000000",  # pas E.164
        "+2801234567",  # indicatif pays non attribué
    ],
)
def test_register_rejects_fake_numbers(phone: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(phone_number=phone, password="secret123", email="user@example.com")
