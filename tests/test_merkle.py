"""Тести дерева Меркла: парна/непарна кількість елементів, доказ Меркла."""

import pytest

from blockchain.merkle import merkle_root, build_merkle_proof, _hash_pair
from blockchain.crypto_utils import sha256_hex


def test_merkle_root_single_element_equals_the_element_itself():
    h = sha256_hex(b"tx0")
    assert merkle_root([h]) == h


def test_merkle_root_even_number_of_elements():
    hashes = [sha256_hex(f"tx{i}".encode()) for i in range(4)]
    expected_level1 = [_hash_pair(hashes[0], hashes[1]), _hash_pair(hashes[2], hashes[3])]
    expected_root = _hash_pair(expected_level1[0], expected_level1[1])
    assert merkle_root(hashes) == expected_root


def test_merkle_root_odd_number_of_elements_duplicates_last_hash():
    hashes = [sha256_hex(f"tx{i}".encode()) for i in range(3)]
    # останній хеш дублюється, щоб утворити пару
    expected_level1 = [_hash_pair(hashes[0], hashes[1]), _hash_pair(hashes[2], hashes[2])]
    expected_root = _hash_pair(expected_level1[0], expected_level1[1])
    assert merkle_root(hashes) == expected_root


def test_merkle_root_changes_if_any_transaction_changes():
    hashes = [sha256_hex(f"tx{i}".encode()) for i in range(5)]
    root1 = merkle_root(hashes)
    hashes[2] = sha256_hex(b"tampered")
    root2 = merkle_root(hashes)
    assert root1 != root2


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8])
def test_merkle_proof_verifies_for_every_leaf(n):
    hashes = [sha256_hex(f"tx{i}".encode()) for i in range(n)]
    root = merkle_root(hashes)
    for i in range(n):
        proof = build_merkle_proof(hashes, i)
        assert proof.verify(root), f"доказ для листка {i} з {n} не пройшов перевірку"


def test_merkle_proof_fails_for_wrong_root():
    hashes = [sha256_hex(f"tx{i}".encode()) for i in range(5)]
    root = merkle_root(hashes)
    proof = build_merkle_proof(hashes, 2)
    wrong_root = sha256_hex(b"not the real root")
    assert not proof.verify(wrong_root)
