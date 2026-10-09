"""Console reporting, uniform across every pipeline step.

Windows ships a cp1252 stdout, which raises UnicodeEncodeError the moment a
speaker name carries a diacritic. Importing this module reconfigures stdout and
stderr to UTF-8, so every script gets it for free.

The reporting vocabulary is deliberately small:

    step()  a phase is starting
    info()  a fact worth printing
    warn()  something the reader should check, but the run continues
    fail()  the run cannot produce a trustworthy artefact — exits non-zero

`lib` code that refuses raises :class:`Refusal` instead of calling `fail`, and
a script's entry point, run through :func:`main`, turns it into the same exit.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import NoReturn

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


def _report(message: str, problems: Sequence[str]) -> str:
    return "\n".join([f"\nFAILED: {message}", *(f"  - {problem}" for problem in problems)])


class Refusal(SystemExit):
    """A refusal raised in `lib`, carrying what `fail` would have printed.

    A `SystemExit`, for two reasons. A script not run through :func:`main`
    still stops with status 1 and the same lines on stderr, rather than a
    traceback; and no `except Exception` in a caller can swallow it and go on
    to write an artefact. What `lib` gains over calling `fail` is that a test,
    or a caller with something better to do, can catch it by name and read
    `message` and `problems` instead of a process exit.
    """

    def __init__(self, message: str, problems: Sequence[str] | None = None) -> None:
        self.message = message
        self.problems = list(problems or [])
        super().__init__(_report(self.message, self.problems))


def step(message: str) -> None:
    print(f"\n>> {message}")


def info(message: str) -> None:
    print(f"   {message}")


def warn(message: str) -> None:
    print(f"   ! {message}")


def fail(message: str, problems: Sequence[str] | None = None) -> NoReturn:
    """Report an unrecoverable problem and exit non-zero.

    A script that cannot assert its output is correct must not leave a
    plausible-looking artefact behind; see scripts/README.md.
    """
    print(_report(message, list(problems or [])), file=sys.stderr)
    sys.exit(1)


def main(entry: Callable[[], object]) -> None:
    """Run a script's entry point, turning a :class:`Refusal` into :func:`fail`.

    The lines printed and the exit status are `fail`'s, so a refusal reads the
    same whether a script failed or `lib` refused.
    """
    try:
        entry()
    except Refusal as refusal:
        fail(refusal.message, refusal.problems)


def table(rows: list[tuple[str, object]], indent: str = "   ") -> None:
    """Print aligned label/value pairs."""
    if not rows:
        return
    width = max(len(str(label)) for label, _ in rows)
    for label, value in rows:
        print(f"{indent}{label!s:<{width}}  {value}")
