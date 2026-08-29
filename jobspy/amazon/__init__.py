"""
Amazon Jobs direct scraper for JobSpy.
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

class Amazon(Scraper):
    """
    Scraper for Amazon Jobs search API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Amazon scraper.
        """
        super().__init__(Site.AMAZON, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "application/json"
            })

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrape jobs from Amazon Jobs API.
        """
        search_term = scraper_input.search_term or "software"
        location = scraper_input.location or "India"
        url = f"https://www.amazon.jobs/en/search.json?base_query={search_term}&loc_query={location}&result_limit={scraper_input.results_wanted}"
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
            job_id = str(item.get("id_icims") or item.get("id") or "")
            title = item.get("title", "")
            company = "Amazon"
            job_url = f"https://www.amazon.jobs{item.get('job_path', '')}"
            location_str = item.get("location", location)
            description = item.get("description", "") or item.get("basic_qualifications", "")

            jobs.append(
                JobPost(
                    id=job_id,
                    title=title,
                    company_name=company,
                    job_url=job_url,
                    location=Location(country=location_str),
                    description=description,
                    is_remote="remote" in location_str.lower()
                )
            )

        return JobResponse(jobs=jobs)
