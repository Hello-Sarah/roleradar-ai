import pytest
from docx import Document
from fastapi import HTTPException

from app.api.routes import download_generated_cv
from app.config import Settings, get_settings


@pytest.mark.parametrize(
    "file_name", ["..%2Foutside.docx", "..%5Coutside.docx", "nested%2Fcv.docx"]
)
def test_download_rejects_percent_encoded_traversal_and_separators(tmp_path, file_name) -> None:
    with pytest.raises(HTTPException) as error:
        download_generated_cv(file_name, Settings(generated_cv_path=str(tmp_path)))

    assert error.value.status_code == 400


def test_download_rejects_symlink_escaping_output_directory(client, tmp_path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    external = tmp_path / "outside.docx"
    external.write_bytes(b"private")
    (output / "linked.docx").symlink_to(external)
    client.app.dependency_overrides[get_settings] = lambda: Settings(generated_cv_path=str(output))

    response = client.get("/api/v1/generated-cvs/linked.docx")

    assert response.status_code == 404


def test_download_returns_only_valid_generated_docx(client, tmp_path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    generated = output / "Jane Doe—Applied AI Engineer-chatgpt.docx"
    document = Document()
    document.add_paragraph("Jane Doe")
    document.save(generated)
    client.app.dependency_overrides[get_settings] = lambda: Settings(generated_cv_path=str(output))

    response = client.get(f"/api/v1/generated-cvs/{generated.name}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert response.content.startswith(b"PK")


def test_download_rejects_missing_file(client, tmp_path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    client.app.dependency_overrides[get_settings] = lambda: Settings(generated_cv_path=str(output))

    assert client.get("/api/v1/generated-cvs/missing.docx").status_code == 404


def test_download_rejects_non_docx_file(client, tmp_path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "not-a-cv.txt").write_text("private", encoding="utf-8")
    client.app.dependency_overrides[get_settings] = lambda: Settings(generated_cv_path=str(output))

    assert client.get("/api/v1/generated-cvs/not-a-cv.txt").status_code == 400
