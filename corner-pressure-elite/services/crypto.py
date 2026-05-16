"""
Cifragem de credenciais at-rest com AES-GCM.

A chave vem do env var `BOT_CRED_KEY` (32 bytes base64). Gere uma com:

    python3 -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"

E adicione ao `.env` do api e do bot (depois também).

Decisão arquitetural: a chave fica no env por simplicidade no MVP. Roadmap pós-go-live:
mover para Cloud KMS / Vault para evitar que vazamento de `.env` comprometa todas as
credenciais.

NUNCA logar plaintext. NUNCA expor pela API a username/password — só retornar
metadados (bet_house, last_validated_at, status).
"""

import base64
import logging
import os
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("CPES.Crypto")


class CredentialCipherError(Exception):
    """Erro relacionado à cifragem (chave ausente, formato inválido, descriptografia falhou)."""


@dataclass
class EncryptedBlob:
    """Resultado de uma cifragem: ciphertext + nonce. Persistir os dois lado a lado."""
    ciphertext: bytes
    nonce: bytes


def _load_key() -> bytes:
    key_b64 = os.environ.get("BOT_CRED_KEY", "").strip()
    if not key_b64:
        raise CredentialCipherError(
            "BOT_CRED_KEY ausente do ambiente. "
            "Gere uma com `python3 -c \"import base64,os; print(base64.b64encode(os.urandom(32)).decode())\"`"
        )
    try:
        key = base64.b64decode(key_b64)
    except Exception as e:
        raise CredentialCipherError(f"BOT_CRED_KEY não é base64 válido: {e}") from e
    if len(key) != 32:
        raise CredentialCipherError(
            f"BOT_CRED_KEY deve ter 32 bytes após decode (256 bits); tem {len(key)}."
        )
    return key


class CredentialCipher:
    """Cifragem AES-GCM autenticada (AEAD).

    Cada cifragem usa um nonce aleatório de 12 bytes. O nonce DEVE ser persistido
    junto com o ciphertext (não secret — só não pode repetir com a mesma chave).
    """

    def __init__(self, key: Optional[bytes] = None):
        self._key = key or _load_key()
        self._aes = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> EncryptedBlob:
        if not isinstance(plaintext, str):
            raise CredentialCipherError("plaintext precisa ser str")
        nonce = os.urandom(12)
        ct = self._aes.encrypt(nonce, plaintext.encode("utf-8"), None)
        return EncryptedBlob(ciphertext=ct, nonce=nonce)

    def decrypt(self, ciphertext: bytes, nonce: bytes) -> str:
        try:
            pt = self._aes.decrypt(nonce, ciphertext, None)
            return pt.decode("utf-8")
        except Exception as e:
            # Não logamos o ciphertext nem o nonce — só o tipo de erro
            logger.warning(f"[CredentialCipher] decrypt falhou: {type(e).__name__}")
            raise CredentialCipherError("Descriptografia falhou (chave errada ou dados corrompidos)") from e


# Singleton lazy — só inicializa quando alguém pede, pra não falhar import sem BOT_CRED_KEY
_singleton: Optional[CredentialCipher] = None


def get_cipher() -> CredentialCipher:
    global _singleton
    if _singleton is None:
        _singleton = CredentialCipher()
    return _singleton
