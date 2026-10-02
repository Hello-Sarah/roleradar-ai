import ipaddress
import json
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.ingestion.text_extractor import extract_job_from_text
from app.schemas import JobCreate

MAX_RESPONSE_BYTES = 2_000_000
MAX_REDIRECTS = 4


class JobPageFetchError(ValueError):
    pass


class _JobPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.json_ld_parts: list[str] = []
        self._ignored_depth = 0
        self._in_json_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in {"script", "style", "noscript", "svg"}:
            if tag == "script" and attributes.get("type", "").casefold() == "application/ld+json":
                self._in_json_ld = True
            else:
                self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_json_ld:
            self._in_json_ld = False
        elif tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self.json_ld_parts.append(data)
        elif not self._ignored_depth and data.strip():
            self.text_parts.append(data.strip())


def _validate_public_url(url: str) -> tuple[str, ...]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise JobPageFetchError("Only public HTTP or HTTPS job links are supported")
    if parsed.username or parsed.password:
        raise JobPageFetchError("Job links containing credentials are not supported")
    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise JobPageFetchError("The job link hostname could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise JobPageFetchError("Private or local network links are not allowed")
    if not addresses:
        raise JobPageFetchError("The job link hostname could not be resolved")
    return tuple(dict.fromkeys(address[4][0] for address in addresses))


def _job_posting_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for child in value for item in _job_posting_objects(child)]
    if not isinstance(value, dict):
        return []
    found = [value] if value.get("@type") == "JobPosting" else []
    for child in value.values():
        found.extend(_job_posting_objects(child))
    return found


def _location_from_json_ld(posting: dict[str, Any]) -> str | None:
    location = posting.get("jobLocation")
    if isinstance(location, list):
        location = location[0] if location else None
    if not isinstance(location, dict):
        return None
    address = location.get("address", {})
    if not isinstance(address, dict):
        return None
    parts = [address.get(key) for key in ("addressLocality", "addressRegion", "addressCountry")]
    return ", ".join(str(part) for part in parts if part) or None


def _apply_json_ld(job: JobCreate, json_ld_parts: list[str]) -> JobCreate:
    postings: list[dict[str, Any]] = []
    for part in json_ld_parts:
        try:
            postings.extend(_job_posting_objects(json.loads(part)))
        except json.JSONDecodeError:
            continue
    if not postings:
        return job
    posting = postings[0]
    organization = posting.get("hiringOrganization", {})
    company = organization.get("name") if isinstance(organization, dict) else None
    data = job.model_dump()
    data["company"] = company or job.company
    data["title"] = posting.get("title") or job.title
    data["location"] = _location_from_json_ld(posting) or job.location
    data["posting_date"] = posting.get("datePosted") or job.posting_date
    return JobCreate.model_validate(data)


def fetch_job_from_url(url: str) -> JobCreate:
    """Fetch a public job page, extract readable content, and normalize its metadata."""
    current_url = url
    headers = {"User-Agent": "RoleRadarAI/0.1 (+career intelligence; contact site owner)"}
    # Never use ambient proxies: they could independently resolve the vetted hostname.
    with httpx.Client(
        timeout=15,
        follow_redirects=False,
        headers=headers,
        trust_env=False,
        limits=httpx.Limits(max_keepalive_connections=0),
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            addresses = _validate_public_url(current_url)
            origin = httpx.URL(current_url)
            # Connect to a vetted numeric address, but authenticate the original HTTPS
            # hostname and preserve HTTP authority. No second hostname DNS resolution.
            pinned = origin.copy_with(host=addresses[0])
            try:
                with client.stream(
                    "GET",
                    pinned,
                    headers={"Host": origin.netloc.decode("ascii")},
                    extensions={"sni_hostname": origin.host},
                ) as response:
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_RESPONSE_BYTES:
                            raise JobPageFetchError("The job page is too large to analyze")
                    decoded_headers = dict(response.headers)
                    decoded_headers.pop("content-encoding", None)
                    decoded_headers.pop("content-length", None)
                    response = httpx.Response(
                        response.status_code,
                        headers=decoded_headers,
                        content=bytes(content),
                        request=response.request,
                    )
            except httpx.HTTPError as exc:
                raise JobPageFetchError(f"Could not retrieve the job page: {exc}") from exc
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise JobPageFetchError("The job page returned an invalid redirect")
                current_url = urljoin(current_url, location)
                continue
            break
        else:
            raise JobPageFetchError("The job page redirected too many times")

    if response.status_code >= 400:
        raise JobPageFetchError(f"The job page returned HTTP {response.status_code}")
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise JobPageFetchError("The job page is too large to analyze")
    content_type = response.headers.get("content-type", "").casefold()
    if "text/html" not in content_type:
        raise JobPageFetchError("The link does not point to an HTML job page")

    parser = _JobPageParser()
    parser.feed(response.text)
    readable_text = "\n".join(parser.text_parts)
    if len(readable_text) < 40:
        raise JobPageFetchError("No readable job description was found; paste the job text instead")
    extracted = extract_job_from_text(f"{current_url}\n{readable_text}")
    extracted = _apply_json_ld(extracted, parser.json_ld_parts)
    return extracted.model_copy(update={"url": current_url, "source": "job_url"})
