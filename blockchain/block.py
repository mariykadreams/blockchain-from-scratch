"""
Блок = заголовок + список транзакцій.

Заголовок містить:
  index          — номер блоку (0 для генезис-блоку)
  timestamp      — мітка часу створення блоку
  previous_hash  — хеш попереднього блоку
  merkle_root    — корінь Меркла над транзакціями блоку
  difficulty     — поточна складність (кількість нулів на початку хешу)
  nonce          — число, яке підбирає майнер під час Proof of Work

Хеш блоку = SHA-256 від канонічної серіалізації заголовка.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List

from .crypto_utils import canonical_json, sha256_hex
from .transaction import Transaction
from .merkle import merkle_root


@dataclass
class BlockHeader:
    index: int
    timestamp: float
    previous_hash: str
    merkle_root: str
    difficulty: int
    nonce: int = 0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "difficulty": self.difficulty,
            "nonce": self.nonce,
        }

    def hash_bytes(self) -> bytes:
        return canonical_json(self.to_dict())

    def hash(self) -> str:
        return sha256_hex(self.hash_bytes())

    @classmethod
    def from_dict(cls, d: dict) -> "BlockHeader":
        return cls(
            index=d["index"],
            timestamp=d["timestamp"],
            previous_hash=d["previous_hash"],
            merkle_root=d["merkle_root"],
            difficulty=d["difficulty"],
            nonce=d["nonce"],
        )


@dataclass
class Block:
    header: BlockHeader
    transactions: List[Transaction] = field(default_factory=list)

    def hash(self) -> str:
        return self.header.hash()

    def tx_hashes(self) -> List[str]:
        return [tx.txid() for tx in self.transactions]

    def recompute_merkle_root(self) -> None:
        self.header.merkle_root = merkle_root(self.tx_hashes())

    def meets_difficulty(self) -> bool:
        """Хеш блоку повинен починатись із `difficulty` шістнадцяткових нулів."""
        return self.hash().startswith("0" * self.header.difficulty)

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "transactions": [tx.to_dict() for tx in self.transactions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        header = BlockHeader.from_dict(d["header"])
        txs = [Transaction.from_dict(t) for t in d["transactions"]]
        return cls(header=header, transactions=txs)

    @classmethod
    def genesis(cls, difficulty: int = 4) -> "Block":
        """
        Генезис-блок однаковий для всіх вузлів: фіксовані значення
        (нульовий previous_hash, порожній список транзакцій, timestamp=0),
        щоб різні вузли, запущені окремо, отримали ІДЕНТИЧНИЙ перший блок.
        """
        header = BlockHeader(
            index=0,
            timestamp=0.0,
            previous_hash="0" * 64,
            merkle_root=merkle_root([]),
            difficulty=difficulty,
            nonce=0,
        )
        return cls(header=header, transactions=[])

    def __repr__(self):
        return f"Block(#{self.header.index}, hash={self.hash()[:12]}..., txs={len(self.transactions)})"
