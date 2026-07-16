from fastapi.testclient import TestClient

JOB = {
    "company": "Example AI",
    "title": "Applied AI Engineer",
    "location": "Hong Kong",
    "url": "https://example.com/jobs/1",
    "posting_date": "2026-07-16",
    "description": (
        "Build applied AI products for banking customers using Python, SQL, Docker, "
        "AWS, large language models, and retrieval augmented generation."
    ),
    "source": "manual",
}


def test_full_job_workflow(client: TestClient) -> None:
    created = client.post("/api/v1/jobs", json=JOB)
    assert created.status_code == 201
    job = created.json()
    assert job["classification"]["category"] == "Applied AI Engineer"
    assert job["analysis"]["fit_score"] == sum(job["analysis"]["score_breakdown"].values())
    assert job["analysis"]["evidence"]

    assert client.post("/api/v1/jobs", json=JOB).status_code == 409
    updated = client.patch(f"/api/v1/jobs/{job['id']}/status", json={"status": "Applied"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "Applied"
    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["status_counts"]["Applied"] == 1


def test_validation_rejects_short_description(client: TestClient) -> None:
    assert client.post("/api/v1/jobs", json={**JOB, "description": "Too short"}).status_code == 422


def test_create_job_from_pasted_text(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs/from-text",
        json={
            "text": (
                "Company: Databricks\n"
                "Role: Applied AI Engineer\n"
                "Location: Singapore\n"
                "https://example.com/jobs/ai-2\n"
                "Build applied AI products using Python, SQL, Docker, AWS, and RAG."
            )
        },
    )

    assert response.status_code == 201
    job = response.json()
    assert job["company"] == "Databricks"
    assert job["title"] == "Applied AI Engineer"
    assert job["location"] == "Singapore"
    assert job["source"] == "pasted_text"
