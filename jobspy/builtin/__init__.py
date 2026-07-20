"""
BuiltIn tech job board scraper.
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
from jobspy.util import create_session, markdown_converter

class BuiltIn(Scraper):
    """
    Scraper for BuiltIn tech positions.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize BuiltIn scraper.
        """
        super().__init__(Site.BUILTIN, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
                "Accept": "text/html,application/xhtml+xml"
            })

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrape jobs from BuiltIn.
        """
        search_term = scraper_input.search_term or "developer"
        url = f"https://builtin.com/jobs?search={search_term}"
        try:
            response = self.session.get(
                url,
                timeout=getattr(scraper_input, "request_timeout", 60)
            )
            if response.status_code != 200:
                return JobResponse(jobs=[])
            soup = BeautifulSoup(response.content, "html.parser")
        except Exception:
            return JobResponse(jobs=[])

        jobs = []
        for card in soup.find_all("div", class_=lambda c: c and "job-card" in c):
            title_elem = card.find("a", class_=lambda c: c and "job-title" in c)
            company_elem = card.find("div", class_=lambda c: c and "company-name" in c)
            
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"
            job_url = "https://builtin.com" + title_elem.get("href", "")

            loc_elem = card.find("div", class_=lambda c: c and "job-location" in c)
            location_str = loc_elem.get_text(strip=True) if loc_elem else "Remote"

            desc_elem = card.find("div", class_=lambda c: c and "job-description" in c)
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            jobs.append(
                JobPost(
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
