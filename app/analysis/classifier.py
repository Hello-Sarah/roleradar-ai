from dataclasses import dataclass

from app.schemas import ClassificationRead, RoleCategory


@dataclass(frozen=True)
class CategoryRule:
    category: RoleCategory
    phrases: tuple[str, ...]


RULES = (
    CategoryRule(
        RoleCategory.FORWARD_DEPLOYED_ENGINEER,
        ("forward deployed", "customer deployment", "client-facing engineer", "field engineer"),
    ),
    CategoryRule(
        RoleCategory.APPLIED_AI_ENGINEER,
        ("applied ai", "llm engineer", "machine learning engineer", "ai engineer", "rag"),
    ),
    CategoryRule(
        RoleCategory.AI_SOLUTIONS,
        ("ai solutions", "solutions architect", "solution engineer", "sales engineer"),
    ),
    CategoryRule(
        RoleCategory.AI_PRODUCT,
        ("ai product", "product manager, ai", "product manager ai", "genai product"),
    ),
    CategoryRule(
        RoleCategory.TECHNICAL_PRODUCT_MANAGER,
        ("technical product manager", "technical program product", "platform product manager"),
    ),
    CategoryRule(
        RoleCategory.GENAI_CONSULTING,
        (
            "genai consultant",
            "generative ai consultant",
            "ai consulting",
            "transformation consultant",
        ),
    ),
    CategoryRule(
        RoleCategory.TRADITIONAL_DATA_ENGINEERING,
        ("data engineer", "etl", "data warehouse", "data pipeline"),
    ),
    CategoryRule(
        RoleCategory.PROJECT_MANAGEMENT,
        ("project manager", "program manager", "pmo"),
    ),
    CategoryRule(
        RoleCategory.RESEARCH,
        ("research scientist", "research engineer", "postdoctoral", "publication record"),
    ),
)


def classify_job(title: str, description: str) -> ClassificationRead:
    title_text = title.casefold()
    full_text = f"{title} {description}".casefold()
    ranked: list[tuple[float, CategoryRule, list[str]]] = []
    for rule in RULES:
        evidence = [phrase for phrase in rule.phrases if phrase in full_text]
        title_hits = sum(phrase in title_text for phrase in rule.phrases)
        score = len(evidence) + (2 * title_hits)
        ranked.append((float(score), rule, evidence))

    score, rule, evidence = max(ranked, key=lambda item: item[0])
    if score == 0:
        rule = next(item for item in RULES if item.category == RoleCategory.PROJECT_MANAGEMENT)
        return ClassificationRead(
            category=rule.category,
            confidence=0.35,
            evidence=["No strong role-family keywords; classification requires review"],
        )
    confidence = min(0.95, 0.5 + (score * 0.1))
    return ClassificationRead(
        category=rule.category,
        confidence=round(confidence, 2),
        evidence=[f"Matched '{phrase}'" for phrase in evidence[:4]],
    )
