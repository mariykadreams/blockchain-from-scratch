"""
Ланцюг блоків: додавання блоків, підрахунок балансів, збереження/
завантаження з файлу та — найголовніше — повна перевірка ланцюга.

Стан балансів/nonce тримається у двох словниках, які перераховуються
"з нуля" під час full-валідації (щоб гарантовано не розійтися з
реальним вмістом блоків), а при звичайній роботі оновлюються інкрементно
для швидкості (append_block).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .block import Block, BlockHeader
from .transaction import Transaction
from .difficulty import adjust_difficulty

MINING_REWARD = 50.0


class ChainValidationError(Exception):
    """Блок або весь ланцюг не пройшли перевірку. Повідомлення пояснює причину."""
    pass


@dataclass
class ChainParams:
    initial_difficulty: int = 4
    adjustment_interval: int = 10
    target_block_time: float = 10.0
    mining_reward: float = MINING_REWARD
    min_difficulty: int = 1
    max_difficulty: int = 8


class Blockchain:
    def __init__(self, params: ChainParams = None):
        self.params = params or ChainParams()
        self.blocks: List[Block] = [Block.genesis(self.params.initial_difficulty)]
        self.balances: Dict[str, float] = {}
        self.next_nonce: Dict[str, int] = {}
        self._txid_index: set = set()  # усі txid, що коли-небудь входили в ланцюг
        self.current_difficulty = self.params.initial_difficulty

    # ---------------- базові геттери ----------------

    @property
    def height(self) -> int:
        return len(self.blocks) - 1

    @property
    def last_block(self) -> Block:
        return self.blocks[-1]

    def total_work(self) -> int:
        """
        Сумарна виконана робота ланцюга = сума 16^difficulty по всіх блоках.
        Використовується для вибору "найважчого" ланцюга при розгалуженні
        (а не просто найдовшого за кількістю блоків).
        """
        return sum(16 ** b.header.difficulty for b in self.blocks)

    def get_balance(self, address: str) -> float:
        return self.balances.get(address, 0.0)

    def get_next_nonce(self, address: str) -> int:
        return self.next_nonce.get(address, 0)

    def transaction_exists(self, txid: str) -> bool:
        return txid in self._txid_index

    # ---------------- побудова нового блоку ----------------

    def build_candidate_block(self, transactions: List[Transaction], miner_address: str) -> Block:
        fees = sum(tx.fee for tx in transactions)
        reward_tx = Transaction.coinbase(miner_address, self.params.mining_reward + fees)
        all_txs = [reward_tx] + list(transactions)

        header = BlockHeader(
            index=self.height + 1,
            timestamp=__import__("time").time(),
            previous_hash=self.last_block.hash(),
            merkle_root="",
            difficulty=self.current_difficulty,
            nonce=0,
        )
        block = Block(header=header, transactions=all_txs)
        block.recompute_merkle_root()
        return block

    # ---------------- застосування блоку до стану ----------------

    def _apply_block_to_state(self, block: Block) -> None:
        for tx in block.transactions:
            if tx.is_coinbase():
                self.balances[tx.recipient] = self.balances.get(tx.recipient, 0.0) + tx.amount
            else:
                self.balances[tx.sender] = self.balances.get(tx.sender, 0.0) - (tx.amount + tx.fee)
                self.balances[tx.recipient] = self.balances.get(tx.recipient, 0.0) + tx.amount
                self.next_nonce[tx.sender] = tx.nonce + 1
            self._txid_index.add(tx.txid())

    def append_block(self, block: Block) -> None:
        """Додати ВЖЕ перевірений блок (validate_new_block пройдено) і оновити стан."""
        self.blocks.append(block)
        self._apply_block_to_state(block)
        self.current_difficulty = adjust_difficulty(
            self.blocks,
            self.current_difficulty,
            self.params.adjustment_interval,
            self.params.target_block_time,
            self.params.min_difficulty,
            self.params.max_difficulty,
        )

    # ---------------- перевірка одного нового блоку (перед додаванням) ----------------

    def validate_new_block(self, block: Block) -> Tuple[bool, str]:
        """
        Перевірка кандидата на наступний блок відносно ПОТОЧНОГО стану
        ланцюга (використовується вузлом одразу після майнінгу або при
        отриманні блоку від сусіда, коли він продовжує наш активний ланцюг).
        """
        header = block.header

        if header.index != self.height + 1:
            return False, f"Неправильний номер блоку: очікувався {self.height + 1}, отримано {header.index}"

        if header.previous_hash != self.last_block.hash():
            return False, "previous_hash не збігається з хешем останнього блоку"

        if header.difficulty != self.current_difficulty:
            return False, f"Неправильна складність: очікувалась {self.current_difficulty}, отримано {header.difficulty}"

        if not block.meets_difficulty():
            return False, "Хеш блоку не задовольняє заявлену складність (Proof of Work не виконано)"

        expected_root = block.header.merkle_root
        block.recompute_merkle_root()
        if block.header.merkle_root != expected_root:
            return False, "Корінь Меркла не відповідає списку транзакцій"

        ok, msg = self._validate_block_transactions(block)
        if not ok:
            return False, msg

        return True, "OK"

    def _validate_block_transactions(self, block: Block) -> Tuple[bool, str]:
        if not block.transactions or not block.transactions[0].is_coinbase():
            return False, "Першою транзакцією блоку має бути винагорода майнеру (coinbase)"

        coinbase = block.transactions[0]
        fees_sum = sum(tx.fee for tx in block.transactions[1:])
        expected_reward = self.params.mining_reward + fees_sum
        if coinbase.amount > expected_reward + 1e-9:
            return False, (
                f"Винагорода майнера завищена: {coinbase.amount}, "
                f"максимум дозволено {expected_reward} (база {self.params.mining_reward} + комісії {fees_sum})"
            )

        for tx in block.transactions[1:]:
            if tx.is_coinbase():
                return False, "У блоці не може бути більше однієї coinbase-транзакції"

        # локальна симуляція балансів і nonce ЛИШЕ для транзакцій цього блоку,
        # щоб виявити внутрішні конфлікти (наприклад, подвійну витрату всередині
        # одного блоку), не чіпаючи основний self.balances до фактичного append
        sim_balances: Dict[str, float] = {}
        sim_next_nonce: Dict[str, int] = {}
        seen_txids = set()

        for tx in block.transactions[1:]:
            txid = tx.txid()
            if txid in seen_txids:
                return False, f"Дублікат транзакції {txid[:12]}... всередині блоку"
            if self.transaction_exists(txid):
                return False, f"Транзакція {txid[:12]}... вже підтверджена раніше (повторне надсилання)"
            seen_txids.add(txid)

            if not tx.verify_signature():
                return False, f"Некоректний підпис транзакції {txid[:12]}..."

            if tx.sender not in sim_balances:
                sim_balances[tx.sender] = self.get_balance(tx.sender)
            if tx.sender not in sim_next_nonce:
                sim_next_nonce[tx.sender] = self.get_next_nonce(tx.sender)

            if tx.nonce != sim_next_nonce[tx.sender]:
                return False, (
                    f"Неправильний nonce у транзакції {txid[:12]}...: "
                    f"очікувався {sim_next_nonce[tx.sender]}, отримано {tx.nonce}"
                )

            needed = tx.amount + tx.fee
            if needed > sim_balances[tx.sender] + 1e-9:
                return False, (
                    f"Подвійна витрата / нестача коштів у транзакції {txid[:12]}...: "
                    f"потрібно {needed}, доступно {sim_balances[tx.sender]}"
                )

            sim_balances[tx.sender] -= needed
            sim_balances[tx.recipient] = sim_balances.get(tx.recipient, self.get_balance(tx.recipient)) + tx.amount
            sim_next_nonce[tx.sender] = tx.nonce + 1

        return True, "OK"

    # ---------------- повна перевірка всього ланцюга (крок 5) ----------------

    def validate_full_chain(self) -> Tuple[bool, str]:
        """
        Повна перевірка ланцюга з нуля. Перевіряє геть усе, що вимагає
        методичка: коректність хешів і складності кожного блоку, зв'язність
        (previous_hash), корінь Меркла, усі підписи, послідовність nonce,
        відсутність витрат понад баланс і коректність винагороди майнера.

        Будь-яка зміна даних у вже доданому блоці (навіть одного байта в
        старій транзакції) обов'язково зламає або хеш блоку, або зв'язок
        із наступним блоком, або баланси — і буде виявлена тут.
        """
        if not self.blocks:
            return False, "Порожній ланцюг"

        genesis = self.blocks[0]
        expected_genesis = Block.genesis(self.params.initial_difficulty)
        if genesis.header.previous_hash != expected_genesis.header.previous_hash:
            return False, "Некоректний генезис-блок: previous_hash має бути 64 нулі"
        if genesis.transactions:
            return False, "Генезис-блок не повинен містити транзакцій"

        balances: Dict[str, float] = {}
        next_nonce: Dict[str, int] = {}
        txid_index: set = set()
        difficulty = self.params.initial_difficulty

        for i, block in enumerate(self.blocks):
            header = block.header

            if header.index != i:
                return False, f"Блок на позиції {i} має неправильний index={header.index}"

            if i == 0:
                if block.hash() != genesis.hash():
                    return False, "Хеш генезис-блоку відрізняється від еталонного"
            else:
                prev = self.blocks[i - 1]
                if header.previous_hash != prev.hash():
                    return False, (
                        f"Блок #{i}: previous_hash не збігається з хешем блоку #{i-1} "
                        f"(ланцюг розірвано — виявлено підміну даних)"
                    )

                if header.difficulty != difficulty:
                    return False, f"Блок #{i}: неправильна складність {header.difficulty}, очікувалась {difficulty}"

                if not block.meets_difficulty():
                    return False, f"Блок #{i}: хеш не задовольняє складність {header.difficulty} (Proof of Work не виконано)"

            expected_root = header.merkle_root
            block.recompute_merkle_root()
            if block.header.merkle_root != expected_root:
                return False, f"Блок #{i}: корінь Меркла не відповідає транзакціям (дані підмінено)"

            if i > 0:
                if not block.transactions or not block.transactions[0].is_coinbase():
                    return False, f"Блок #{i}: відсутня coinbase-транзакція"

                fees_sum = sum(tx.fee for tx in block.transactions[1:])
                expected_reward = self.params.mining_reward + fees_sum
                if block.transactions[0].amount > expected_reward + 1e-9:
                    return False, f"Блок #{i}: завищена винагорода майнеру"

                for tx in block.transactions[1:]:
                    txid = tx.txid()
                    if txid in txid_index:
                        return False, f"Блок #{i}: транзакція {txid[:12]}... вже зустрічалась раніше в ланцюзі"

                    if not tx.verify_signature():
                        return False, f"Блок #{i}: некоректний підпис транзакції {txid[:12]}..."

                    expected_n = next_nonce.get(tx.sender, 0)
                    if tx.nonce != expected_n:
                        return False, (
                            f"Блок #{i}: неправильний nonce у транзакції {txid[:12]}... "
                            f"(очікувався {expected_n}, отримано {tx.nonce})"
                        )

                    sender_balance = balances.get(tx.sender, 0.0)
                    needed = tx.amount + tx.fee
                    if needed > sender_balance + 1e-9:
                        return False, (
                            f"Блок #{i}: витрата понад баланс у транзакції {txid[:12]}... "
                            f"(потрібно {needed}, було {sender_balance})"
                        )

                    balances[tx.sender] = sender_balance - needed
                    balances[tx.recipient] = balances.get(tx.recipient, 0.0) + tx.amount
                    next_nonce[tx.sender] = tx.nonce + 1
                    txid_index.add(txid)

                # coinbase застосовуємо ПІСЛЯ перевірки звичайних транзакцій блоку
                cb = block.transactions[0]
                balances[cb.recipient] = balances.get(cb.recipient, 0.0) + cb.amount
                txid_index.add(cb.txid())

                if header.index != 0 and header.index % self.params.adjustment_interval == 0:
                    difficulty = adjust_difficulty(
                        self.blocks[: i + 1],
                        difficulty,
                        self.params.adjustment_interval,
                        self.params.target_block_time,
                        self.params.min_difficulty,
                        self.params.max_difficulty,
                    )

        return True, f"Ланцюг коректний: {len(self.blocks)} блоків, {len(txid_index)} транзакцій"

    def rebuild_state_from_blocks(self) -> None:
        """Перерахувати balances/next_nonce/txid_index/current_difficulty з нуля за self.blocks."""
        self.balances = {}
        self.next_nonce = {}
        self._txid_index = set()
        self.current_difficulty = self.params.initial_difficulty
        for i, block in enumerate(self.blocks):
            if i > 0:
                self._apply_block_to_state(block)
                if i % self.params.adjustment_interval == 0:
                    self.current_difficulty = adjust_difficulty(
                        self.blocks[: i + 1],
                        self.current_difficulty,
                        self.params.adjustment_interval,
                        self.params.target_block_time,
                        self.params.min_difficulty,
                        self.params.max_difficulty,
                    )

    # ---------------- заміна ланцюга (для консенсусу вузлів) ----------------

    def replace_chain(self, new_blocks: List[Block]) -> Tuple[bool, str, List[Transaction]]:
        """
        Спробувати замінити поточний ланцюг на новий (довший за сумарною
        роботою). Повертає (успіх, повідомлення, транзакції_що_повертаються_в_мемпул).
        """
        old_blocks = self.blocks
        old_txids = {tx.txid() for b in old_blocks for tx in b.transactions if not tx.is_coinbase()}

        candidate = Blockchain(self.params)
        candidate.blocks = new_blocks
        ok, msg = candidate.validate_full_chain()
        if not ok:
            return False, f"Новий ланцюг не пройшов перевірку: {msg}", []

        if candidate.total_work() <= self.total_work():
            return False, "Новий ланцюг не має більшої сумарної роботи — заміна не потрібна", []

        candidate.rebuild_state_from_blocks()

        new_txids = {tx.txid() for b in new_blocks for tx in b.transactions if not tx.is_coinbase()}
        returned_txids = old_txids - new_txids
        returned_txs = [
            tx for b in old_blocks for tx in b.transactions
            if not tx.is_coinbase() and tx.txid() in returned_txids
        ]

        self.blocks = candidate.blocks
        self.balances = candidate.balances
        self.next_nonce = candidate.next_nonce
        self._txid_index = candidate._txid_index
        self.current_difficulty = candidate.current_difficulty

        return True, f"Ланцюг замінено, нова висота {self.height}", returned_txs

    # ---------------- серіалізація на диск ----------------

    def to_dict(self) -> dict:
        return {
            "params": self.params.__dict__,
            "current_difficulty": self.current_difficulty,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    def save(self, path: str) -> None:
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)  # атомарна заміна, щоб не пошкодити файл при падінні процесу

    @classmethod
    def load(cls, path: str) -> "Blockchain":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        params = ChainParams(**data["params"])
        chain = cls(params)
        chain.blocks = [Block.from_dict(b) for b in data["blocks"]]
        chain.current_difficulty = data.get("current_difficulty", params.initial_difficulty)
        chain.rebuild_state_from_blocks()
        return chain

    @classmethod
    def load_or_create(cls, path: str, params: ChainParams = None) -> "Blockchain":
        if os.path.exists(path):
            return cls.load(path)
        chain = cls(params)
        chain.save(path)
        return chain
