"""
Levels.fyi jobs scraper.
"""

from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Scraper,
    ScraperInput,
    Site
)
from jobspy.util import create_session

class LevelsFyi(Scraper):
    """
    Scraper for Levels.fyi job postings.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Levels.fyi scraper.
        """
        super().__init__(Site.LEVELSFYI, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        Scrape jobs from Levels.fyi API.
        """
        search_term = scraper_input.search_term or "software"
        url = f"https://www.levels.fyi/api/jobs?searchText={search_term}"
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
        for item in data.get("jobs", []):
            title = item.get("title", "")
            company = item.get("companyName", "")
            job_url = item.get("link", "")
            location_str = item.get("location", "Remote")
            description = item.get("description", "")

            jobs.append(
                JobPost(
                    id=str(item.get("id", "")),
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
