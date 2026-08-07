"""Console reporting, uniform across every pipeline step.

Windows ships a cp1252 stdout, which raises UnicodeEncodeError the moment a
speaker name carries a diacritic. Importing this module reconfigures stdout and
stderr to UTF-8, so every script gets it for free.

The reporting vocabulary is deliberately small:

    step()  a phase is starting
    info()  a fact worth printing
    warn()  something the reader should check, but the run continues
    fail()  the run cannot produce a trustworthy artefact — exits non-zero
"""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


def step(message: str) -> None:
    print(f"\n>> {message}")


def info(message: str) -> None:
    print(f"   {message}")


def warn(message: str) -> None:
    print(f"   ! {message}")


def fail(message: str, problems: list[str] | None = None) -> None:
    """Report an unrecoverable problem and exit non-zero.

    A script that cannot assert its output is correct must not leave a
    plausible-looking artefact behind; see scripts/README.md.
    """
    print(f"\nFAILED: {message}", file=sys.stderr)
    for problem in problems or []:
        print(f"  - {problem}", file=sys.stderr)
    sys.exit(1)


@contextmanager
def timed(message: str) -> Iterator[None]:
    """Time a phase and report how long it took."""
    step(message)
    started = time.monotonic()
    yield
    info(f"({time.monotonic() - started:.1f}s)")


def table(rows: list[tuple[str, object]], indent: str = "   ") -> None:
    """Print aligned label/value pairs."""
    if not rows:
        return
    width = max(len(str(label)) for label, _ in rows)
    for label, value in rows:
        print(f"{indent}{label!s:<{width}}  {value}")
