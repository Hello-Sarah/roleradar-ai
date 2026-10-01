import tomllib
from pathlib import Path


def test_coverage_source_is_configured_by_coverage_py() -> None:
    """Keep pytest-cov from trying to resolve an already-imported package as its source."""
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert config["tool"]["coverage"]["run"]["source"] == ["app"]
    assert config["tool"]["coverage"]["run"]["relative_files"] is True
    assert "--cov=app" not in config["tool"]["pytest"]["ini_options"]["addopts"]
    assert "--cov" in config["tool"]["pytest"]["ini_options"]["addopts"].split()
