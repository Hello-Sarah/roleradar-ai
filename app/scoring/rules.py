"""Versioned, data-only rules for deterministic Career Fit Score V2."""

from dataclasses import dataclass

SCORING_VERSION = "career-fit-v2"
PROMPT_VERSION = "career-fit-v2-explainer-v2-selections"

DIMENSION_MAXIMA: dict[str, int] = {
    "ai_depth": 20,
    "ownership": 20,
    "build_and_ship": 20,
    "product_exposure": 15,
    "technical_exposure": 15,
    "career_option_value": 10,
}


@dataclass(frozen=True)
class Rule:
    code: str
    points: int
    phrases: tuple[str, ...]


DIMENSION_RULES: dict[str, tuple[Rule, ...]] = {
    "ai_depth": (
        Rule("AI_AGENTIC", 4, ("agent", "agents", "agentic", "tool calling")),
        Rule("AI_WORKFLOW_ORCHESTRATION", 4, ("workflow orchestration",)),
        Rule("AI_RAG", 4, ("rag", "retrieval augmented generation")),
        Rule("AI_LLM", 4, ("llm", "llms", "large language model", "generative ai")),
        Rule("AI_EVALUATION", 4, ("evaluation", "evaluate", "evals")),
        Rule("AI_ARCHITECTURE", 4, ("ai architecture", "ai platform", "model architecture")),
    ),
    "ownership": (
        Rule("LEADERSHIP_TITLE", 4, ("lead", "head", "director", "manager")),
        Rule("OWNER", 8, ("own", "owner", "ownership")),
        Rule("DECISION_MAKER", 4, ("decision maker", "make decisions", "accountable")),
        Rule("END_TO_END", 8, ("end to end", "end-to-end", "0 to 1", "0-to-1", "0→1")),
    ),
    "build_and_ship": (
        Rule("BUILD", 4, ("build", "building", "hands-on")),
        Rule("PROTOTYPE", 4, ("prototype", "prototyping", "proof of concept")),
        Rule("DEPLOY", 4, ("deploy", "deployment", "customer deployment")),
        Rule("PRODUCTION", 4, ("production", "ship", "shipping")),
        Rule("ITERATE", 4, ("iterate", "iteration", "improve continuously")),
    ),
    "product_exposure": (
        Rule("DISCOVERY", 3, ("user discovery", "customer discovery", "discovery")),
        Rule("ROADMAP", 3, ("product roadmap", "roadmap")),
        Rule("PRIORITIZATION", 3, ("prioritize", "prioritization")),
        Rule("METRICS", 3, ("product metrics", "success metrics", "measure outcomes")),
        Rule("EXPERIMENTATION", 3, ("experiment", "experimentation", "iteration", "iterate")),
    ),
    "technical_exposure": (
        Rule("API", 3, ("api", "apis")),
        Rule("ARCHITECTURE", 3, ("technical architecture", "system architecture", "architecture")),
        Rule("DATA", 3, ("data pipeline", "data integration", "data systems", "data")),
        Rule("CODE", 3, ("code", "coding", "python", "sql")),
        Rule("INTEGRATION", 3, ("integration", "system design", "technical design")),
    ),
    "career_option_value": (
        Rule(
            "AI_NATIVE_ROLE",
            5,
            (
                "forward deployed",
                "applied ai",
                "ai product",
                "ai engineer",
                "ai solutions",
            ),
        ),
        Rule(
            "CUSTOMER_BUILDING",
            5,
            ("with customers", "customer deployment", "customer-facing", "0 to 1", "0-to-1"),
        ),
    ),
}

GREEN_FLAG_PHRASES: dict[str, tuple[str, ...]] = {
    "AGENTIC": ("agent", "agents", "agentic"),
    "RAG": ("rag", "retrieval augmented generation"),
    "LLM": ("llm", "llms", "large language model"),
    "TOOL_CALLING": ("tool calling",),
    "WORKFLOW_ORCHESTRATION": ("workflow orchestration",),
    "EVALUATION": ("evaluation", "evaluate", "evals"),
    "RAPID_PROTOTYPING": ("rapid prototype", "rapid prototyping"),
    "API_INTEGRATION": ("api integration", "api integrations"),
    "CUSTOMER_DEPLOYMENT": ("customer deployment", "deploy", "deployment"),
    "PRODUCTION": ("production",),
    "PRODUCT_ROADMAP": ("product roadmap", "roadmap"),
    "USER_DISCOVERY": ("user discovery", "customer discovery"),
    "AI_PLATFORM": ("ai platform",),
    "TECHNICAL_ARCHITECTURE": ("technical architecture",),
    "HANDS_ON": ("hands-on", "hands on"),
    "PROOF_OF_CONCEPT": ("proof of concept",),
    "ZERO_TO_ONE": ("0 to 1", "0-to-1", "0→1"),
    "END_TO_END_OWNERSHIP": ("end-to-end ownership", "end to end ownership", "own end to end"),
}

RED_FLAG_PHRASES: dict[str, tuple[str, ...]] = {
    "COORDINATION": ("coordinate", "coordination"),
    "STATUS_TRACKING": ("status tracking",),
    "REPORTING": ("reporting",),
    "STEERING_COMMITTEE": ("steering committee",),
    "GOVERNANCE": ("governance",),
    "VENDOR_MANAGEMENT": ("vendor management",),
    "PMO": ("pmo", "programme management office", "project management office"),
    "DOCUMENTATION": ("documentation",),
    "REQUIREMENT_GATHERING": ("requirement gathering", "requirements gathering"),
}

COUNTER_EVIDENCE_PHRASES: tuple[str, ...] = (
    "build",
    "prototype",
    "deploy",
    "design",
    "experiment",
    "evaluate",
    "evaluation",
    "architecture",
    "ai agent",
    "agentic",
    "production",
)

AI_TITLE_PHRASES: tuple[str, ...] = (
    "ai",
    "artificial intelligence",
    "generative ai",
    "genai",
    "llm",
)
