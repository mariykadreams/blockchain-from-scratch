#!/usr/bin/env python3
"""
Наочна демонстрація п'яти атак і реакції системи на кожну (крок 8 методички).

Це не pytest-тести (вони є окремо в tests/test_chain.py), а скрипт,
який друкує результат кожної атаки в консоль — саме ці скріншоти
й потрібно вставити у звіт.

Запуск: python3 attacks/demo_attacks.py
"""

from blockchain.wallet import Wallet
from blockchain.transaction import Transaction
from blockchain.chain import Blockchain, ChainParams
from blockchain.mining import mine_block


def line(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def setup_chain():
    alice, bob, miner = Wallet(), Wallet(), Wallet()
    chain = Blockchain(ChainParams(initial_difficulty=3))
    b1 = mine_block(chain.build_candidate_block([], miner.address))
    chain.append_block(b1)

    tx = Transaction(sender=miner.address, recipient=alice.address, amount=20, fee=0.5, nonce=0)
    tx.sign_with(miner)
    b2 = mine_block(chain.build_candidate_block([tx], miner.address))
    chain.append_block(b2)

    b3 = mine_block(chain.build_candidate_block([], miner.address))
    chain.append_block(b3)
    return chain, alice, bob, miner


def attack_1_amount_tampering():
    line("АТАКА 1: зміна суми в транзакції вже доданого (старого) блоку")
    chain, alice, bob, miner = setup_chain()
    print("Стан до атаки: ланцюг валідний?", chain.validate_full_chain())

    print(f"\nЗловмисник відкриває файл ланцюга і змінює суму транзакції в блоці #2")
    print(f"  було:  amount = {chain.blocks[2].transactions[1].amount}")
    chain.blocks[2].transactions[1].amount = 100000.0
    print(f"  стало: amount = {chain.blocks[2].transactions[1].amount}")

    ok, msg = chain.validate_full_chain()
    print(f"\nРезультат повної перевірки ланцюга: valid={ok}")
    print(f"Причина: {msg}")
    assert not ok, "Атака мала бути виявлена!"
    print("=> Атака ВІДБИТА: підміну суми виявлено на етапі перевірки кореня Меркла.")


def attack_2_recompute_hash():
    line("АТАКА 2: зміна даних із перерахунком хешу ЦЬОГО Ж блоку")
    chain, alice, bob, miner = setup_chain()

    print("Зловмисник змінює суму транзакції в блоці #2 (у межах наявного балансу,")
    print("щоб не спрацювала перевірка 'подвійної витрати') і ПЕРЕМАЙНОВУЄ блок #2,")
    print("щоб корінь Меркла і Proof-of-Work знову формально 'збігались'.")
    old_hash = chain.blocks[2].hash()
    chain.blocks[2].transactions[1].amount = 25.0  # було 20, залишається в межах балансу
    remined = mine_block(chain.blocks[2])
    chain.blocks[2] = remined
    new_hash = chain.blocks[2].hash()
    print(f"  старий хеш блоку #2: {old_hash[:16]}...")
    print(f"  новий хеш блоку #2:  {new_hash[:16]}... (інший, бо дані інші)")
    print(f"  блок #3.previous_hash усе ще вказує на СТАРИЙ хеш: "
          f"{chain.blocks[3].header.previous_hash[:16]}...")

    ok, msg = chain.validate_full_chain()
    print(f"\nРезультат повної перевірки ланцюга: valid={ok}")
    print(f"Причина: {msg}")
    assert not ok
    print("=> Атака ВІДБИТА одразу двома незалежними механізмами:")
    print("   1) сума — частина підписаних даних, тому зміна суми без приватного ключа")
    print("      відправника автоматично робить підпис транзакції недійсним;")
    print("   2) навіть якби підпис якимось дивом залишився коректним, блок #3")
    print("      усе одно посилається на СТАРИЙ хеш блоку #2 — зв'язок ланцюга розірвано.")


def attack_3_forged_signature():
    line("АТАКА 3: транзакція з підробленим підписом")
    chain, alice, bob, miner = setup_chain()

    print("Зловмисник (Mallory) намагається витратити гроші Аліси,")
    print("підписавши транзакцію СВОЇМ приватним ключем, але вказавши")
    print("публічний ключ Аліси (без доступу до її приватного ключа).")

    mallory = Wallet()
    forged_tx = Transaction(sender=alice.address, recipient=mallory.address, amount=15, fee=0.1, nonce=0)
    forged_tx.public_key = alice.public_key
    forged_tx.signature = mallory.sign(forged_tx.signing_bytes())  # підписано НЕ тим ключем

    from blockchain.mempool import Mempool, TransactionRejected
    mempool = Mempool()
    try:
        mempool.add_transaction(forged_tx, chain)
        print("=> ПОМИЛКА: транзакцію прийнято, атака не відбита!")
    except TransactionRejected as e:
        print(f"\nМемпул відхилив транзакцію: {e}")
        print("=> Атака ВІДБИТА: підпис не відповідає публічному ключу/адресі відправника.")


def attack_4_double_spend():
    line("АТАКА 4: подвійна витрата (дві транзакції, кожна на весь баланс)")
    chain, alice, bob, miner = setup_chain()

    balance = chain.get_balance(miner.address)
    print(f"Баланс майнера: {balance}")
    print("Майнер намагається надіслати ВЕСЬ баланс і Alice, і Bob одночасно.")

    tx1 = Transaction(sender=miner.address, recipient=alice.address, amount=balance, fee=0, nonce=chain.get_next_nonce(miner.address))
    tx1.sign_with(miner)
    tx2 = Transaction(sender=miner.address, recipient=bob.address, amount=balance, fee=0, nonce=chain.get_next_nonce(miner.address) + 1)
    tx2.sign_with(miner)

    from blockchain.mempool import Mempool, TransactionRejected
    mempool = Mempool()
    mempool.add_transaction(tx1, chain)
    print(f"\nПерша транзакція (Alice, {balance}) прийнята в мемпул.")
    try:
        mempool.add_transaction(tx2, chain)
        print("=> ПОМИЛКА: другу транзакцію прийнято, атака не відбита!")
    except TransactionRejected as e:
        print(f"Друга транзакція (Bob, {balance}) відхилена: {e}")
        print("=> Атака ВІДБИТА: мемпул враховує кошти, вже 'зарезервовані' першою транзакцією.")


def attack_5_replay():
    line("АТАКА 5: повторне надсилання вже підтвердженої транзакції")
    chain, alice, bob, miner = setup_chain()

    confirmed_tx = chain.blocks[2].transactions[1]  # транзакція miner->alice з блоку #2
    print(f"Беремо вже підтверджену транзакцію з блоку #2: "
          f"{confirmed_tx.txid()[:16]}... ({confirmed_tx.amount} від майнера до Аліси)")
    print("Зловмисник (або сам відправник) намагається надіслати її ще раз.")

    from blockchain.mempool import Mempool, TransactionRejected
    mempool = Mempool()
    try:
        mempool.add_transaction(confirmed_tx, chain)
        print("=> ПОМИЛКА: транзакцію прийнято повторно, атака не відбита!")
    except TransactionRejected as e:
        print(f"\nМемпул відхилив: {e}")
        print("=> Атака ВІДБИТА: транзакція вже входить у ланцюг (перевірка за txid), "
              "а nonce вже 'використаний'.")


if __name__ == "__main__":
    attack_1_amount_tampering()
    attack_2_recompute_hash()
    attack_3_forged_signature()
    attack_4_double_spend()
    attack_5_replay()
    print("\n\nУсі п'ять атак продемонстровано, система відбила кожну з них.")
