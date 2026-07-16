import hashlib
import re

from app.schemas import JobCreate


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_job(job: JobCreate) -> JobCreate:
    data = job.model_dump()
    for field in ("company", "title", "location", "description", "source"):
        data[field] = normalize_space(str(data[field]))
    return JobCreate.model_validate(data)


def job_fingerprint(job: JobCreate) -> str:
    canonical = "|".join(
        [
            normalize_space(job.company).casefold(),
            normalize_space(job.title).casefold(),
            normalize_space(job.location).casefold(),
            str(job.url or "").rstrip("/").casefold(),
        ]
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
