"""
Автоматичне коригування складності.

Кожні K блоків дивимось, скільки реального часу зайняло видобування
останніх K блоків, і порівнюємо із заданим (target_block_time * K).
Якщо блоки знаходились швидше за очікуване — складність зростає
(додається нуль), якщо повільніше — складність падає (нуль забирається).

Це спрощена, але чесна модель того ж принципу, що і в Bitcoin
(там перерахунок теж робиться за співвідношенням "очікуваний час /
фактичний час", тільки там це виражається в 32-бітному target,
а тут — у кількості нулів на початку хешу).
"""

from __future__ import annotations
from typing import List

from .block import Block


def adjust_difficulty(
    chain_blocks: List[Block],
    current_difficulty: int,
    adjustment_interval: int,
    target_block_time: float,
    min_difficulty: int = 1,
    max_difficulty: int = 8,
) -> int:
    """
    Викликається ПІСЛЯ додавання чергового блоку.
    Перераховує складність, тільки якщо номер щойно доданого блоку
    кратний adjustment_interval (і це не генезис-блок).
    """
    last_index = chain_blocks[-1].header.index
    if last_index == 0 or last_index % adjustment_interval != 0:
        return current_difficulty

    window = chain_blocks[-adjustment_interval:]
    actual_time = window[-1].header.timestamp - window[0].header.timestamp
    expected_time = target_block_time * (adjustment_interval - 1) if adjustment_interval > 1 else target_block_time
    expected_time = max(expected_time, 1e-6)

    ratio = actual_time / expected_time

    new_difficulty = current_difficulty
    if ratio < 0.5:
        # блоки видобувались більш ніж удвічі швидше за очікуване -> ускладнюємо
        new_difficulty = current_difficulty + 1
    elif ratio > 2.0:
        # видобувались більш ніж удвічі повільніше -> спрощуємо
        new_difficulty = current_difficulty - 1

    return max(min_difficulty, min(max_difficulty, new_difficulty))
