from dataclasses import dataclass


@dataclass(frozen=True)
class CompanySource:
    company: str
    careers_url: str
    ingestion_mode: str = "manual_review"


# Phase 2 allowlist. A source graduates from manual_review only after an official,
# structured feed is verified and contract-tested. No HTML scraping is performed.
SUPPORTED_COMPANIES = (
    CompanySource("OpenAI", "https://openai.com/careers/"),
    CompanySource("Anthropic", "https://www.anthropic.com/careers"),
    CompanySource("Google", "https://www.google.com/about/careers/applications/jobs/results/"),
    CompanySource("Microsoft", "https://jobs.careers.microsoft.com/global/en/search"),
    CompanySource("AWS", "https://www.amazon.jobs/en/teams/amazon-web-services"),
    CompanySource("Databricks", "https://www.databricks.com/company/careers/open-positions"),
    CompanySource("Palantir", "https://www.palantir.com/careers/"),
    CompanySource("Capgemini", "https://www.capgemini.com/careers/join-capgemini/job-search/"),
    CompanySource("HSBC", "https://www.hsbc.com/careers/find-a-job"),
    CompanySource("JPMorgan", "https://careers.jpmorgan.com/global/en/search-results"),
    CompanySource("Goldman Sachs", "https://higher.gs.com/"),
    CompanySource("Airwallex", "https://www.airwallex.com/careers"),
    CompanySource("Standard Chartered", "https://www.sc.com/en/global-careers/"),
)
