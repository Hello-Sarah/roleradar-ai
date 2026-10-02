import hashlib
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import pytest

from app.config import Settings, get_settings
from app.database.models import GeneratedCV, Job
from app.services.cv_service import (
    EvidenceBackedItem,
    TailoredCVContent,
    TailoredCVSection,
    scan_cv_library,
)


def _content() -> TailoredCVContent:
    evidence = "Built reliable Python APIs for banking users."
    return TailoredCVContent(
        name=EvidenceBackedItem(text="Jane Doe", source_quote="Jane Doe"),
        contact=EvidenceBackedItem(
            text="jane@example.com · Hong Kong",
            source_quote="jane@example.com · Hong Kong",
        ),
        headline=EvidenceBackedItem(text="Applied AI Engineer", source_quote="Applied AI Engineer"),
        summary=[EvidenceBackedItem(text=evidence, source_quote=evidence)],
        skills=[EvidenceBackedItem(text="Python", source_quote="Python")],
        sections=[
            TailoredCVSection(
                title="Experience",
                items=[EvidenceBackedItem(text=evidence, source_quote=evidence)],
            )
        ],
    )


def _prepared_generation(db, tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    source_file = source / "main.txt"
    source_file.write_text(
        "Jane Doe\njane@example.com · Hong Kong\nApplied AI Engineer\n"
        "Built reliable Python APIs for banking users.",
        encoding="utf-8",
    )
    scan = scan_cv_library(db, Settings(cv_library_path=str(source)))
    job = Job(
        fingerprint="api-generated-cv-job",
        company="Example AI",
        title="Applied AI Engineer",
        location="Hong Kong",
        description="Build reliable AI systems.",
        source="manual",
        status="Saved",
    )
    db.add(job)
    db.commit()
    settings = Settings(
        cv_library_path=str(source),
        generated_cv_path=str(output),
        openai_api_key="test-key",
        openai_model="test-model",
    )
    return job, settings, scan


@pytest.mark.parametrize(
    "file_name",
    [
        "..%2Foutside.docx",
        "..%5Coutside.docx",
        "nested%2Fcv.docx",
        "nested/cv.docx",
        r"nested\cv.docx",
        "file%00.docx",
    ],
)
def test_download_endpoint_rejects_encoded_and_plain_separators(
    client, tmp_path, file_name
) -> None:
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        generated_cv_path=str(tmp_path)
    )

    response = client.get(f"/api/v1/generated-cvs/999/{file_name}")

    assert response.status_code == 400


def test_download_rejects_symlink_escaping_output_directory(client, db, tmp_path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    external = tmp_path / "outside.docx"
    external.write_bytes(b"private")
    linked = output / "linked.docx"
    linked.symlink_to(external)
    job = Job(
        fingerprint="api-symlink-job",
        company="Example AI",
        title="Applied AI Engineer",
        location="Hong Kong",
        description="Build reliable AI systems.",
        source="manual",
        status="Saved",
    )
    db.add(job)
    db.flush()
    generated = GeneratedCV(
        job_id=job.id,
        file_name=linked.name,
        file_path=str(linked),
        output_hash=hashlib.sha256(external.read_bytes()).hexdigest(),
        source_cv_ids=[],
        source_cv_hashes={},
        model_version="test-model",
        prompt_version="test-prompt",
        generated_at=datetime(2026, 8, 25, tzinfo=UTC),
    )
    db.add(generated)
    db.commit()
    client.app.dependency_overrides[get_settings] = lambda: Settings(generated_cv_path=str(output))

    response = client.get(f"/api/v1/generated-cvs/{generated.id}/{linked.name}")

    assert response.status_code == 404


def test_generate_response_and_download_preserve_the_intended_artifact(
    client, db, tmp_path, monkeypatch
) -> None:
    job, settings, scan = _prepared_generation(db, tmp_path)
    client.app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.services.cv_service._generate_content", lambda *_: _content())

    generated_response = client.post(f"/api/v1/jobs/{job.id}/tailored-cv")

    assert generated_response.status_code == 200
    generated = generated_response.json()
    stored = db.get(GeneratedCV, generated["id"])
    assert generated["file_name"] == "Jane Doe—Applied AI Engineer-chatgpt.docx"
    assert generated["file_path"] == stored.file_path
    assert generated["source_cv_ids"] == [document.id for document in scan.documents]
    assert generated["source_cv_hashes"] == {
        str(document.id): document.fingerprint for document in scan.documents
    }

    response = client.get(
        f"/api/v1/generated-cvs/{generated['id']}/{quote(generated['file_name'], safe='')}"
    )

    assert response.status_code == 200
    assert response.content == Path(generated["file_path"]).read_bytes()
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert response.headers["content-disposition"].startswith("attachment;")
    assert quote(generated["file_name"], safe="") in response.headers["content-disposition"]


def test_generated_cv_detail_returns_the_exact_durable_artifact(client, db, tmp_path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    artifact = output / "tailored.docx"
    artifact.write_bytes(b"generated")
    job = Job(
        fingerprint="generated-cv-detail-job",
        company="Example AI",
        title="Applied AI Engineer",
        location="Hong Kong",
        description="Build reliable AI systems.",
        source="manual",
        status="Saved",
    )
    db.add(job)
    db.flush()
    generated = GeneratedCV(
        job_id=job.id,
        file_name=artifact.name,
        file_path=str(artifact),
        output_hash=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        source_cv_ids=[2],
        source_cv_hashes={"2": "abc123"},
        model_version="test-model",
        prompt_version="test-prompt",
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    db.add(generated)
    db.commit()

    response = client.get(f"/api/v1/generated-cvs/{generated.id}/metadata")

    assert response.status_code == 200
    assert response.json()["id"] == generated.id
    assert response.json()["job_id"] == job.id
    assert response.json()["file_name"] == "tailored.docx"
    assert response.json()["output_hash"] == hashlib.sha256(b"generated").hexdigest()
    assert client.get("/api/v1/generated-cvs/99999/metadata").status_code == 404


def test_download_rejects_missing_generated_artifact(client, tmp_path) -> None:
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        generated_cv_path=str(tmp_path)
    )

    assert client.get("/api/v1/generated-cvs/999/missing.docx").status_code == 404
