"""
Lever ATS job board scraper.
"""

import datetime
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

class Lever(Scraper):
    """
    Scraper for Lever API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Lever scraper.
        """
        super().__init__(Site.LEVER, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        self.base_url = "https://api.lever.co/v0/postings"

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
        for job_data in data:
            description_html = job_data.get("description", "")
            description_text = ""
            if description_html:
                soup = BeautifulSoup(description_html, "html.parser")
                description_text = soup.get_text(separator=" ", strip=True)

            list_contents = []
            for item in job_data.get("lists", []):
                item_title = item.get("text", "")
                item_html = item.get("content", "")
                if item_html:
                    soup_item = BeautifulSoup(item_html, "html.parser")
                    list_contents.append(f"{item_title}\n{soup_item.get_text(separator=' ', strip=True)}")

            if list_contents:
                description_text += "\n\n" + "\n\n".join(list_contents)

            created_at_ms = job_data.get("createdAt")
            date_posted = None
            if created_at_ms:
                try:
                    date_posted = datetime.datetime.fromtimestamp(
                        created_at_ms / 1000.0,
                        datetime.timezone.utc
                    ).date()
                except Exception:
                    pass

            categories = job_data.get("categories", {})
            location_name = categories.get("location", "Remote")

            jobs.append(
                JobPost(
                    id=str(job_data.get("id")),
                    title=job_data.get("title", ""),
                    company_name=company.capitalize(),
                    job_url=job_data.get("hostedUrl", ""),
                    location=Location(country=location_name),
                    description=description_text,
                    date_posted=date_posted,
                    is_remote="remote" in location_name.lower()
                )
            )

        return JobResponse(jobs=jobs)
