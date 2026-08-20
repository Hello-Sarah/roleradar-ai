import socket

import pytest

from app.ingestion.url_fetcher import JobPageFetchError, _validate_public_url


def test_rejects_private_network_job_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
    )

    with pytest.raises(JobPageFetchError, match="Private or local"):
        _validate_public_url("http://localhost/job")


def test_accepts_public_job_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    _validate_public_url("https://example.com/jobs/123")
