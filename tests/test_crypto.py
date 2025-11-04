import pytest

from app.utils.crypto import decrypt_password, encrypt_password


def test_encrypt_password_round_trip():
    password = "super-secret"

    encrypted = encrypt_password(password)
    assert encrypted != password

    decrypted = decrypt_password(encrypted)
    assert decrypted == password


@pytest.mark.parametrize("value", ["", "123456", "pässwörd"])
def test_encrypt_password_consistent(value: str):
    first = encrypt_password(value)
    second = encrypt_password(value)

    assert first != value
    assert second != value
    assert decrypt_password(first) == value
    assert decrypt_password(second) == value
