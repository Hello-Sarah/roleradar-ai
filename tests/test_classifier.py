from app.analysis.classifier import classify_job
from app.schemas import RoleCategory


def test_classifies_forward_deployed_role() -> None:
    result = classify_job(
        "Forward Deployed Engineer",
        "Work directly with customers on customer deployment of AI systems.",
    )
    assert result.category == RoleCategory.FORWARD_DEPLOYED_ENGINEER
    assert result.confidence >= 0.7
    assert result.evidence


def test_unknown_role_is_flagged_for_review() -> None:
    result = classify_job("Operations Lead", "Coordinate business stakeholders and reporting.")
    assert result.confidence < 0.5
    assert "review" in result.evidence[0]
