#!/usr/bin/env python3
"""Run the acceptance API with a deterministic provider over synthetic CV evidence."""

from __future__ import annotations

import os

import uvicorn

import app.services.cv_service as cv_service


def _synthetic_content(documents, job, settings):
    del job, settings
    lines = [line for line in documents[0].extracted_text.splitlines() if line.strip()]
    name = lines[0]
    evidence = lines[-1]
    return cv_service.TailoredCVContent(
        name=cv_service.EvidenceBackedItem(text=name, source_quote=name),
        headline=cv_service.EvidenceBackedItem(text=name, source_quote=name),
        summary=[cv_service.EvidenceBackedItem(text=evidence, source_quote=evidence)],
        skills=[cv_service.EvidenceBackedItem(text=evidence, source_quote=evidence)],
        sections=[
            cv_service.TailoredCVSection(
                title="Experience",
                items=[cv_service.EvidenceBackedItem(text=evidence, source_quote=evidence)],
            )
        ],
    )


def main() -> None:
    cv_service._generate_content = _synthetic_content
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("ACCEPTANCE_API_PORT", "8000")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
