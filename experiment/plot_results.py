#!/usr/bin/env python3
"""Побудова графіка середнього часу майнінгу з розкидом (логарифмічна вісь часу)."""

import json
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "difficulty_experiment.png")


def main():
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    difficulties = sorted(int(k) for k in data.keys())
    means = [statistics.mean(data[str(d)]) for d in difficulties]
    stdevs = [statistics.stdev(data[str(d)]) if len(data[str(d)]) > 1 else 0 for d in difficulties]

    fig, ax = plt.subplots(figsize=(8, 5.5))

    # окремі точки запусків (розкид) — сірі, напівпрозорі
    for d in difficulties:
        xs = [d] * len(data[str(d)])
        ax.scatter(xs, data[str(d)], color="gray", alpha=0.4, s=25, zorder=2,
                   label="окремі запуски" if d == difficulties[0] else None)

    ax.errorbar(difficulties, means, yerr=stdevs, fmt="o-", color="#1f6feb",
                capsize=5, linewidth=2, markersize=7, zorder=3,
                label="середній час ± стандартне відхилення")

    ax.set_yscale("log")
    ax.set_xlabel("Складність (кількість нулів на початку хешу)")
    ax.set_ylabel("Час майнінгу, с (логарифмічна шкала)")
    ax.set_title("Залежність часу майнінгу від складності Proof of Work")
    ax.set_xticks(difficulties)
    ax.grid(True, which="both", linestyle="--", alpha=0.4)
    ax.legend()

    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=150)
    print(f"Графік збережено у {OUT_PATH}")

    print("\nПояснення форми кривої:")
    print("Очікуваний час майнінгу зростає ЕКСПОНЕНЦІЙНО зі складністю, оскільки для")
    print("кожного додаткового шістнадцяткового нуля (тобто 4 додаткових бітів) простір")
    print("'придатних' хешів звужується у 16 разів, а хеш-функція SHA-256 не дає жодного")
    print("способу передбачити результат — лишається лише повний перебір nonce. Тому на")
    print("графіку з логарифмічною віссю часу точки лягають майже на пряму лінію —")
    print("ознака експоненційної залежності при лінійному кроці складності.")
    for i in range(1, len(difficulties)):
        ratio = means[i] / means[i - 1]
        print(f"  складність {difficulties[i-1]} -> {difficulties[i]}: "
              f"час зріс у {ratio:.2f} раза (теоретично очікується ~16x)")


if __name__ == "__main__":
    main()
