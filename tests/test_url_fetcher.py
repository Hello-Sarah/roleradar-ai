import socket

import httpx
import pytest

from app.ingestion import url_fetcher
from app.ingestion.url_fetcher import JobPageFetchError, _validate_public_url, fetch_job_from_url


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
        lambda host, *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34", 443),
            )
        ],
    )

    _validate_public_url("https://example.com/jobs/123")


@pytest.mark.parametrize(
    ("response_factory", "expected"),
    [
        (
            lambda request: httpx.Response(
                302, headers={"location": "http://127.0.0.1/private"}, request=request
            ),
            "Private or local",
        ),
        (
            lambda request: httpx.Response(
                200,
                content=b"x" * (url_fetcher.MAX_RESPONSE_BYTES + 1),
                headers={"content-type": "text/html"},
                request=request,
            ),
            "too large",
        ),
        (
            lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("synthetic timeout")),
            "Could not retrieve",
        ),
    ],
)
def test_public_url_safeguards_reject_redirect_size_and_timeout(
    monkeypatch: pytest.MonkeyPatch, response_factory, expected: str
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34", 443),
            )
        ],
    )
    transport = httpx.MockTransport(response_factory)
    real_client = httpx.Client
    monkeypatch.setattr(
        url_fetcher.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, follow_redirects=False),
    )

    with pytest.raises(JobPageFetchError, match=expected):
        fetch_job_from_url("https://example.com/jobs/guarded")
