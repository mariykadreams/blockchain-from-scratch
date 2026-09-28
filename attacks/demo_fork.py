#!/usr/bin/env python3
"""
Демонстрація штучного розгалуження ланцюга (крок 6 методички).

Сценарій:
  1. Три вузли (A, B, C) синхронізовані й мають однаковий ланцюг.
  2. C "від'єднується" від мережі (не знайомий із A/B на момент майнінгу) —
     імітація розриву зв'язку.
  3. Майнимо блок на A -> він розповсюджується на B (вони й далі знайомі),
     але НЕ доходить до ізольованого C.
  4. У мемпул ізольованого C кладемо звичайну (підписану) транзакцію і
     майнимо нею блок на C -> з'являється конкурентна гілка тієї ж висоти.
  5. Майнимо ще один блок на A/B -> їхня гілка стає "важчою" (більше
     сумарної Proof-of-Work роботи), хоча в C теж лише на 1 блок менше.
  6. "Підключаємо" C назад (реєструємо сусідів) і викликаємо /nodes/resolve.
     C бачить, що ланцюг A/B важчий, приймає його, а транзакцію зі свого
     "програного" блоку повертає в мемпул.

Запуск: спершу підняти три вузли (див. README), потім
    python3 attacks/demo_fork.py
"""

import sys
import time
import requests

sys.path.insert(0, ".")
from blockchain.crypto_utils import KeyPair
from blockchain.transaction import Transaction

A = "http://localhost:5001"
B = "http://localhost:5002"
C = "http://localhost:5003"


def get(url):
    r = requests.get(url)
    r.raise_for_status()
    return r.json()


def post(url, json=None):
    return requests.post(url, json=json or {})


class RemoteWallet:
    """Локальна пара ключів, яку ми самі згенерували (не через /wallet/new вузла)."""

    def __init__(self):
        self.keypair = KeyPair.generate()

    @property
    def address(self):
        return self.keypair.address

    @property
    def public_key(self):
        return self.keypair.public_hex

    def sign(self, message: bytes) -> str:
        return self.keypair.sign(message)


def main():
    print("=== Демонстрація розгалуження ланцюга ===\n")

    for n in (A, B, C):
        try:
            get(f"{n}/health")
        except Exception:
            print(f"Вузол {n} недоступний. Спочатку запустіть три вузли (див. README).")
            sys.exit(1)

    print("1) Початковий стан (усі вузли синхронізовані):")
    for n in (A, B, C):
        print(f"   {n}: {get(f'{n}/chain/height')}")

    miner_a = RemoteWallet()
    miner_c = RemoteWallet()
    victim = RemoteWallet()

    print("\n2) Вузол C ізольований від мережі (не зареєстрований як сусід A/B, і навпаки).")

    print("\n3) Майнимо блок на вузлі A (розповсюдиться на B, бо вони з'єднані):")
    r = post(f"{A}/mine", {"miner_address": miner_a.address})
    print("   успіх:", r.json().get("mined"), "-> висота A:", get(f'{A}/chain/height')['height'])
    time.sleep(1)
    print("   висота B після трансляції:", get(f'{B}/chain/height')['height'])
    print("   висота C (ізольований, блок не дійшов):", get(f'{C}/chain/height')['height'])

    print("\n   Даємо C намайнити один блок, щоб у miner_c з'явився баланс для транзакції:")
    post(f"{C}/mine", {"miner_address": miner_c.address})
    bal = get(f"{C}/balance/{miner_c.address}")
    print("   баланс miner_c на C:", bal["balance"])

    tx = Transaction(sender=miner_c.address, recipient=victim.address, amount=5, fee=0.1,
                      nonce=bal["next_nonce"])
    tx.sign_with(miner_c)
    resp = post(f"{C}/transactions/new", tx.to_dict())
    print("   демонстраційна транзакція в мемпул C:", resp.status_code, resp.json())

    print("\n4) Майнимо на ізольованому C блок, що включає цю транзакцію:")
    r = post(f"{C}/mine", {"miner_address": miner_c.address})
    print("   успіх:", r.json().get("mined"), "-> висота C:", get(f'{C}/chain/height')['height'])

    print("\n   Тепер A/B мають один ланцюг, C — інший, приблизно тієї ж довжини:")
    for n, name in ((A, "A"), (B, "B"), (C, "C")):
        h = get(f"{n}/chain/height")
        print(f"   {name}: height={h['height']} work={h['total_work']}")

    print("\n5) Домайновуємо на A, доки гілка A/B не стане важчою за роботою за гілку C:")
    while get(f"{A}/chain/height")["total_work"] <= get(f"{C}/chain/height")["total_work"]:
        post(f"{A}/mine", {"miner_address": miner_a.address})
        time.sleep(0.3)
    print("   висота A:", get(f'{A}/chain/height')['height'], " висота C:", get(f'{C}/chain/height')['height'])

    print("\n6) 'Підключаємо' C назад до мережі (реєструємо сусідів) і викликаємо /nodes/resolve на C:")
    post(f"{C}/nodes/register", {"peers": [A, B]})
    post(f"{A}/nodes/register", {"peers": [C]})
    post(f"{B}/nodes/register", {"peers": [C]})
    r = post(f"{C}/nodes/resolve")
    print("   ", r.json())

    print("\n7) Фінальний стан — усі вузли на одному (найважчому) ланцюзі:")
    for n, name in ((A, "A"), (B, "B"), (C, "C")):
        print(f"   {name}: {get(f'{n}/chain/height')}")

    pending_c = get(f"{C}/transactions/pending")
    print(f"\n8) Мемпул C після реорганізації (має містити повернуту транзакцію): "
          f"{len(pending_c)} транз.")
    for t in pending_c:
        print(f"   {t['txid'][:12]}...  {t['sender'][:10]}... -> {t['recipient'][:10]}...  {t['amount']}")

    print("\nВисновок: транзакція з 'програного' блоку C не зникла — вона повернулась у мемпул "
          "і буде включена в один із наступних блоків.")


if __name__ == "__main__":
    main()
