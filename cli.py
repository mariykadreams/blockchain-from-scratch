#!/usr/bin/env python3
"""
Консольний клієнт для керування вузлом (крок 7 методички).

Спілкується з локальним вузлом через його REST API, тобто його можна
запускати з будь-якого місця, знаючи лише адресу вузла (--node).

Команди:
  wallet-new [--out FILE]                    — створити гаманець
  wallet-info FILE                           — показати адресу гаманця
  send --wallet FILE --to ADDR --amount N [--fee N]
                                              — надіслати транзакцію
  mine --miner ADDR                          — намайнити блок
  chain                                      — показати ланцюг (стисло)
  balance ADDR                               — показати баланс
  validate                                   — перевірити ланцюг
  add-peer URL                               — додати сусіда
  peers                                      — список сусідів
  sync                                       — синхронізуватися з мережею
  pending                                    — показати мемпул
"""

import argparse
import json
import sys

import requests

from blockchain.wallet import Wallet
from blockchain.transaction import Transaction


def cmd_wallet_new(args):
    w = Wallet()
    if args.out:
        w.save(args.out)
        print(f"Гаманець збережено у {args.out}")
    print(f"Адреса: {w.address}")
    print(f"Публічний ключ: {w.public_key}")
    if not args.out:
        print(f"Приватний ключ (НЕ ПОШИРЮВАТИ): {w.keypair.private_hex}")


def cmd_wallet_info(args):
    w = Wallet.load(args.file)
    print(f"Адреса: {w.address}")
    print(f"Публічний ключ: {w.public_key}")


def cmd_send(args):
    w = Wallet.load(args.wallet)
    r = requests.get(f"{args.node}/balance/{w.address}")
    r.raise_for_status()
    info = r.json()
    tx = Transaction(
        sender=w.address,
        recipient=args.to,
        amount=args.amount,
        fee=args.fee,
        nonce=info["next_nonce"],
    )
    tx.sign_with(w)
    resp = requests.post(f"{args.node}/transactions/new", json=tx.to_dict())
    print(resp.status_code, resp.json())


def cmd_mine(args):
    resp = requests.post(f"{args.node}/mine", json={"miner_address": args.miner})
    data = resp.json()
    if resp.status_code == 201:
        block = data["block"]
        print(f"Намайновано блок #{block['header']['index']}, "
              f"транзакцій: {len(block['transactions'])}, nonce={block['header']['nonce']}")
    else:
        print("Помилка:", data)


def cmd_chain(args):
    resp = requests.get(f"{args.node}/chain")
    data = resp.json()
    for b in data["blocks"]:
        h = b["header"]
        print(f"#{h['index']:>3}  hash={_short(_block_hash(b))}  prev={_short(h['previous_hash'])}  "
              f"diff={h['difficulty']}  nonce={h['nonce']:<10}  txs={len(b['transactions'])}")


def _block_hash(block_dict):
    from blockchain.block import Block
    return Block.from_dict(block_dict).hash()


def _short(h):
    return h[:10] + "..."


def cmd_balance(args):
    resp = requests.get(f"{args.node}/balance/{args.address}")
    print(resp.json())


def cmd_validate(args):
    resp = requests.get(f"{args.node}/chain/validate")
    print(resp.json())


def cmd_add_peer(args):
    resp = requests.post(f"{args.node}/nodes/register", json={"peers": [args.url]})
    print(resp.json())


def cmd_peers(args):
    resp = requests.get(f"{args.node}/nodes")
    print(resp.json())


def cmd_sync(args):
    resp = requests.post(f"{args.node}/nodes/resolve")
    print(resp.json())


def cmd_pending(args):
    resp = requests.get(f"{args.node}/transactions/pending")
    for tx in resp.json():
        print(f"{tx['txid'][:12]}...  {tx['sender'][:10]}... -> {tx['recipient'][:10]}...  "
              f"{tx['amount']} (комісія {tx['fee']}, nonce {tx['nonce']})")


def main():
    parser = argparse.ArgumentParser(description="Консольний клієнт блокчейну")
    parser.add_argument("--node", default="http://localhost:5000", help="адреса вузла")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("wallet-new")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_wallet_new)

    p = sub.add_parser("wallet-info")
    p.add_argument("file")
    p.set_defaults(func=cmd_wallet_info)

    p = sub.add_parser("send")
    p.add_argument("--wallet", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--amount", type=float, required=True)
    p.add_argument("--fee", type=float, default=0.1)
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("mine")
    p.add_argument("--miner", required=True)
    p.set_defaults(func=cmd_mine)

    p = sub.add_parser("chain")
    p.set_defaults(func=cmd_chain)

    p = sub.add_parser("balance")
    p.add_argument("address")
    p.set_defaults(func=cmd_balance)

    p = sub.add_parser("validate")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("add-peer")
    p.add_argument("url")
    p.set_defaults(func=cmd_add_peer)

    p = sub.add_parser("peers")
    p.set_defaults(func=cmd_peers)

    p = sub.add_parser("sync")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("pending")
    p.set_defaults(func=cmd_pending)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
