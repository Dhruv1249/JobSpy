"""
The Muse job board scraper.
"""

from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Scraper,
    ScraperInput,
    Site
)
from jobspy.util import (
    create_session,
    markdown_converter,
    extract_emails_from_text
)

class TheMuse(Scraper):
    """
    Scraper for The Muse API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize The Muse scraper.
        """
        super().__init__(Site.THE_MUSE, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
                "User-Agent": "JobCruiser/1.0"
            })

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrape job postings from The Muse.
        """
        url = "https://www.themuse.com/api/public/jobs"
        params = {"page": 1}
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=getattr(scraper_input, "request_timeout", 60)
            )
            if response.status_code != 200:
                return JobResponse(jobs=[])
            data = response.json()
        except Exception:
            return JobResponse(jobs=[])

        jobs = []
        search_term_lower = scraper_input.search_term.lower() if scraper_input.search_term else None

        for job_data in data.get("results", []):
            title = job_data.get("name", "")
            company = job_data.get("company", {}).get("name", "")
            description_html = job_data.get("contents", "")
            description = markdown_converter(description_html) if description_html else ""

            if search_term_lower:
                title_matches = search_term_lower in title.lower()
                company_matches = search_term_lower in company.lower()
                desc_matches = search_term_lower in description.lower()
                if not (title_matches or company_matches or desc_matches):
                    continue

            locations = job_data.get("locations", [])
            location_str = locations[0].get("name", "USA") if locations else "USA"
            location = Location(country=location_str)

            job_url = job_data.get("refs", {}).get("landing_page", "")
            emails = extract_emails_from_text(description) if description else []

            jobs.append(
                JobPost(
                    id=str(job_data.get("id")),
                    title=title,
                    company_name=company,
                    job_url=job_url,
                    location=location,
                    description=description,
                    emails=emails,
                    is_remote="remote" in location_str.lower()
                )
            )

            if len(jobs) >= scraper_input.results_wanted:
                break

        return JobResponse(jobs=jobs)
