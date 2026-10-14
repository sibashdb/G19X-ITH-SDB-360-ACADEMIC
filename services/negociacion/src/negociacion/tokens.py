"""Tokens de invitación: opacos, de 256 bits; en la base solo se guarda su SHA-256 (spec §8.1)."""

import hashlib
import secrets


def hash_de(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def nuevo_token() -> tuple[str, str]:
    """(token para el enlace, hash para la base)."""
    token = secrets.token_urlsafe(32)
    return token, hash_de(token)
