import re
from datetime import date

from app.ingestion.sources import SUPPORTED_COMPANIES
from app.schemas import JobCreate

FIELD_PATTERNS = {
    "company": re.compile(r"(?im)^\s*(?:company|公司)\s*[:：-]\s*(.+?)\s*$"),
    "title": re.compile(
        r"(?im)^\s*(?:job title|position|role|职位|職位|岗位|職位名稱)\s*[:：-]\s*(.+?)\s*$"
    ),
    "location": re.compile(r"(?im)^\s*(?:location|地点|地點|工作地点)\s*[:：-]\s*(.+?)\s*$"),
    "date": re.compile(
        r"(?im)^\s*(?:posted|posting date|date posted|发布日期|發佈日期)\s*[:：-]\s*(.+?)\s*$"
    ),
}
URL_PATTERN = re.compile(r"https?://[^\s<>\]\[)]+")
DATE_PATTERN = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")

ROLE_TERMS = (
    "forward deployed engineer",
    "applied ai engineer",
    "ai solutions engineer",
    "solutions architect",
    "technical product manager",
    "ai product manager",
    "product manager",
    "machine learning engineer",
    "data engineer",
    "research engineer",
    "research scientist",
    "project manager",
    "program manager",
    "consultant",
)
LOCATIONS = (
    "Hong Kong",
    "Singapore",
    "San Francisco",
    "New York",
    "London",
    "Tokyo",
    "Sydney",
    "Shanghai",
    "Beijing",
    "Shenzhen",
    "Remote",
    "香港",
    "新加坡",
)


def _label_value(text: str, field: str) -> str | None:
    match = FIELD_PATTERNS[field].search(text)
    return match.group(1).strip() if match else None


def _infer_company(text: str) -> str:
    explicit = _label_value(text, "company")
    if explicit:
        return explicit[:200]
    folded = text.casefold()
    for source in SUPPORTED_COMPANIES:
        if source.company.casefold() in folded:
            return source.company
    return "Unknown Company"


def _infer_title(text: str, lines: list[str]) -> str:
    explicit = _label_value(text, "title")
    if explicit:
        return explicit[:300]
    for line in lines[:20]:
        if any(term in line.casefold() for term in ROLE_TERMS):
            return line[:300]
    return lines[0][:300] if lines else "Unidentified Role"


def _infer_location(text: str) -> str:
    explicit = _label_value(text, "location")
    if explicit:
        return explicit[:200]
    folded = text.casefold()
    for location in LOCATIONS:
        if location.casefold() in folded:
            return location
    return "Location not specified"


def _infer_date(text: str) -> date | None:
    labelled = _label_value(text, "date") or ""
    match = DATE_PATTERN.search(labelled) or DATE_PATTERN.search(text[:1000])
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def extract_job_from_text(raw_text: str) -> JobCreate:
    """Extract normalized metadata while retaining the full posting as evidence."""
    text = raw_text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    url_match = URL_PATTERN.search(text)
    return JobCreate(
        company=_infer_company(text),
        title=_infer_title(text, lines),
        location=_infer_location(text),
        url=url_match.group(0).rstrip(".,;") if url_match else None,
        posting_date=_infer_date(text),
        description=text,
        source="pasted_text",
    )
