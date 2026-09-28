#!/usr/bin/env python3
"""
Експеримент: залежність часу майнінгу від складності (крок 8 методички).

Для кожного рівня складності виконуємо N незалежних запусків майнінгу
одного блока (з нуля, різний timestamp/nonce-простір) і фіксуємо час.
Результати зберігаються в experiment/results.json, графік — у
experiment/difficulty_experiment.png.
"""

import json
import os
import statistics
import time

from blockchain.wallet import Wallet
from blockchain.chain import Blockchain, ChainParams
from blockchain.mining import mine_block

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.json")


def measure_one(difficulty: int, miner_address: str) -> float:
    chain = Blockchain(ChainParams(initial_difficulty=difficulty))
    candidate = chain.build_candidate_block([], miner_address)
    start = time.perf_counter()
    mine_block(candidate)
    return time.perf_counter() - start


def run_experiment(difficulties, runs_per_level: int = 10):
    miner = Wallet()
    results = {}
    for d in difficulties:
        times = []
        print(f"Складність {d}: ", end="", flush=True)
        for i in range(runs_per_level):
            t = measure_one(d, miner.address)
            times.append(t)
            print(f"{t:.3f}s ", end="", flush=True)
        results[d] = times
        mean = statistics.mean(times)
        stdev = statistics.stdev(times) if len(times) > 1 else 0.0
        print(f"\n  середнє = {mean:.4f}с, стандартне відхилення = {stdev:.4f}с\n")
    return results


def main():
    # Складність обрана так, щоб експеримент займав розумний час у навчальному середовищі
    # (у "бойовому" запуску з методички можна взяти 4..7, тут — щоб вклалось у хвилини)
    difficulties = [2, 3, 4, 5]
    runs_per_level = 10

    results = run_experiment(difficulties, runs_per_level)

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in results.items()}, f, indent=2)
    print(f"Результати збережено у {RESULTS_PATH}")

    print("\nПідсумкова таблиця:")
    print(f"{'складність':>10} | {'сер. час, с':>12} | {'у скільки разів більше за попередню':>36}")
    prev_mean = None
    for d in difficulties:
        mean = statistics.mean(results[d])
        ratio = f"{mean / prev_mean:.2f}x" if prev_mean else "-"
        print(f"{d:>10} | {mean:>12.4f} | {ratio:>36}")
        prev_mean = mean


if __name__ == "__main__":
    main()
