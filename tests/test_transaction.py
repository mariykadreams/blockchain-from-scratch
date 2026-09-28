"""Тести гаманця, транзакції та детермінованої серіалізації."""

import pytest

from blockchain.wallet import Wallet
from blockchain.transaction import Transaction
from blockchain.crypto_utils import canonical_json


def test_wallet_address_derived_from_public_key():
    w = Wallet()
    from blockchain.crypto_utils import hash_public_key_to_address
    assert w.address == hash_public_key_to_address(w.keypair.verifying_key.to_string())


def test_signature_valid_for_correct_transaction():
    alice = Wallet()
    tx = Transaction(sender=alice.address, recipient="bob_address", amount=10, fee=0.1, nonce=0)
    tx.sign_with(alice)
    assert tx.verify_signature() is True


def test_signature_invalid_after_tampering_amount():
    alice = Wallet()
    tx = Transaction(sender=alice.address, recipient="bob_address", amount=10, fee=0.1, nonce=0)
    tx.sign_with(alice)
    tx.amount = 999  # підміна суми ПІСЛЯ підпису
    assert tx.verify_signature() is False


def test_signature_invalid_with_wrong_signer():
    alice = Wallet()
    mallory = Wallet()
    tx = Transaction(sender=alice.address, recipient="bob_address", amount=10, fee=0.1, nonce=0)
    # Mallory намагається підписати транзакцію від імені Аліси
    tx.public_key = mallory.public_key
    tx.signature = mallory.sign(tx.signing_bytes())
    assert tx.verify_signature() is False


def test_canonical_json_is_deterministic_regardless_of_key_order():
    d1 = {"b": 2, "a": 1, "c": {"y": 2, "x": 1}}
    d2 = {"a": 1, "c": {"x": 1, "y": 2}, "b": 2}
    assert canonical_json(d1) == canonical_json(d2)


def test_txid_changes_if_any_signed_field_changes():
    alice = Wallet()
    tx1 = Transaction(sender=alice.address, recipient="bob", amount=10, fee=0.1, nonce=0)
    tx1.sign_with(alice)
    txid1 = tx1.txid()

    tx2 = Transaction(sender=alice.address, recipient="bob", amount=10, fee=0.1, nonce=1)
    tx2.sign_with(alice)
    txid2 = tx2.txid()

    assert txid1 != txid2
