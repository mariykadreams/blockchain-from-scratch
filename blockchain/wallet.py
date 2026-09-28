"""Гаманець користувача: генерація ключів, адреса, збереження/завантаження."""

import json
import os

from .crypto_utils import KeyPair


class Wallet:
    def __init__(self, keypair: KeyPair = None):
        self.keypair = keypair or KeyPair.generate()

    @property
    def address(self) -> str:
        return self.keypair.address

    @property
    def public_key(self) -> str:
        return self.keypair.public_hex

    def sign(self, message: bytes) -> str:
        return self.keypair.sign(message)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "private_key": self.keypair.private_hex,
                "public_key": self.keypair.public_hex,
                "address": self.address,
            }, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(path, 0o600)  # приватний ключ — лише для власника файлу
        except OSError:
            pass

    @classmethod
    def load(cls, path: str) -> "Wallet":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(KeyPair.from_private_hex(data["private_key"]))

    def __repr__(self):
        return f"Wallet(address={self.address[:12]}...)"
