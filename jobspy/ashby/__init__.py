"""
Ashby ATS job board scraper.
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

class Ashby(Scraper):
    """
    Scraper for Ashby API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Ashby scraper.
        """
        super().__init__(Site.ASHBY, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        self.base_url = "https://api.ashbyhq.com/posting-api/job-board"

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrape jobs for the company slug provided in search_term.
        """
        company = scraper_input.search_term
        if not company:
            return JobResponse(jobs=[])

        url = f"{self.base_url}/{company}"
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
            description_html = job_data.get("descriptionHtml", "")
            description_text = ""
            if description_html:
                soup = BeautifulSoup(description_html, "html.parser")
                description_text = soup.get_text(separator=" ", strip=True)

            location_name = job_data.get("location", "Remote")
            
            jobs.append(
                JobPost(
                    id=str(job_data.get("id")),
                    title=job_data.get("title", ""),
                    company_name=company.capitalize(),
                    job_url=job_data.get("jobUrl", ""),
                    location=Location(country=location_name),
                    description=description_text,
                    is_remote="remote" in location_name.lower()
                )
            )

        return JobResponse(jobs=jobs)
