"""How a refusal leaves the process: the same lines and status, raised or failed."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from lib import console

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

ENDINGS = {
    "fail": "console.fail('no trustworthy artefact', ['first', 'second'])",
    "uncaught": "raise console.Refusal('no trustworthy artefact', ['first', 'second'])",
    "main": (
        "def entry():\n"
        "    raise console.Refusal('no trustworthy artefact', ['first', 'second'])\n"
        "console.main(entry)"
    ),
}


def ending(code: str) -> subprocess.CompletedProcess[str]:
    program = f"import sys\nsys.path.insert(0, {str(SCRIPTS)!r})\nfrom lib import console\n{code}\n"
    return subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, encoding="utf-8"
    )


def test_a_refusal_ends_the_process_exactly_as_fail_does() -> None:
    """A script not yet run through `console.main` loses nothing: the refusal
    still prints the failure and its problems, and exits 1, with no traceback."""
    results = {name: ending(code) for name, code in ENDINGS.items()}
    expected = "\nFAILED: no trustworthy artefact\n  - first\n  - second\n"
    for name, result in results.items():
        assert result.returncode == 1, name
        assert result.stderr == expected, name
        assert result.stdout == "", name


def test_a_refusal_carries_its_message_and_problems() -> None:
    with pytest.raises(console.Refusal) as refused:
        raise console.Refusal("stop", ["one reason"])
    assert refused.value.message == "stop"
    assert refused.value.problems == ["one reason"]


def test_main_turns_only_a_refusal_into_an_exit() -> None:
    def broken() -> None:
        raise KeyError("a bug is a traceback, not a refusal")

    with pytest.raises(KeyError):
        console.main(broken)
    with pytest.raises(SystemExit) as exited:
        console.main(lambda: (_ for _ in ()).throw(console.Refusal("stop")))
    assert exited.value.code == 1
