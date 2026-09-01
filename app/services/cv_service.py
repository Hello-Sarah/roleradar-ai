import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from openai import OpenAI
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import CVDocument, GeneratedCV, Job
from app.schemas import CVDocumentRead, CVLibraryScanRead, GeneratedCVRead

SUPPORTED_CV_SUFFIXES = {".docx", ".pdf", ".txt"}
CV_PROMPT_VERSION = "tailored-cv-v1"
logger = logging.getLogger(__name__)


class CVLibraryError(ValueError):
    pass


class EvidenceBackedItem(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    source_quote: str = Field(min_length=2, max_length=800)


class TailoredCVSection(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    items: list[EvidenceBackedItem] = Field(min_length=1, max_length=20)


class TailoredCVContent(BaseModel):
    name: EvidenceBackedItem
    contact: EvidenceBackedItem | None = None
    headline: EvidenceBackedItem
    summary: list[EvidenceBackedItem] = Field(min_length=1, max_length=4)
    skills: list[EvidenceBackedItem] = Field(min_length=1, max_length=25)
    sections: list[TailoredCVSection] = Field(min_length=1, max_length=8)


@dataclass(frozen=True)
class ScanCounters:
    discovered: int
    added: int
    updated: int
    unchanged: int
    failed: list[str]


def _configured_directory(path_value: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise CVLibraryError(f"CV library path is not a directory: {path}")
    return path


def _extract_cv_text(path: Path) -> str:
    if path.suffix.casefold() == ".docx":
        document = Document(path)
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            parts.extend(cell.text for row in table.rows for cell in row.cells if cell.text.strip())
        text = "\n".join(parts)
    elif path.suffix.casefold() == ".pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    else:
        text = path.read_text(encoding="utf-8")
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) < 40:
        raise CVLibraryError("No usable CV text was found")
    return text


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def list_cv_documents(db: Session) -> list[CVDocument]:
    return list(
        db.scalars(
            select(CVDocument).where(CVDocument.active.is_(True)).order_by(CVDocument.file_name)
        ).all()
    )


def scan_cv_library(db: Session, settings: Settings) -> CVLibraryScanRead:
    library = _configured_directory(settings.cv_library_path)
    files = sorted(
        path
        for path in library.rglob("*")
        if path.is_file() and path.suffix.casefold() in SUPPORTED_CV_SUFFIXES
    )
    existing = {document.file_path: document for document in db.scalars(select(CVDocument))}
    seen: set[str] = set()
    added = updated = unchanged = 0
    failed: list[str] = []

    for path in files:
        resolved = str(path.resolve())
        seen.add(resolved)
        try:
            fingerprint = _fingerprint(path)
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            document = existing.get(resolved)
            if document and document.fingerprint == fingerprint:
                document.active = True
                unchanged += 1
                continue
            extracted_text = _extract_cv_text(path)
            if document is None:
                document = CVDocument(file_path=resolved)
                db.add(document)
                added += 1
            else:
                updated += 1
            document.file_name = path.name
            document.file_type = path.suffix.casefold().lstrip(".")
            document.fingerprint = fingerprint
            document.modified_at = modified_at
            document.extracted_text = extracted_text
            document.active = True
        except Exception as exc:
            logger.warning("Failed to index CV file %s: %s", path, exc)
            failed.append(f"{path.name}: {exc}")

    for path, document in existing.items():
        if path not in seen:
            document.active = False
    db.commit()
    documents = list_cv_documents(db)
    return CVLibraryScanRead(
        library_path=str(library),
        discovered=len(files),
        added=added,
        updated=updated,
        unchanged=unchanged,
        failed=failed,
        documents=[CVDocumentRead.model_validate(document) for document in documents],
    )


def _normalized_contains(corpus: str, quote: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    return normalize(quote) in normalize(corpus)


def _validate_evidence(content: TailoredCVContent, corpus: str) -> None:
    items = [content.name, content.headline, *content.summary, *content.skills]
    if content.contact:
        items.append(content.contact)
    items.extend(item for section in content.sections for item in section.items)
    unsupported = [
        item.text for item in items if not _normalized_contains(corpus, item.source_quote)
    ]
    if unsupported:
        raise CVLibraryError(
            "The model produced claims without verifiable CV evidence; generation was stopped"
        )


def _source_corpus(documents: list[CVDocument]) -> str:
    return "\n\n".join(
        f"=== SOURCE CV {document.id}: {document.file_name} ===\n{document.extracted_text}"
        for document in documents
    )


def _generate_content(
    documents: list[CVDocument], job: Job, settings: Settings
) -> TailoredCVContent:
    if not settings.openai_api_key:
        raise CVLibraryError("OPENAI_API_KEY is required to generate a tailored CV")
    corpus = _source_corpus(documents)
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    response = client.responses.parse(
        model=settings.openai_model,
        input=[
            {
                "role": "system",
                "content": (
                    "Create an ATS-friendly tailored CV using only facts present in the source "
                    "CVs. Never invent skills, employers, dates, achievements, metrics, education, "
                    "or credentials. Reorder and concisely rewrite true evidence for relevance. "
                    "Every output item must include an exact source_quote copied from the CV "
                    "corpus."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"TARGET JOB\nCompany: {job.company}\nTitle: {job.title}\n"
                    f"Description:\n{job.description}\n\nSOURCE CVS\n{corpus}"
                ),
            },
        ],
        text_format=TailoredCVContent,
    )
    if response.output_parsed is None:
        raise CVLibraryError("The model returned no structured CV content")
    _validate_evidence(response.output_parsed, corpus)
    logger.info("Generated validated CV content for job_id=%s", job.id)
    return response.output_parsed


def _safe_filename(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\n\r]+", " ", value).strip()[:120]


def _set_font(run, size: float, bold: bool = False, color: str = "222222") -> None:
    run.font.name = "Arial"
    fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:ascii"), "Arial")
    fonts.set(qn("w:hAnsi"), "Arial")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def _build_docx(content: TailoredCVContent, output: Path) -> None:
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.08

    name = document.add_paragraph()
    name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name.paragraph_format.space_after = Pt(2)
    _set_font(name.add_run(content.name.text), 20, bold=True, color="102A43")
    if content.contact:
        contact = document.add_paragraph()
        contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact.paragraph_format.space_after = Pt(4)
        _set_font(contact.add_run(content.contact.text), 9.5, color="52606D")
    headline = document.add_paragraph()
    headline.alignment = WD_ALIGN_PARAGRAPH.CENTER
    headline.paragraph_format.space_after = Pt(8)
    _set_font(headline.add_run(content.headline.text), 11, bold=True, color="334E68")

    def add_heading(text: str) -> None:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(8)
        paragraph.paragraph_format.space_after = Pt(3)
        _set_font(paragraph.add_run(text.upper()), 11, bold=True, color="1F4D78")

    add_heading("Professional Summary")
    summary = document.add_paragraph()
    summary.add_run(" ".join(item.text for item in content.summary))

    add_heading("Core Skills")
    skills = document.add_paragraph()
    skills.add_run(" • ".join(item.text for item in content.skills))

    for tailored_section in content.sections:
        add_heading(tailored_section.title)
        for item in tailored_section.items:
            paragraph = document.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.left_indent = Inches(0.22)
            paragraph.paragraph_format.first_line_indent = Inches(-0.16)
            paragraph.paragraph_format.space_after = Pt(3)
            paragraph.add_run(item.text)

    document.save(output)


def generate_tailored_cv(db: Session, job_id: int, settings: Settings) -> GeneratedCVRead:
    job = db.get(Job, job_id)
    if job is None:
        raise LookupError("Job not found")
    documents = list_cv_documents(db)
    if not documents:
        raise CVLibraryError("The CV library is empty; scan the configured folder first")
    content = _generate_content(documents, job, settings)
    # Preserve this deterministic gate at the generation boundary so validation cannot be
    # bypassed by a future provider adapter or an internal caller.
    _validate_evidence(content, _source_corpus(documents))
    output_directory = _configured_directory(settings.generated_cv_path)
    file_name = f"{_safe_filename(content.name.text)}—{_safe_filename(job.title)}-chatgpt.docx"
    output = output_directory / file_name
    temporary_output = output_directory / f".{uuid.uuid4().hex}.docx"
    try:
        _build_docx(content, temporary_output)
        output_hash = _fingerprint(temporary_output)
        temporary_output.replace(output)
        generated_at = datetime.now(UTC)
        generated = GeneratedCV(
            job_id=job.id,
            file_name=file_name,
            file_path=str(output),
            output_hash=output_hash,
            source_cv_ids=[document.id for document in documents],
            source_cv_hashes={str(document.id): document.fingerprint for document in documents},
            model_version=settings.openai_model,
            prompt_version=CV_PROMPT_VERSION,
            generated_at=generated_at,
        )
        db.add(generated)
        db.commit()
        db.refresh(generated)
    except Exception:
        db.rollback()
        temporary_output.unlink(missing_ok=True)
        raise
    logger.info(
        "Saved tailored CV id=%s for job_id=%s using source_cv_ids=%s to %s",
        generated.id,
        job.id,
        [document.id for document in documents],
        output,
    )
    return GeneratedCVRead(
        id=generated.id,
        job_id=job.id,
        file_name=file_name,
        file_path=str(output),
        source_cv_ids=[document.id for document in documents],
        source_cv_hashes={str(document.id): document.fingerprint for document in documents},
        output_hash=output_hash,
        model_version=settings.openai_model,
        prompt_version=CV_PROMPT_VERSION,
        generated_at=generated_at,
    )
