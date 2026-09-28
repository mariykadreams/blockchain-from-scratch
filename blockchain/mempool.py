"""
Мемпул — черга непідтверджених транзакцій.

Перед тим як транзакція потрапить у чергу, вона проходить чотири
перевірки (крок 2 методички):
  1) підпис коректний;
  2) у відправника вистачає коштів — З УРАХУВАННЯМ транзакцій, які
     від нього ж уже лежать у черзі (інакше можна двічі витратити ті
     самі гроші, просто відправивши дві транзакції поспіль);
  3) nonce правильний — рівно наступний після останнього підтвердженого
     АБО вже поставленого в чергу від цього відправника;
  4) такої транзакції ще немає ні в черзі, ні в ланцюзі (захист від
     повторного надсилання / replay).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .transaction import Transaction


class TransactionRejected(Exception):
    """Транзакція не пройшла одну з перевірок мемпула."""
    pass


@dataclass
class PendingState:
    """Проміжний стан (баланс + очікуваний nonce) з урахуванням черги."""
    balance: float
    next_nonce: int


class Mempool:
    def __init__(self):
        # txid -> Transaction
        self._pool: Dict[str, Transaction] = {}
        # sender -> список txid у порядку надходження (для впорядкованого mining)
        self._by_sender: Dict[str, List[str]] = {}

    def __len__(self):
        return len(self._pool)

    def __contains__(self, txid: str):
        return txid in self._pool

    def get(self, txid: str) -> Optional[Transaction]:
        return self._pool.get(txid)

    def all_transactions(self) -> List[Transaction]:
        return list(self._pool.values())

    def _pending_outflow(self, sender: str, exclude_txid: str = None) -> float:
        total = 0.0
        for txid in self._by_sender.get(sender, []):
            if txid == exclude_txid:
                continue
            tx = self._pool[txid]
            total += tx.amount + tx.fee
        return total

    def _pending_max_nonce(self, sender: str) -> Optional[int]:
        nonces = [self._pool[txid].nonce for txid in self._by_sender.get(sender, [])]
        return max(nonces) if nonces else None

    def add_transaction(self, tx: Transaction, chain) -> str:
        """
        Спробувати додати транзакцію в мемпул.
        `chain` — об'єкт Blockchain, потрібен для отримання підтвердженого
        балансу/nonce відправника.
        Повертає txid у разі успіху, інакше кидає TransactionRejected
        із людяним поясненням причини (як і вимагає методичка).
        """
        txid = tx.txid()

        # 4) дублікати — у черзі або вже в ланцюзі
        if txid in self._pool:
            raise TransactionRejected(f"Транзакція {txid[:12]}... вже є в мемпулі")
        if chain.transaction_exists(txid):
            raise TransactionRejected(
                f"Транзакція {txid[:12]}... вже підтверджена в ланцюзі (повторне надсилання)"
            )

        # 1) підпис
        if not tx.verify_signature():
            raise TransactionRejected("Некоректний підпис транзакції")

        # 2) і 3) баланс і nonce — з урахуванням черги
        confirmed_balance = chain.get_balance(tx.sender)
        confirmed_next_nonce = chain.get_next_nonce(tx.sender)

        pending_max_nonce = self._pending_max_nonce(tx.sender)
        expected_nonce = (pending_max_nonce + 1) if pending_max_nonce is not None else confirmed_next_nonce

        if tx.nonce != expected_nonce:
            raise TransactionRejected(
                f"Неправильний nonce: очікувався {expected_nonce}, отримано {tx.nonce}"
            )

        pending_outflow = self._pending_outflow(tx.sender)
        available = confirmed_balance - pending_outflow
        needed = tx.amount + tx.fee
        if needed > available + 1e-12:
            raise TransactionRejected(
                f"Недостатньо коштів: потрібно {needed}, доступно {available} "
                f"(баланс {confirmed_balance}, вже в черзі {pending_outflow})"
            )

        self._pool[txid] = tx
        self._by_sender.setdefault(tx.sender, []).append(txid)
        return txid

    def remove(self, txid: str) -> None:
        tx = self._pool.pop(txid, None)
        if tx is None:
            return
        lst = self._by_sender.get(tx.sender, [])
        if txid in lst:
            lst.remove(txid)
        if not lst:
            self._by_sender.pop(tx.sender, None)

    def remove_many(self, txids) -> None:
        for txid in txids:
            self.remove(txid)

    def return_transactions(self, txs: List[Transaction], chain) -> None:
        """
        Повернути транзакції з відкинутого (програного у розгалуженні) блоку
        назад у мемпул. Пропускаємо ті, що вже присутні або вже підтверджені
        деінде (наприклад, у новому ланцюзі, на який щойно перемкнулись),
        а також coinbase-транзакції (винагороду майнера повертати не треба —
        вона не є транзакцією користувача).
        """
        for tx in txs:
            if tx.is_coinbase():
                continue
            txid = tx.txid()
            if txid in self._pool or chain.transaction_exists(txid):
                continue
            try:
                self.add_transaction(tx, chain)
            except TransactionRejected:
                # якщо після повернення на новий ланцюг транзакція вже
                # не валідна (наприклад, конфліктний nonce) — просто губимо її,
                # це очікувана поведінка при реорганізації ланцюга
                continue

    def select_for_block(self, max_count: int = None) -> List[Transaction]:
        """Вибрати транзакції для нового блоку (за замовчуванням — усі, FIFO)."""
        txs = list(self._pool.values())
        if max_count is not None:
            txs = txs[:max_count]
        return txs
