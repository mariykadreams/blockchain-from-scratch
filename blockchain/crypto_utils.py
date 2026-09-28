"""
Криптографічні примітиви, які використовуються в усьому проєкті.

Тут навмисно НЕ реалізовано власний SHA-256 чи ECDSA "з нуля" на рівні
математики еліптичних кривих — це прийнятні допоміжні бібліотеки
(hashlib — стандартна бібліотека Python, ecdsa — обгортка над
відомим і перевіреним алгоритмом підпису). Усе, що стосується власне
блокчейну (формат транзакції, дерево Меркла, блок, ланцюг, консенсус),
написано власноруч у відповідних модулях.
"""

import hashlib
import json
from typing import Any

from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError


def sha256(data: bytes) -> bytes:
    """Один прохід SHA-256 над байтами."""
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    """SHA-256 у вигляді hex-рядка (зручно для зберігання/друку)."""
    return hashlib.sha256(data).hexdigest()


def double_sha256_hex(data: bytes) -> str:
    """Подвійний SHA-256 (як у Bitcoin) — трохи ускладнює атаки на розширення довжини."""
    return hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()


def canonical_json(obj: Any) -> bytes:
    """
    Детермінована серіалізація довільного словника/списку в байти.

    Критично важливо для підписів: та сама логічна структура даних
    ЗАВЖДИ повинна перетворюватися на ту саму послідовність байтів,
    незалежно від вузла, порядку вставки ключів у словник тощо.
    Тому:
      - ключі сортуються (sort_keys=True);
      - прибираються зайві пробіли (separators);
      - non-ASCII символи не екранізуються спеціально, але це не впливає
        на детермінованість, бо ensure_ascii=True завжди дає однаковий результат.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def hash_public_key_to_address(public_key_bytes: bytes) -> str:
    """
    Адреса користувача = хеш його публічного ключа.
    Використовуємо SHA-256 від публічного ключа, представлений у hex.
    (У "справжніх" мережах додатково беруть RIPEMD-160 та Base58Check,
    але для навчальної реалізації достатньо одного хешу — ідея та сама:
    з хешу неможливо відновити публічний ключ.)
    """
    return sha256_hex(public_key_bytes)


class KeyPair:
    """Пара приватний/публічний ключ на кривій secp256k1 (ECDSA)."""

    def __init__(self, signing_key: SigningKey):
        self.signing_key = signing_key
        self.verifying_key: VerifyingKey = signing_key.get_verifying_key()

    @classmethod
    def generate(cls) -> "KeyPair":
        return cls(SigningKey.generate(curve=SECP256k1))

    @classmethod
    def from_private_hex(cls, private_hex: str) -> "KeyPair":
        sk = SigningKey.from_string(bytes.fromhex(private_hex), curve=SECP256k1)
        return cls(sk)

    @property
    def private_hex(self) -> str:
        return self.signing_key.to_string().hex()

    @property
    def public_hex(self) -> str:
        return self.verifying_key.to_string().hex()

    @property
    def address(self) -> str:
        return hash_public_key_to_address(self.verifying_key.to_string())

    def sign(self, message: bytes) -> str:
        """Підписати повідомлення (байти). Повертає підпис у hex."""
        signature = self.signing_key.sign_deterministic(message, hashfunc=hashlib.sha256)
        return signature.hex()


def verify_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """Перевірити підпис ECDSA над повідомленням за публічним ключем."""
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        return vk.verify(bytes.fromhex(signature_hex), message, hashfunc=hashlib.sha256)
    except (BadSignatureError, ValueError, Exception):
        return False
