"""
Working Nomads job board scraper.
"""

from datetime import datetime
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

class WorkingNomads(Scraper):
    """
    Scraper for Working Nomads API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Working Nomads scraper.
        """
        super().__init__(Site.WORKING_NOMADS, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        Scrape job postings from Working Nomads.
        """
        url = "https://www.workingnomads.com/api/exposed_jobs/"
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
            if not isinstance(job_data, dict):
                continue

            title = job_data.get("title", "")
            company = job_data.get("company_name", "") or job_data.get("company", "")
            description_html = job_data.get("description", "")
            description = markdown_converter(description_html) if description_html else ""

            location_str = job_data.get("location", "Worldwide")
            location = Location(country=location_str)

            pub_date_str = job_data.get("pub_date") or job_data.get("created")
            date_posted = None
            if pub_date_str:
                try:
                    date_posted = datetime.strptime(pub_date_str[:10], "%Y-%m-%d").date()
                except Exception:
                    pass

            emails = extract_emails_from_text(description) if description else []

            jobs.append(
                JobPost(
                    id=str(job_data.get("id")),
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
