"""Exponential backoff with full jitter."""
from __future__ import annotations

import random
from collections.abc import Callable


class Backoff:
    def __init__(self, base: float = 2.0, cap: float = 300.0,
                 rng: Callable[[], float] = random.random) -> None:
        if base <= 0 or cap < base:
            raise ValueError("require 0 < base <= cap")
        self.base, self.cap, self._rng = base, cap, rng
        self.attempt = 0

    def ceiling(self) -> float:
        """Upper bound for the current attempt: min(cap, base * 2**attempt)."""
        return min(self.cap, self.base * (2 ** self.attempt))

    def next_delay(self) -> float:
        """Delay before the next retry; grows exponentially, randomised in [base/2, ceiling]."""
        ceiling = self.ceiling()
        self.attempt += 1
        low = self.base / 2
        return low + (ceiling - low) * self._rng()

    def reset(self) -> None:
        self.attempt = 0
