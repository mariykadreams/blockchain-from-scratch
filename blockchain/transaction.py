"""
Транзакція та її детермінована серіалізація.

Поля:
  sender     — адреса відправника (порожній рядок для coinbase-транзакції винагороди)
  recipient  — адреса отримувача
  amount     — сума переказу
  fee        — комісія, яку забирає майнер
  nonce      — порядковий номер транзакції ЦЬОГО відправника (0, 1, 2, ...)
  timestamp  — час створення (для інформації; на консенсус не впливає)
  public_key — публічний ключ відправника (потрібен для перевірки підпису
               без окремого реєстру користувачів)
  signature  — підпис над усіма попередніми полями
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from .crypto_utils import canonical_json, sha256_hex, verify_signature


COINBASE_SENDER = ""  # спеціальне значення відправника для винагороди за блок


@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: float
    fee: float = 0.0
    nonce: int = 0
    timestamp: float = field(default_factory=time.time)
    public_key: str = ""
    signature: Optional[str] = None

    # ---------- серіалізація ----------

    def _signing_payload(self) -> dict:
        """Усі поля транзакції, ОКРІМ самого підпису — те, що підписується."""
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "fee": self.fee,
            "nonce": self.nonce,
            "timestamp": self.timestamp,
            "public_key": self.public_key,
        }

    def signing_bytes(self) -> bytes:
        """Детерміновані байти, які підписуються і перевіряються."""
        return canonical_json(self._signing_payload())

    def to_dict(self) -> dict:
        d = self._signing_payload()
        d["signature"] = self.signature
        d["txid"] = self.txid()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        return cls(
            sender=d["sender"],
            recipient=d["recipient"],
            amount=d["amount"],
            fee=d.get("fee", 0.0),
            nonce=d.get("nonce", 0),
            timestamp=d.get("timestamp", 0.0),
            public_key=d.get("public_key", ""),
            signature=d.get("signature"),
        )

    def txid(self) -> str:
        """
        Ідентифікатор транзакції = хеш від (payload + підпис).
        Якщо підпис відсутній (coinbase), рахуємо тільки від payload.
        """
        base = self.signing_bytes()
        if self.signature:
            base += bytes.fromhex(self.signature) if _is_hex(self.signature) else self.signature.encode()
        return sha256_hex(base)

    # ---------- підпис / перевірка ----------

    def sign_with(self, wallet) -> None:
        """Підписати транзакцію гаманцем відправника."""
        self.public_key = wallet.public_key
        self.signature = wallet.sign(self.signing_bytes())

    def is_coinbase(self) -> bool:
        return self.sender == COINBASE_SENDER

    def verify_signature(self) -> bool:
        """Перевірити коректність підпису (без перевірки балансу/nonce — це робить мемпул)."""
        if self.is_coinbase():
            return self.signature is None
        if not self.signature or not self.public_key:
            return False
        # адреса відправника повинна відповідати наданому публічному ключу
        from .crypto_utils import hash_public_key_to_address
        expected_address = hash_public_key_to_address(bytes.fromhex(self.public_key))
        if expected_address != self.sender:
            return False
        return verify_signature(self.public_key, self.signing_bytes(), self.signature)

    @classmethod
    def coinbase(cls, recipient: str, amount: float) -> "Transaction":
        """Спеціальна транзакція винагороди майнеру. Без відправника і без підпису."""
        return cls(
            sender=COINBASE_SENDER,
            recipient=recipient,
            amount=amount,
            fee=0.0,
            nonce=0,
            timestamp=time.time(),
            public_key="",
            signature=None,
        )


def _is_hex(s: str) -> bool:
    try:
        int(s, 16)
        return len(s) % 2 == 0
    except ValueError:
        return False
