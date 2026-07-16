from app.ingestion.text_extractor import extract_job_from_text


def test_extracts_labelled_job_posting() -> None:
    job = extract_job_from_text(
        """
        Company: OpenAI
        Job Title: Forward Deployed Engineer
        Location: Singapore
        Posted: 2026-07-15
        https://example.com/jobs/fde

        Work with enterprise customers to deploy applied AI systems.
        Build production solutions using Python, SQL, Docker, and AWS.
        """
    )

    assert job.company == "OpenAI"
    assert job.title == "Forward Deployed Engineer"
    assert job.location == "Singapore"
    assert str(job.url) == "https://example.com/jobs/fde"
    assert job.posting_date.isoformat() == "2026-07-15"
    assert job.source == "pasted_text"


def test_infers_metadata_from_unlabelled_text() -> None:
    job = extract_job_from_text(
        """
        Applied AI Engineer
        Join Anthropic in Hong Kong to build reliable large language model products.
        You will use Python and Docker and partner with banking customers.
        This role requires strong communication and production engineering experience.
        """
    )

    assert job.company == "Anthropic"
    assert job.title == "Applied AI Engineer"
    assert job.location == "Hong Kong"
