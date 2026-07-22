"""
Microsoft Careers direct scraper for JobSpy.
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

class Microsoft(Scraper):
    """
    Scraper for Microsoft Careers search API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Microsoft scraper.
        """
        super().__init__(Site.MICROSOFT, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        Scrape jobs from Microsoft Careers API.
        """
        search_term = scraper_input.search_term or "software"
        location = scraper_input.location or "India"
        url = f"https://services.careers.microsoft.com/api/v1/search?q={search_term}&lc={location}&l=en_us&pg=1&pgSz={scraper_input.results_wanted}"
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
        jobs_list = data.get("operationResult", {}).get("result", {}).get("jobs", [])
        for item in jobs_list:
            job_id = str(item.get("jobId", ""))
            title = item.get("title", "")
            company = "Microsoft"
            job_url = f"https://jobs.careers.microsoft.com/global/en/job/{job_id}"
            location_str = item.get("properties", {}).get("primaryLocation", location)
            description = item.get("properties", {}).get("description", "")

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
