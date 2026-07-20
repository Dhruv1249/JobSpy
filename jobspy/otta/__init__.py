"""
Otta curated tech job board scraper.
"""

from bs4 import BeautifulSoup
from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Scraper,
    ScraperInput,
    Site
)
from jobspy.util import create_session

class Otta(Scraper):
    """
    Scraper for Otta curated positions.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Otta scraper.
        """
        super().__init__(Site.OTTA, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.session = create_session(
            proxies=self.proxies,
            ca_cert=ca_cert,
            is_tls=False,
            has_retry=True,
            delay=5,
            clear_cookies=True
        )
        if user_agent:
            self.session.headers.update({"User-Agent": user_agent})
        else:
            self.session.headers.update({
                "User-Agent": "JobCruiser/1.0",
                "Accept": "application/json"
            })

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrape jobs from Otta public API endpoint.
        """
        search_term = scraper_input.search_term or "engineer"
        url = f"https://api.otta.com/v1/jobs/search?q={search_term}"
        try:
            response = self.session.get(
                url,
                timeout=getattr(scraper_input, "request_timeout", 60)
            )
            if response.status_code != 200:
                return JobResponse(jobs=[])
            data = response.json()
        except Exception:
            return JobResponse(jobs=[])

        jobs = []
        for job_data in data.get("jobs", []):
            title = job_data.get("title", "")
            company = job_data.get("company", {}).get("name", "")
            job_url = job_data.get("applyUrl") or job_data.get("url", "")
            location_str = job_data.get("location", "Remote")
            description = job_data.get("summary", "")

            jobs.append(
                JobPost(
                    id=str(job_data.get("id", "")),
                    title=title,
                    company_name=company,
                    job_url=job_url,
                    location=Location(country=location_str),
                    description=description,
                    is_remote="remote" in location_str.lower()
                )
            )

            if len(jobs) >= scraper_input.results_wanted:
                break

        return JobResponse(jobs=jobs)
