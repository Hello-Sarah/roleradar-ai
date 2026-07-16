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
