"""
Мережевий вузол: HTTP-сервер (Flask) + логіка спілкування із сусідами.

Кожен вузол — окремий процес на своєму порту. Вузли знають адреси
одне одного (список `peers`, наприклад ["http://localhost:5001"]).

Ендпоінти:
  GET  /chain                    — весь ланцюг (для синхронізації)
  GET  /chain/height             — висота і сумарна робота (легка перевірка "чи є щось нове")
  POST /transactions/new         — прийняти нову транзакцію (від клієнта або сусіда), розповсюдити далі
  GET  /transactions/pending     — вміст мемпула
  POST /mine                     — намайнити один блок із поточного мемпула
  POST /blocks/new               — прийняти новий блок від сусіда
  POST /nodes/register           — додати сусіда(-ів)
  GET  /nodes                    — список сусідів
  POST /nodes/resolve            — синхронізуватися з мережею (consensus): опитати сусідів,
                                    прийняти найважчий ланцюг
  GET  /balance/<address>        — баланс адреси
  GET  /wallet/new               — згенерувати новий гаманець (для зручності демонстрації)
  GET  /health                   — перевірка живості
"""

from __future__ import annotations

import argparse
import threading
import time
from typing import List, Set

import requests
from flask import Flask, jsonify, request

from .block import Block
from .chain import Blockchain, ChainParams, ChainValidationError
from .mempool import Mempool, TransactionRejected
from .transaction import Transaction
from .wallet import Wallet
from .merkle import build_merkle_proof, MerkleProof


class Node:
    def __init__(self, node_id: str, chain_path: str, params: ChainParams = None):
        self.node_id = node_id
        self.chain_path = chain_path
        self.chain = Blockchain.load_or_create(chain_path, params)
        self.mempool = Mempool()
        self.peers: Set[str] = set()
        self.lock = threading.RLock()

    # ---------------- транзакції ----------------

    def submit_transaction(self, tx: Transaction, broadcast: bool = True) -> str:
        with self.lock:
            txid = self.mempool.add_transaction(tx, self.chain)
        if broadcast:
            self._broadcast_transaction(tx)
        return txid

    def _broadcast_transaction(self, tx: Transaction) -> None:
        for peer in list(self.peers):
            try:
                requests.post(f"{peer}/transactions/new", json=tx.to_dict(), timeout=2,
                               headers={"X-From-Node": self.node_id})
            except requests.RequestException:
                pass  # сусід недоступний — не критично, синхронізується пізніше

    # ---------------- майнінг ----------------

    def mine_one_block(self, miner_address: str, max_txs: int = 50) -> Block:
        from .mining import mine_block

        with self.lock:
            txs = self.mempool.select_for_block(max_txs)
            candidate = self.chain.build_candidate_block(txs, miner_address)

        mined = mine_block(candidate)
        if mined is None:
            raise RuntimeError("Не вдалося намайнити блок (вичерпано nonce)")

        with self.lock:
            ok, msg = self.chain.validate_new_block(mined)
            if not ok:
                raise ChainValidationError(msg)
            self.chain.append_block(mined)
            self.mempool.remove_many([tx.txid() for tx in mined.transactions if not tx.is_coinbase()])
            self.chain.save(self.chain_path)

        self._broadcast_block(mined)
        return mined

    def _broadcast_block(self, block: Block) -> None:
        for peer in list(self.peers):
            try:
                requests.post(f"{peer}/blocks/new", json=block.to_dict(), timeout=2,
                               headers={"X-From-Node": self.node_id})
            except requests.RequestException:
                pass

    def receive_block(self, block: Block) -> dict:
        """
        Обробка блоку, який прислав сусід.
        Спочатку пробуємо додати його як пряме продовження нашого ланцюга.
        Якщо не підходить (наприклад, він посилається на блок, якого в нас
        немає, або наш ланцюг вже пішов далі) — просимо сусіда повний ланцюг
        і вирішуємо питання розгалуження через resolve_conflicts.
        """
        with self.lock:
            ok, msg = self.chain.validate_new_block(block)
            if ok:
                self.chain.append_block(block)
                self.mempool.remove_many([tx.txid() for tx in block.transactions if not tx.is_coinbase()])
                self.chain.save(self.chain_path)
                return {"accepted": True, "mode": "extended", "height": self.chain.height}

        # можливе розгалуження — перевіримо, чи не варто переключитись на довший ланцюг сусіда
        replaced = self.resolve_conflicts()
        return {"accepted": replaced["replaced"], "mode": "conflict_check", "detail": replaced}

    # ---------------- консенсус / синхронізація ----------------

    def resolve_conflicts(self) -> dict:
        """
        Опитати всіх сусідів, отримати їхні ланцюги і, якщо серед них є
        такий, що має БІЛЬШУ сумарну виконану роботу (не просто довший!)
        і проходить повну перевірку — перейти на нього.
        Транзакції з блоків, що "програли" (залишились у старому ланцюзі,
        але не увійшли в новий), повертаються в мемпул.
        """
        best_blocks = None
        best_work = self.chain.total_work()
        source = None

        for peer in list(self.peers):
            try:
                resp = requests.get(f"{peer}/chain", timeout=3)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                blocks = [Block.from_dict(b) for b in data["blocks"]]
                candidate = Blockchain(self.chain.params)
                candidate.blocks = blocks
                ok, _ = candidate.validate_full_chain()
                if not ok:
                    continue
                work = candidate.total_work()
                if work > best_work:
                    best_work = work
                    best_blocks = blocks
                    source = peer
            except requests.RequestException:
                continue

        if best_blocks is None:
            return {"replaced": False, "message": "Наш ланцюг вже найважчий (або сусіди недоступні)"}

        with self.lock:
            ok, msg, returned_txs = self.chain.replace_chain(best_blocks)
            if ok:
                self.mempool.return_transactions(returned_txs, self.chain)
                self.chain.save(self.chain_path)
        return {"replaced": ok, "message": msg, "source": source, "height": self.chain.height,
                "returned_tx_count": len(returned_txs) if ok else 0}

    def register_peer(self, peer_url: str) -> None:
        peer_url = peer_url.rstrip("/")
        if peer_url:
            self.peers.add(peer_url)


# ============================================================
# Flask REST API
# ============================================================

def create_app(node: Node) -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "node_id": node.node_id})

    @app.get("/chain")
    def get_chain():
        with node.lock:
            return jsonify(node.chain.to_dict())

    @app.get("/chain/height")
    def chain_height():
        with node.lock:
            return jsonify({"height": node.chain.height, "total_work": node.chain.total_work(),
                             "difficulty": node.chain.current_difficulty})

    @app.get("/chain/validate")
    def validate_chain():
        with node.lock:
            ok, msg = node.chain.validate_full_chain()
        return jsonify({"valid": ok, "message": msg}), (200 if ok else 409)

    @app.post("/transactions/new")
    def new_transaction():
        payload = request.get_json(force=True)
        tx = Transaction.from_dict(payload)
        from_peer = request.headers.get("X-From-Node") is not None
        try:
            txid = node.submit_transaction(tx, broadcast=True)
            return jsonify({"accepted": True, "txid": txid}), 201
        except TransactionRejected as e:
            return jsonify({"accepted": False, "reason": str(e)}), 400

    @app.get("/transactions/pending")
    def pending_transactions():
        with node.lock:
            return jsonify([tx.to_dict() for tx in node.mempool.all_transactions()])

    @app.post("/mine")
    def mine():
        payload = request.get_json(silent=True) or {}
        miner_address = payload.get("miner_address")
        if not miner_address:
            return jsonify({"error": "потрібно вказати miner_address"}), 400
        try:
            block = node.mine_one_block(miner_address)
            return jsonify({"mined": True, "block": block.to_dict()}), 201
        except ChainValidationError as e:
            return jsonify({"mined": False, "error": str(e)}), 500

    @app.post("/blocks/new")
    def new_block():
        payload = request.get_json(force=True)
        try:
            block = Block.from_dict(payload)
        except Exception as e:
            return jsonify({"accepted": False, "error": f"Некоректний формат блоку: {e}"}), 400
        result = node.receive_block(block)
        return jsonify(result), (200 if result.get("accepted") else 409)

    @app.post("/nodes/register")
    def register_nodes():
        payload = request.get_json(force=True)
        peers = payload.get("peers", [])
        if isinstance(peers, str):
            peers = [peers]
        for p in peers:
            node.register_peer(p)
        return jsonify({"peers": sorted(node.peers)}), 201

    @app.get("/nodes")
    def list_nodes():
        return jsonify({"peers": sorted(node.peers)})

    @app.post("/nodes/resolve")
    def resolve():
        result = node.resolve_conflicts()
        return jsonify(result)

    @app.get("/balance/<address>")
    def balance(address):
        with node.lock:
            return jsonify({
                "address": address,
                "balance": node.chain.get_balance(address),
                "next_nonce": node.chain.get_next_nonce(address),
            })

    @app.get("/wallet/new")
    def new_wallet():
        w = Wallet()
        return jsonify({
            "address": w.address,
            "public_key": w.public_key,
            "private_key": w.keypair.private_hex,
        })

    @app.get("/merkle_proof/<int:block_index>/<txid>")
    def merkle_proof(block_index, txid):
        """Доказ Меркла для легкого клієнта (додаткове завдання №1)."""
        with node.lock:
            if block_index < 0 or block_index > node.chain.height:
                return jsonify({"error": "немає такого блоку"}), 404
            block = node.chain.blocks[block_index]
            tx_hashes = block.tx_hashes()
            try:
                idx = tx_hashes.index(txid)
            except ValueError:
                return jsonify({"error": "транзакція не входить у цей блок"}), 404
            proof = build_merkle_proof(tx_hashes, idx)
            return jsonify({
                "block_index": block_index,
                "merkle_root": block.header.merkle_root,
                "proof": proof.to_dict(),
            })

    return app


def run_node_process(node_id: str, port: int, chain_path: str, peers: List[str] = None):
    node = Node(node_id, chain_path)
    for p in (peers or []):
        node.register_peer(p)
    app = create_app(node)
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)


def main():
    parser = argparse.ArgumentParser(description="Запуск вузла блокчейну")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--id", type=str, default=None)
    parser.add_argument("--data", type=str, default=None, help="шлях до файлу ланцюга")
    parser.add_argument("--peers", type=str, nargs="*", default=[], help="URL-адреси сусідніх вузлів")
    args = parser.parse_args()

    node_id = args.id or f"node-{args.port}"
    chain_path = args.data or f"chain_{args.port}.json"
    run_node_process(node_id, args.port, chain_path, args.peers)


if __name__ == "__main__":
    main()
