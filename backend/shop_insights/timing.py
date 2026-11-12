"""Tiny timer used to measure each analysis step (timings are reported in the README and API)."""
import time
from collections.abc import Iterator
from contextlib import contextmanager


class StepTimer:
    def __init__(self, verbose: bool = False) -> None:
        self.seconds: dict[str, float] = {}
        self.verbose = verbose

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.seconds[name] = round(elapsed, 3)
            if self.verbose:
                print(f"  {name:<32} {elapsed:7.2f} s")
