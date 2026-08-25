from docx import Document

from app.config import Settings
from app.services.cv_service import (
    EvidenceBackedItem,
    TailoredCVContent,
    TailoredCVSection,
    _build_docx,
    _safe_filename,
    _validate_evidence,
    scan_cv_library,
)


def test_scan_cv_library_adds_and_reuses_fingerprint(db, tmp_path) -> None:
    source = tmp_path / "cv-library"
    source.mkdir()
    (source / "main.txt").write_text(
        "Jane Doe\nApplied AI Engineer\nBuilt and deployed Python APIs for banking users.",
        encoding="utf-8",
    )
    settings = Settings(cv_library_path=str(source))

    first = scan_cv_library(db, settings)
    second = scan_cv_library(db, settings)

    assert first.discovered == 1
    assert first.added == 1
    assert first.documents[0].file_name == "main.txt"
    assert second.added == 0
    assert second.unchanged == 1
    assert second.documents[0].id == first.documents[0].id


def test_build_docx_creates_readable_tailored_cv(tmp_path) -> None:
    content = TailoredCVContent(
        name=EvidenceBackedItem(text="Jane Doe", source_quote="Jane Doe"),
        contact=EvidenceBackedItem(
            text="jane@example.com · Hong Kong",
            source_quote="jane@example.com · Hong Kong",
        ),
        headline=EvidenceBackedItem(text="Applied AI Engineer", source_quote="Applied AI Engineer"),
        summary=[
            EvidenceBackedItem(
                text="Built production AI systems for banking users.",
                source_quote="Built production AI systems for banking users.",
            )
        ],
        skills=[EvidenceBackedItem(text="Python", source_quote="Python")],
        sections=[
            TailoredCVSection(
                title="Experience",
                items=[
                    EvidenceBackedItem(
                        text="Deployed a Python API.", source_quote="Deployed a Python API."
                    )
                ],
            )
        ],
    )
    output = tmp_path / "Jane Doe—Applied AI Engineer-chatgpt.docx"

    _build_docx(content, output)

    rendered = Document(output)
    text = "\n".join(paragraph.text for paragraph in rendered.paragraphs)
    assert "Jane Doe" in text
    assert "PROFESSIONAL SUMMARY" in text
    assert "Deployed a Python API." in text


def test_evidence_validation_rejects_unsupported_claim() -> None:
    content = TailoredCVContent(
        name=EvidenceBackedItem(text="Jane Doe", source_quote="Jane Doe"),
        headline=EvidenceBackedItem(text="AI Engineer", source_quote="AI Engineer"),
        summary=[EvidenceBackedItem(text="Invented claim", source_quote="not in source")],
        skills=[EvidenceBackedItem(text="Python", source_quote="Python")],
        sections=[
            TailoredCVSection(
                title="Experience",
                items=[EvidenceBackedItem(text="Built APIs", source_quote="Built APIs")],
            )
        ],
    )

    try:
        _validate_evidence(content, "Jane Doe AI Engineer Python Built APIs")
    except ValueError as exc:
        assert "without verifiable CV evidence" in str(exc)
    else:
        raise AssertionError("Unsupported claims must be rejected")


def test_safe_filename_removes_path_characters() -> None:
    assert _safe_filename("Jane/Smith: AI*Lead?") == "Jane Smith  AI Lead"
