"""Pure contracts and orchestration for the public job-analysis demo."""

from app.demo.contracts import DemoAnalysisResponse, DemoAnalyzeRequest
from app.demo.service import analyze_demo_job

__all__ = ["DemoAnalysisResponse", "DemoAnalyzeRequest", "analyze_demo_job"]
