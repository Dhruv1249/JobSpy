"""
Dice tech job board scraper.
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

class Dice(Scraper):
    """
    Scraper for Dice tech jobs API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Dice scraper.
        """
        super().__init__(Site.DICE, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        Scrape jobs from Dice public REST API.
        """
        search_term = scraper_input.search_term or "developer"
        url = f"https://api.dice.com/jobs/v1/search?q={search_term}&pageSize={scraper_input.results_wanted}"
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
        for result in data.get("resultItemList", []):
            title = result.get("title", "")
            company = result.get("company", "")
            job_url = result.get("detailUrl", "")
            location_str = result.get("location", "Remote")
            description = result.get("snippet", "")

            jobs.append(
                JobPost(
                    id=str(result.get("id", "")),
                    title=title,
                    company_name=company,
                    job_url=job_url,
                    location=Location(country=location_str),
                    description=description,
                    is_remote="remote" in location_str.lower()
                )
            )

        return JobResponse(jobs=jobs)
