"""Regression tests for the Dataverse HTTP boundary.

The retry tests below exist because of a real failure on 11 August 2026: the
publish workflow died twice in a row on a 404 from Harvard Dataverse, while the
same URLs answered 200 from a laptop seconds apart. The archive sheds load with
a 404 and an HTML body rather than a 429, so "retry the 5xx" would not have
helped and "retry every 404" would have hidden a mistyped version pin. What is
tested here is that distinction, because it is the whole of the fix.
"""

from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def fetch_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "00_fetch_data.py"
    spec = importlib.util.spec_from_file_location("fetch_data", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_headers(request, fetch_module, accept: str) -> None:
    assert request.get_header("User-agent") == fetch_module.USER_AGENT
    assert request.get_header("Accept") == accept


def test_dataset_metadata_request_identifies_the_project(monkeypatch, fetch_module):
    seen = {}
    payload = {
        "data": {
            "versionNumber": 6,
            "versionMinorNumber": 1,
            "files": [],
        }
    }

    def urlopen(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", urlopen)

    assert fetch_module.dataset_version("6.1") == payload["data"]
    assert seen["timeout"] == 60
    assert_headers(seen["request"], fetch_module, "application/json")


def test_file_download_identifies_the_project(monkeypatch, tmp_path, fetch_module):
    seen = {}

    def urlopen(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return io.BytesIO(b"abc")

    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", urlopen)
    destination = tmp_path / "sample.tsv"

    fetch_module.download(123, destination, 3)

    assert destination.read_bytes() == b"abc"
    assert seen["timeout"] == 120
    assert_headers(seen["request"], fetch_module, "application/octet-stream")


def http_error(code: int, body: bytes, headers: dict | None = None):
    return urllib.error.HTTPError(
        "https://dataverse.harvard.edu/api/access/datafile/1",
        code,
        "Not Found",
        headers or {},  # type: ignore[arg-type]
        io.BytesIO(body),
    )


#: What the archive sends when it is declining to answer: a 404 carrying a page.
SHEDDING = b"<html><head><title>404</title></head><body>Not Found</body></html>"

#: What it sends when the thing genuinely is not there.
REFUSAL = json.dumps({"status": "ERROR", "message": "Dataset version not found"}).encode()


@pytest.fixture(autouse=True)
def instant_backoff(monkeypatch, fetch_module):
    """The waits are real seconds; a test suite must not sit through them."""
    monkeypatch.setattr(fetch_module.time, "sleep", lambda _: None)


class TestSheddingIsToldFromRefusal:
    def test_a_404_with_a_page_is_the_archive_declining(self, fetch_module):
        assert fetch_module._shedding(http_error(404, SHEDDING))

    def test_a_404_with_dataverses_own_json_is_a_real_answer(self, fetch_module):
        """A mistyped version pin must fail now, not after two minutes of
        retrying and then a message about the network."""
        assert not fetch_module._shedding(http_error(404, REFUSAL))

    def test_an_empty_404_body_is_treated_as_shedding(self, fetch_module):
        assert fetch_module._shedding(http_error(404, b""))

    def test_the_overload_statuses_are_retryable(self, fetch_module):
        for code in (429, 500, 502, 503, 504):
            assert fetch_module._shedding(http_error(code, b""))

    def test_a_forbidden_is_not_retried(self, fetch_module):
        """403 is a decision about this client, and repeating the request will
        not change it."""
        assert not fetch_module._shedding(http_error(403, b""))


class TestRetry:
    def test_a_shed_request_is_tried_again_and_succeeds(self, fetch_module):
        attempts = []

        def operation():
            attempts.append(len(attempts))
            if len(attempts) < 3:
                raise http_error(404, SHEDDING)
            return "payload"

        assert fetch_module.with_retry(operation, "datafile 1") == "payload"
        assert len(attempts) == 3

    def test_a_real_refusal_is_raised_on_the_first_attempt(self, fetch_module):
        attempts = []

        def operation():
            attempts.append(len(attempts))
            raise http_error(404, REFUSAL)

        with pytest.raises(urllib.error.HTTPError):
            fetch_module.with_retry(operation, "dataset version 9.9")
        assert len(attempts) == 1

    def test_it_gives_up_rather_than_hanging_the_workflow(self, fetch_module):
        attempts = []

        def operation():
            attempts.append(len(attempts))
            raise http_error(503, b"")

        with pytest.raises(urllib.error.HTTPError):
            fetch_module.with_retry(operation, "datafile 1", attempts=4)
        assert len(attempts) == 4

    def test_a_dropped_connection_mid_download_is_retried(self, fetch_module):
        """The 474 MB file is where this matters: the stream can die after the
        response headers were fine."""
        attempts = []

        def operation():
            attempts.append(len(attempts))
            if len(attempts) < 2:
                raise ConnectionResetError("connection reset by peer")
            return "done"

        assert fetch_module.with_retry(operation, "datafile 1") == "done"
        assert len(attempts) == 2

    def test_a_named_retry_after_is_honoured(self, fetch_module, monkeypatch):
        waits = []
        monkeypatch.setattr(fetch_module.time, "sleep", waits.append)
        attempts = []

        def operation():
            attempts.append(len(attempts))
            if len(attempts) < 2:
                raise http_error(429, b"", {"Retry-After": "7"})
            return "ok"

        assert fetch_module.with_retry(operation, "datafile 1") == "ok"
        assert waits == [7.0]

    def test_a_2xx_that_carries_no_json_is_retried(self, fetch_module):
        """Observed on 12 August 2026: every Dataverse endpoint answered 202 with
        an empty text/html body. `urlopen` raises nothing below 400, so the
        response reached `json.load` and the run died in 205 ms with all six
        attempts unspent — the retry bypassed by the outage it exists for."""
        attempts = []

        def operation():
            attempts.append(len(attempts))
            if len(attempts) < 3:
                raise json.JSONDecodeError("Expecting value", "", 0)
            return "payload"

        assert fetch_module.with_retry(operation, "dataset version 6.1") == "payload"
        assert len(attempts) == 3

    def test_giving_up_on_an_unreadable_body_blames_the_archive(self, fetch_module):
        """A bare JSONDecodeError names a column of a string nobody wrote and
        sends whoever reads the log to `json/decoder.py` for what is an outage."""
        attempts = []

        def operation():
            attempts.append(len(attempts))
            raise json.JSONDecodeError("Expecting value", "", 0)

        with pytest.raises(RuntimeError, match="without readable JSON") as caught:
            fetch_module.with_retry(operation, "dataset version 6.1", attempts=3)
        assert len(attempts) == 3
        # Chained, so the parser's own account survives for anyone who wants it.
        assert isinstance(caught.value.__cause__, json.JSONDecodeError)


class Stream:
    """A response that hands back chunks, optionally dying part-way through."""

    def __init__(self, *chunks: bytes, fail_after: int | None = None):
        self.chunks = list(chunks)
        self.fail_after = fail_after
        self.served = 0

    def read(self, size: int = -1) -> bytes:
        if self.fail_after is not None and self.served == self.fail_after:
            raise ConnectionResetError("connection reset by peer")
        if not self.chunks:
            return b""
        self.served += 1
        return self.chunks.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_a_retried_download_does_not_append_to_the_failed_attempt(
    monkeypatch, tmp_path, fetch_module
):
    """The partial bytes of a failed attempt must not survive into the file the
    MD5 check then runs against — an appended retry would produce `truncabc`
    and a mismatch nobody could explain from the log."""
    calls = []

    def urlopen(request, timeout):
        calls.append(request)
        if len(calls) == 1:
            return Stream(b"trunc", fail_after=1)
        return Stream(b"abc")

    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", urlopen)
    destination = tmp_path / "sample.tsv"

    fetch_module.download(123, destination, 3)

    assert destination.read_bytes() == b"abc"
    assert len(calls) == 2
