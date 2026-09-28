"""Proof of Work: пошук nonce, при якому хеш блоку задовольняє складність."""

from __future__ import annotations
from typing import Optional

from .block import Block


class MiningAborted(Exception):
    """Майнінг перервано ззовні (наприклад, прийшов блок від іншого вузла)."""
    pass


def mine_block(block: Block, should_abort=None, max_nonce: int = 2**32) -> Optional[Block]:
    """
    Підбір nonce методом повного перебору — суть Proof of Work: єдиний
    практичний спосіб знайти підходящий nonce — це пробувати значення
    одне за одним, немає "розумнішого" шляху (в цьому й уся ідея
    "доказу виконаної роботи").

    `should_abort` — необов'язкова функція без аргументів; якщо вона
    повертає True, майнінг переривається (потрібно для мережевого
    сценарію: якщо сусідній вузол вже надіслав новий блок, немає сенсу
    продовжувати майнити застарілий).
    """
    block.recompute_merkle_root()
    header = block.header
    nonce = 0
    while nonce <= max_nonce:
        if should_abort is not None and nonce % 2000 == 0 and should_abort():
            raise MiningAborted()
        header.nonce = nonce
        if block.meets_difficulty():
            return block
        nonce += 1
    return None
