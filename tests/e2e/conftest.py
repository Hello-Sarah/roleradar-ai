"""Playwright fixtures for an isolated, synthetic RoleRadar acceptance environment."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from playwright.sync_api import Browser, Page, expect

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_JD = """Company: Synthetic Signal Labs
Job Title: Forward Deployed AI Engineer
Location: Hong Kong
https://example.invalid/jobs/fde-ai
Posted: 2026-09-30

Build and ship production AI workflows with Python, FastAPI, evaluation, customer discovery,
and end-to-end technical ownership. Partner with product teams and deploy reliable systems.
"""
SYNTHETIC_CV = """Synthetic Candidate
Forward Deployed AI Engineer
Built and shipped production AI workflows with Python and FastAPI.
Led customer discovery and end-to-end technical delivery.
"""


@dataclass(slots=True)
class AcceptanceRuntime:
    api_url: str
    app_url: str
    provider_call_log: Path
    api_process: subprocess.Popen[str]
    app_process: subprocess.Popen[str]


class ScreenshotPath:
    _ZH_ROUTES = {
        "Dashboard": "仪表盘",
        "Jobs": "职位",
        "Watch List": "关注列表",
        "CV Library": "CV 库",
    }

    def __init__(self, root: Path, browser_name: str) -> None:
        self.root = root
        self.browser_name = browser_name

    def __call__(self, locale: str, name: str) -> Path:
        destination = self.root / "screenshots" / locale / f"{self.browser_name}-{name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    def localized_route(self, route: str) -> str:
        return self._ZH_ROUTES[route]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_url(url: str, process: subprocess.Popen[str], timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(
                f"Acceptance service exited before {url} became ready\n{stdout}\n{stderr}"
            )
        try:
            if httpx.get(url, timeout=0.5).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for {url}")


def _stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _api_bootstrap() -> str:
    return """
from pathlib import Path
import os
import uvicorn
import app.services.cv_service as cv_service

def fake_generate_content(documents, job, settings):
    del job, settings
    with Path(os.environ['PROVIDER_CALL_LOG']).open('a', encoding='utf-8') as handle:
        handle.write('tailored_cv\\n')
    return cv_service.TailoredCVContent(
        name=cv_service.EvidenceBackedItem(
            text='Synthetic Candidate', source_quote='Synthetic Candidate'
        ),
        headline=cv_service.EvidenceBackedItem(
            text='Forward Deployed AI Engineer',
            source_quote='Forward Deployed AI Engineer',
        ),
        summary=[cv_service.EvidenceBackedItem(
            text='Built and shipped production AI workflows with Python and FastAPI.',
            source_quote='Built and shipped production AI workflows with Python and FastAPI.',
        )],
        skills=[cv_service.EvidenceBackedItem(text='Python', source_quote='Python')],
        sections=[cv_service.TailoredCVSection(
            title='Experience',
            items=[cv_service.EvidenceBackedItem(
                text='Led customer discovery and end-to-end technical delivery.',
                source_quote='Led customer discovery and end-to-end technical delivery.',
            )],
        )],
    )

cv_service._generate_content = fake_generate_content
uvicorn.run(
    'app.main:app',
    host='127.0.0.1',
    port=int(os.environ['E2E_API_PORT']),
    log_level='warning',
)
"""


@pytest.fixture
def synthetic_jd() -> str:
    return SYNTHETIC_JD


@pytest.fixture
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 1100},
        "locale": "en-US",
        "reduced_motion": "reduce",
    }


@pytest.fixture
def app_runtime(tmp_path: Path) -> Generator[AcceptanceRuntime, None, None]:
    api_port = _free_port()
    app_port = _free_port()
    database = tmp_path / "acceptance.sqlite3"
    cv_library = tmp_path / "cv-library"
    generated_cvs = tmp_path / "generated-cvs"
    cv_library.mkdir()
    generated_cvs.mkdir()
    (cv_library / "synthetic-redacted-cv.txt").write_text(SYNTHETIC_CV, encoding="utf-8")
    provider_call_log = tmp_path / "provider-calls.log"
    provider_call_log.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{database}",
            "AI_EXPLANATIONS_ENABLED": "false",
            "OPENAI_API_KEY": "mocked-e2e-provider",
            "CV_LIBRARY_PATH": str(cv_library),
            "GENERATED_CV_PATH": str(generated_cvs),
            "PROVIDER_CALL_LOG": str(provider_call_log),
            "E2E_API_PORT": str(api_port),
            "API_BASE_URL": f"http://127.0.0.1:{api_port}",
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        }
    )
    api_process = subprocess.Popen(
        [sys.executable, "-c", _api_bootstrap()],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    app_process: subprocess.Popen[str] | None = None
    try:
        _wait_for_url(f"http://127.0.0.1:{api_port}/api/v1/health", api_process)
        app_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app/dashboard/streamlit_app.py",
                "--server.headless=true",
                "--server.address=127.0.0.1",
                f"--server.port={app_port}",
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_url(f"http://127.0.0.1:{app_port}/_stcore/health", app_process)
        yield AcceptanceRuntime(
            api_url=f"http://127.0.0.1:{api_port}",
            app_url=f"http://127.0.0.1:{app_port}",
            provider_call_log=provider_call_log,
            api_process=api_process,
            app_process=app_process,
        )
    finally:
        if app_process is not None:
            _stop(app_process)
        _stop(api_process)


@pytest.fixture
def api_client(app_runtime: AcceptanceRuntime) -> Generator[httpx.Client, None, None]:
    with httpx.Client(base_url=app_runtime.api_url, timeout=20) as client:
        yield client


@pytest.fixture
def provider_call_log(app_runtime: AcceptanceRuntime) -> Path:
    return app_runtime.provider_call_log


def _load_app(page: Page, app_runtime: AcceptanceRuntime) -> Page:
    page.goto(f"{app_runtime.app_url}/?lang=en")
    expect(page.get_by_text("RoleRadar AI", exact=True).first).to_be_visible(timeout=20_000)
    return page


def _release_trace_path(request: pytest.FixtureRequest, browser_name: str) -> Path:
    from scripts.build_acceptance_bundle import REQUIRED_TRACE_WORKFLOWS

    test_name = request.node.originalname or request.node.name
    workflow = next(
        (name for name, test in REQUIRED_TRACE_WORKFLOWS.items() if test == test_name), test_name
    )
    output = Path(str(request.config.getoption("output")))
    path = output / "traces" / f"{browser_name}-{workflow}.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def roleradar_page(
    browser: Browser,
    browser_context_args: dict[str, Any],
    browser_name: str,
    request: pytest.FixtureRequest,
    app_runtime: AcceptanceRuntime,
) -> Generator[Page, None, None]:
    # Own this context so plugin retain-on-failure cannot discard successful release traces.
    context = browser.new_context(**browser_context_args)
    context.tracing.start(title=request.node.nodeid, screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    try:
        yield _load_app(page, app_runtime)
    finally:
        context.tracing.stop(path=_release_trace_path(request, browser_name))
        context.close()


@pytest.fixture
def narrow_roleradar_page(
    browser: Browser,
    browser_name: str,
    request: pytest.FixtureRequest,
    app_runtime: AcceptanceRuntime,
) -> Generator[Page, None, None]:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, locale="en-US", reduced_motion="reduce"
    )
    context.tracing.start(title=request.node.nodeid, screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    try:
        yield _load_app(page, app_runtime)
    finally:
        context.tracing.stop(path=_release_trace_path(request, browser_name))
        context.close()


def _seed(client: httpx.Client) -> None:
    job = client.post(
        "/api/v1/jobs",
        json={
            "company": "Synthetic Signal Labs",
            "title": "Forward Deployed AI Engineer",
            "location": "Hong Kong",
            "url": "https://example.invalid/jobs/fde-ai",
            "posting_date": "2026-09-30",
            "description": SYNTHETIC_JD,
            "source": "synthetic_acceptance_seed",
        },
    )
    job.raise_for_status()
    event = client.post(
        f"/api/v1/jobs/{job.json()['id']}/application-events",
        json={
            "status": "Saved",
            "occurred_at": "2026-10-01T09:00:00Z",
            "channel": "Company website",
            "notes": "Synthetic redacted application event",
            "next_follow_up_date": "2026-10-01",
        },
    )
    event.raise_for_status()
    company = client.post(
        "/api/v1/watchlist/companies",
        json={
            "name": "Synthetic Signal Labs",
            "canonical_domain": "synthetic-signal.invalid",
            "company_type": "ai_native_forward_deployed",
            "strategic_priority": "core_target",
            "action_window": "apply_now",
            "target_role_patterns": ["Forward Deployed AI Engineer"],
            "target_locations": ["Hong Kong"],
            "positive_keywords": ["AI", "Python"],
            "exclusion_keywords": [],
            "location_notes": "Synthetic fixture only",
            "work_authorization_notes": "No private data",
            "official_source_url": "https://example.invalid/careers",
            "source_kind": "career_page",
            "source_state": "verified_manual",
            "source_state_reason": "Synthetic test source",
            "rationale": "Synthetic acceptance target",
        },
    )
    company.raise_for_status()
    scan = client.post("/api/v1/cv-library/scan", json={})
    scan.raise_for_status()


@pytest.fixture
def seeded_roleradar_page(
    page: Page, app_runtime: AcceptanceRuntime, api_client: httpx.Client
) -> Page:
    _seed(api_client)
    return _load_app(page, app_runtime)


@pytest.fixture
def narrow_seeded_page(
    browser: Browser, app_runtime: AcceptanceRuntime, api_client: httpx.Client
) -> Generator[Page, None, None]:
    _seed(api_client)
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, locale="en-US", reduced_motion="reduce"
    )
    page = context.new_page()
    try:
        yield _load_app(page, app_runtime)
    finally:
        context.close()


@pytest.fixture
def unavailable_page(page: Page, app_runtime: AcceptanceRuntime) -> Page:
    _stop(app_runtime.api_process)
    return _load_app(page, app_runtime)


@pytest.fixture
def screenshot_path(request: pytest.FixtureRequest, browser_name: str) -> ScreenshotPath:
    configured = os.getenv("EVIDENCE_DIR")
    if configured:
        root = Path(configured)
    else:
        output = Path(str(request.config.getoption("output")))
        root = output.parent if output.name == "browser-results" else Path("/tmp/roleradar-e2e")
    return ScreenshotPath(root, browser_name)
