"""
RemoteOK job board scraper.
"""

from datetime import date
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

class RemoteOK(Scraper):
    """
    Scraper for RemoteOK API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize RemoteOK scraper.
        """
        super().__init__(Site.REMOTEOK, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        Scrape job postings from RemoteOK.
        """
        url = "https://remoteok.com/api"
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
        search_term_lower = scraper_input.search_term.lower() if scraper_input.search_term else None

        for job_data in data:
            if not isinstance(job_data, dict) or "legal" in job_data:
                continue

            title = job_data.get("position", "")
            company = job_data.get("company", "")
            description_html = job_data.get("description", "")
            description = markdown_converter(description_html) if description_html else ""

            if search_term_lower:
                title_matches = search_term_lower in title.lower()
                company_matches = search_term_lower in company.lower()
                desc_matches = search_term_lower in description.lower()
                if not (title_matches or company_matches or desc_matches):
                    continue

            location_str = job_data.get("location", "Worldwide")
            location = Location(country=location_str)

            epoch_str = job_data.get("epoch")
            date_posted = None
            if epoch_str:
                try:
                    date_posted = date.fromtimestamp(int(epoch_str))
                except Exception:
                    pass

            emails = extract_emails_from_text(description) if description else []

            jobs.append(
                JobPost(
                    id=job_data.get("id"),
                    title=title,
                    company_name=company,
                    job_url=job_data.get("url"),
                    location=location,
                    description=description,
                    date_posted=date_posted,
                    emails=emails,
                    is_remote=True
                )
            )

            if len(jobs) >= scraper_input.results_wanted:
                break

        return JobResponse(jobs=jobs)
