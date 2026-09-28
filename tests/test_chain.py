"""Тести блоку, PoW, ланцюга і повної перевірки (включно з атаками)."""

import time
import pytest

from blockchain.wallet import Wallet
from blockchain.transaction import Transaction
from blockchain.chain import Blockchain, ChainParams
from blockchain.mining import mine_block
from blockchain.difficulty import adjust_difficulty


def build_chain_with_wallets(difficulty=2):
    alice, bob, miner = Wallet(), Wallet(), Wallet()
    chain = Blockchain(ChainParams(initial_difficulty=difficulty, adjustment_interval=10, target_block_time=1.0))
    return chain, alice, bob, miner


def mine_and_append(chain, txs, miner_address):
    block = mine_block(chain.build_candidate_block(txs, miner_address))
    ok, msg = chain.validate_new_block(block)
    assert ok, msg
    chain.append_block(block)
    return block


def test_genesis_block_is_deterministic():
    g1 = Blockchain(ChainParams(initial_difficulty=3)).blocks[0]
    g2 = Blockchain(ChainParams(initial_difficulty=3)).blocks[0]
    assert g1.hash() == g2.hash()


def test_mined_block_satisfies_difficulty():
    chain, _, _, miner = build_chain_with_wallets(difficulty=3)
    block = mine_block(chain.build_candidate_block([], miner.address))
    assert block.hash().startswith("000")


def test_balances_update_after_transaction():
    chain, alice, bob, miner = build_chain_with_wallets()
    mine_and_append(chain, [], miner.address)
    assert chain.get_balance(miner.address) == chain.params.mining_reward

    tx = Transaction(sender=miner.address, recipient=alice.address, amount=10, fee=1, nonce=0)
    tx.sign_with(miner)
    mine_and_append(chain, [tx], miner.address)

    assert chain.get_balance(alice.address) == 10
    assert chain.get_balance(miner.address) == chain.params.mining_reward * 2 - 10 - 1 + 1  # +комісія собі ж


def test_full_chain_validates_when_untouched():
    chain, alice, bob, miner = build_chain_with_wallets()
    mine_and_append(chain, [], miner.address)
    tx = Transaction(sender=miner.address, recipient=alice.address, amount=5, fee=0.1, nonce=0)
    tx.sign_with(miner)
    mine_and_append(chain, [tx], miner.address)

    ok, msg = chain.validate_full_chain()
    assert ok, msg


def test_attack_amount_tampering_detected_by_full_validation():
    """Атака: зміна суми в транзакції старого блоку — повна перевірка має це виявити."""
    chain, alice, bob, miner = build_chain_with_wallets()
    mine_and_append(chain, [], miner.address)
    tx = Transaction(sender=miner.address, recipient=alice.address, amount=5, fee=0.1, nonce=0)
    tx.sign_with(miner)
    mine_and_append(chain, [tx], miner.address)
    mine_and_append(chain, [], miner.address)  # ще один блок зверху

    chain.blocks[2].transactions[1].amount = 9999  # підміна суми в старому блоці

    ok, msg = chain.validate_full_chain()
    assert not ok


def test_attack_recompute_hash_after_tampering_breaks_chain_link():
    """
    Атака: зловмисник змінює дані блоку І перераховує його власний хеш,
    щоб merkle_root і PoW цього блоку виглядали 'консистентними' —
    але це розриває зв'язок previous_hash із наступним блоком.
    """
    chain, alice, bob, miner = build_chain_with_wallets(difficulty=2)
    mine_and_append(chain, [], miner.address)
    tx = Transaction(sender=miner.address, recipient=alice.address, amount=5, fee=0.1, nonce=0)
    tx.sign_with(miner)
    mine_and_append(chain, [tx], miner.address)
    mine_and_append(chain, [], miner.address)

    tampered_block = chain.blocks[1]
    tampered_block.transactions[0].amount = 12345  # змінюємо coinbase у блоці 1
    remined = mine_block(tampered_block)  # зловмисник перемайновує цей самий блок
    chain.blocks[1] = remined

    ok, msg = chain.validate_full_chain()
    assert not ok  # previous_hash блоку #2 більше не відповідає новому хешу блоку #1


def test_attack_forged_signature_rejected():
    chain, alice, bob, miner = build_chain_with_wallets()
    mine_and_append(chain, [], miner.address)

    tx = Transaction(sender=miner.address, recipient=alice.address, amount=5, fee=0.1, nonce=0)
    tx.public_key = miner.public_key
    tx.signature = "ab" * 64  # підроблений підпис

    candidate = chain.build_candidate_block([tx], miner.address)
    mined = mine_block(candidate)
    ok, msg = chain.validate_new_block(mined)
    assert not ok
    assert "підпис" in msg.lower()


def test_attack_double_spend_within_same_block_rejected():
    """Атака: дві транзакції на весь баланс в одному блоці — друга має бути відхилена."""
    chain, alice, bob, miner = build_chain_with_wallets()
    mine_and_append(chain, [], miner.address)  # miner отримує 50

    reward = chain.params.mining_reward
    tx1 = Transaction(sender=miner.address, recipient=alice.address, amount=reward, fee=0, nonce=0)
    tx1.sign_with(miner)
    tx2 = Transaction(sender=miner.address, recipient=bob.address, amount=reward, fee=0, nonce=1)
    tx2.sign_with(miner)

    candidate = chain.build_candidate_block([tx1, tx2], miner.address)
    mined = mine_block(candidate)
    ok, msg = chain.validate_new_block(mined)
    assert not ok


def test_attack_replay_confirmed_transaction_rejected():
    chain, alice, bob, miner = build_chain_with_wallets()
    mine_and_append(chain, [], miner.address)
    tx = Transaction(sender=miner.address, recipient=alice.address, amount=5, fee=0.1, nonce=0)
    tx.sign_with(miner)
    mine_and_append(chain, [tx], miner.address)

    # той самий tx намагаються провести ще раз у наступному блоці
    candidate = chain.build_candidate_block([tx], miner.address)
    mined = mine_block(candidate)
    ok, msg = chain.validate_new_block(mined)
    assert not ok


def test_chain_save_and_load_roundtrip(tmp_path):
    chain, alice, bob, miner = build_chain_with_wallets()
    mine_and_append(chain, [], miner.address)
    tx = Transaction(sender=miner.address, recipient=alice.address, amount=5, fee=0.1, nonce=0)
    tx.sign_with(miner)
    mine_and_append(chain, [tx], miner.address)

    path = tmp_path / "chain.json"
    chain.save(str(path))
    loaded = Blockchain.load(str(path))

    assert loaded.height == chain.height
    assert loaded.get_balance(alice.address) == chain.get_balance(alice.address)
    ok, msg = loaded.validate_full_chain()
    assert ok, msg


def test_difficulty_increases_when_blocks_are_too_fast():
    # 10 блоків, кожен з інтервалом 0.01с при цілі 10с -> набагато швидше за очікуване
    blocks = []

    class FakeHeader:
        def __init__(self, index, timestamp, difficulty):
            self.index, self.timestamp, self.difficulty = index, timestamp, difficulty

    class FakeBlock:
        def __init__(self, header):
            self.header = header

    for i in range(11):
        blocks.append(FakeBlock(FakeHeader(i, i * 0.01, 3)))

    new_diff = adjust_difficulty(blocks, current_difficulty=3, adjustment_interval=10, target_block_time=10.0)
    assert new_diff == 4


def test_difficulty_decreases_when_blocks_are_too_slow():
    class FakeHeader:
        def __init__(self, index, timestamp, difficulty):
            self.index, self.timestamp, self.difficulty = index, timestamp, difficulty

    class FakeBlock:
        def __init__(self, header):
            self.header = header

    blocks = [FakeHeader.__new__(FakeHeader) for _ in range(0)]
    blocks = []
    for i in range(11):
        blocks.append(FakeBlock(FakeHeader(i, i * 100.0, 3)))  # набагато повільніше за ціль

    new_diff = adjust_difficulty(blocks, current_difficulty=3, adjustment_interval=10, target_block_time=10.0)
    assert new_diff == 2
