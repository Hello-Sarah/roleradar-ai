import gzip
import socket
import ssl

import httpx
import pytest

from app.ingestion import url_fetcher
from app.ingestion.url_fetcher import JobPageFetchError, _validate_public_url, fetch_job_from_url


def test_rr_f01_real_transport_pins_redirects_tls_and_ignores_ambient_proxy(monkeypatch):
    from httpcore._backends.sync import SyncBackend

    connected = []
    tls_hosts = []
    requests = []
    body = gzip.compress(b"<h1>AI Engineer</h1><p>Build reliable AI systems with customers.</p>")
    replies = [
        b"HTTP/1.1 302 Found\r\nLocation: https://next.invalid/job\r\nContent-Length: 0\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Encoding: gzip\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
        + body,
    ]

    class Stream:
        def read(self, max_bytes, timeout=None):
            return replies.pop(0) if replies else b""

        def write(self, buffer, timeout=None):
            requests.append(buffer)

        def close(self):
            pass

        def get_extra_info(self, name):
            return False if name == "is_readable" else None

        def start_tls(self, ssl_context, server_hostname, timeout=None):
            assert ssl_context.check_hostname is True
            assert ssl_context.verify_mode == ssl.CERT_REQUIRED
            tls_hosts.append(server_hostname)
            return self

    resolutions = []

    def resolve(host, *args, **kwargs):
        resolutions.append(host)
        address = "93.184.216.34"
        if host.endswith(".invalid") and resolutions.count(host) > 1:
            address = "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    def connect(self, host, port, **kwargs):
        peer = socket.getaddrinfo(host, port)[0][4][0]
        assert peer != "127.0.0.1", "Private peer reached through DNS rebinding"
        connected.append((host, port))
        return Stream()

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(SyncBackend, "connect_tcp", connect)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    job = fetch_job_from_url("https://rebind.invalid/job")
    assert "Build reliable AI systems" in job.description
    assert connected == [("93.184.216.34", 443), ("93.184.216.34", 443)]
    assert tls_hosts == ["rebind.invalid", "next.invalid"]
    assert b"Host: rebind.invalid" in b"".join(requests)
    assert b"Host: next.invalid" in b"".join(requests)


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


def test_rr_f01_rebinding_never_connects_to_second_hostname_answer(monkeypatch) -> None:
    resolutions = []

    def resolve(host, *args, **kwargs):
        resolutions.append(host)
        address = (
            "127.0.0.1"
            if host == "rebind.invalid" and resolutions.count(host) > 1
            else "93.184.216.34"
        )
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    def connection(request):
        peer = socket.getaddrinfo(request.url.host, 443)[0][4][0]
        assert peer != "127.0.0.1", "Rebinding reached a private connection address"
        assert request.headers["host"] == "rebind.invalid"
        assert request.extensions["sni_hostname"] == "rebind.invalid"
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<h1>Applied AI Engineer</h1><p>Build reliable AI systems for customers.</p>",
        )

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    real_client = httpx.Client
    options = {}

    def client(**kwargs):
        options.update(kwargs)
        return real_client(transport=httpx.MockTransport(connection))

    monkeypatch.setattr(url_fetcher.httpx, "Client", client)
    result = fetch_job_from_url("https://rebind.invalid/jobs/1")
    assert result.url == "https://rebind.invalid/jobs/1"
    assert options["trust_env"] is False


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
