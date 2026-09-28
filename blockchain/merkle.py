"""
Власна реалізація дерева Меркла.

Ідея: замість того, щоб зберігати в заголовку блоку хеш від усього
списку транзакцій одразу (що не дало б ефективного способу довести
входження ОДНІЄЇ транзакції без пред'явлення всіх інших), будуємо
бінарне дерево хешів знизу вгору:

  рівень 0: hash(tx_0), hash(tx_1), hash(tx_2), ...
  рівень 1: hash(h0+h1), hash(h2+h3), ...
  ...
  корінь:   один хеш, що залежить від УСІХ транзакцій і їхнього порядку.

Якщо на якомусь рівні непарна кількість хешів — останній хеш
дублюється, щоб можна було утворити пару (класичний підхід, як
у Bitcoin).
"""

from __future__ import annotations
from typing import List, Optional

from .crypto_utils import sha256_hex


def _hash_pair(left: str, right: str) -> str:
    return sha256_hex(bytes.fromhex(left) + bytes.fromhex(right))


def merkle_root(tx_hashes: List[str]) -> str:
    """
    Обчислити корінь Меркла зі списку хешів транзакцій (hex-рядки).
    Порожній список -> корінь із хешу порожнього рядка (щоб не було
    спеціального None-значення, яке довелось би окремо обробляти).
    """
    if not tx_hashes:
        return sha256_hex(b"")

    level = list(tx_hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])  # дублюємо останній хеш при непарній кількості
        level = [_hash_pair(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


class MerkleProof:
    """
    Доказ Меркла: шлях хешів-"братів" від листка до кореня плюс сторона
    (лівий/правий) кожного з них. Потрібен "легкому" клієнту (SPV), щоб
    переконатись, що конкретна транзакція входить у блок, маючи лише
    корінь Меркла із заголовка блоку — без завантаження всіх транзакцій.
    """

    def __init__(self, leaf_hash: str, path: List[tuple]):
        # path: список (sibling_hash, is_left_sibling)
        self.leaf_hash = leaf_hash
        self.path = path

    def verify(self, expected_root: str) -> bool:
        current = self.leaf_hash
        for sibling_hash, sibling_is_left in self.path:
            if sibling_is_left:
                current = _hash_pair(sibling_hash, current)
            else:
                current = _hash_pair(current, sibling_hash)
        return current == expected_root

    def to_dict(self) -> dict:
        return {"leaf_hash": self.leaf_hash, "path": self.path}

    @classmethod
    def from_dict(cls, d: dict) -> "MerkleProof":
        return cls(d["leaf_hash"], [tuple(p) for p in d["path"]])


def build_merkle_proof(tx_hashes: List[str], index: int) -> Optional[MerkleProof]:
    """Побудувати доказ Меркла для транзакції за індексом у списку хешів."""
    if not tx_hashes or index < 0 or index >= len(tx_hashes):
        return None

    leaf_hash = tx_hashes[index]
    level = list(tx_hashes)
    idx = index
    path = []

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        if idx % 2 == 0:
            sibling_index = idx + 1
            sibling_is_left = False  # брат праворуч від нас
        else:
            sibling_index = idx - 1
            sibling_is_left = True  # брат ліворуч від нас

        path.append((level[sibling_index], sibling_is_left))

        level = [_hash_pair(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        idx //= 2

    return MerkleProof(leaf_hash, path)
