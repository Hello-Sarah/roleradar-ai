"""Release image must retain the migration assets used by API startup."""

from pathlib import Path


def test_docker_runtime_includes_alembic_assets() -> None:
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    copy_lines = [line.split() for line in dockerfile.splitlines() if line.startswith("COPY ")]
    copied_sources = {source for line in copy_lines for source in line[1:-1]}
    assert "alembic.ini" in copied_sources, "API startup needs the root Alembic configuration"
    assert "alembic" in copied_sources, "API startup needs the revision scripts"
    assert (root / "alembic.ini").is_file()
    assert (root / "alembic" / "env.py").is_file()
    assert list((root / "alembic" / "versions").glob("*.py"))
