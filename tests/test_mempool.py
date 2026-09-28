"""Тести мемпула: чотири перевірки — підпис, баланс, nonce, дублікати."""

import pytest

from blockchain.wallet import Wallet
from blockchain.transaction import Transaction
from blockchain.chain import Blockchain, ChainParams
from blockchain.mempool import Mempool, TransactionRejected
from blockchain.mining import mine_block


@pytest.fixture
def funded_chain_and_wallets():
    """Ланцюг з одним заздалегідь намайненим блоком, що дає Alice кошти."""
    alice = Wallet()
    bob = Wallet()
    chain = Blockchain(ChainParams(initial_difficulty=1))
    block = mine_block(chain.build_candidate_block([], alice.address))
    chain.append_block(block)
    return chain, alice, bob


def test_reject_invalid_signature(funded_chain_and_wallets):
    chain, alice, bob = funded_chain_and_wallets
    mempool = Mempool()
    tx = Transaction(sender=alice.address, recipient=bob.address, amount=1, fee=0, nonce=0)
    tx.public_key = alice.public_key
    tx.signature = "00" * 64  # завідомо невалідний підпис
    with pytest.raises(TransactionRejected):
        mempool.add_transaction(tx, chain)


def test_reject_insufficient_balance(funded_chain_and_wallets):
    chain, alice, bob = funded_chain_and_wallets
    mempool = Mempool()
    tx = Transaction(sender=alice.address, recipient=bob.address, amount=10_000, fee=0, nonce=0)
    tx.sign_with(alice)
    with pytest.raises(TransactionRejected):
        mempool.add_transaction(tx, chain)


def test_reject_wrong_nonce(funded_chain_and_wallets):
    chain, alice, bob = funded_chain_and_wallets
    mempool = Mempool()
    tx = Transaction(sender=alice.address, recipient=bob.address, amount=1, fee=0, nonce=5)  # має бути 0
    tx.sign_with(alice)
    with pytest.raises(TransactionRejected):
        mempool.add_transaction(tx, chain)


def test_reject_duplicate_transaction_in_pool(funded_chain_and_wallets):
    chain, alice, bob = funded_chain_and_wallets
    mempool = Mempool()
    tx = Transaction(sender=alice.address, recipient=bob.address, amount=1, fee=0, nonce=0)
    tx.sign_with(alice)
    mempool.add_transaction(tx, chain)
    with pytest.raises(TransactionRejected):
        mempool.add_transaction(tx, chain)  # та сама транзакція вдруге


def test_accepts_valid_transaction_and_accounts_for_pending_balance(funded_chain_and_wallets):
    chain, alice, bob = funded_chain_and_wallets
    mempool = Mempool()
    tx1 = Transaction(sender=alice.address, recipient=bob.address, amount=20, fee=0, nonce=0)
    tx1.sign_with(alice)
    mempool.add_transaction(tx1, chain)

    # друга транзакція від Аліси повинна врахувати те, що перша вже "забронювала" кошти
    tx2 = Transaction(sender=alice.address, recipient=bob.address, amount=1000, fee=0, nonce=1)
    tx2.sign_with(alice)
    with pytest.raises(TransactionRejected):
        mempool.add_transaction(tx2, chain)


def test_reject_replay_of_confirmed_transaction(funded_chain_and_wallets):
    """Повторне надсилання вже підтвердженої транзакції має відхилятись."""
    chain, alice, bob = funded_chain_and_wallets
    tx = Transaction(sender=alice.address, recipient=bob.address, amount=1, fee=0, nonce=0)
    tx.sign_with(alice)

    block = mine_block(chain.build_candidate_block([tx], alice.address))
    chain.append_block(block)

    mempool = Mempool()
    with pytest.raises(TransactionRejected):
        mempool.add_transaction(tx, chain)
