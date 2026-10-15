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
        Scrapes jobs from Amazon Jobs search API mapping location and remote criteria.
        """
        search_term = scraper_input.search_term or "software"
        location_input = scraper_input.location or ""
        is_remote_requested = scraper_input.is_remote or "remote" in location_input.lower()

        resolved_query = search_term
        if is_remote_requested and "remote" not in resolved_query.lower() and "virtual" not in resolved_query.lower():
            resolved_query = f"{resolved_query} remote"

        query_parameters = [
            f"base_query={resolved_query}",
            f"result_limit={scraper_input.results_wanted or 25}",
        ]

        normalized_location = location_input.lower().strip()
        if "india" in normalized_location:
            query_parameters.append("country=IND")
        elif "united states" in normalized_location or "usa" in normalized_location or normalized_location == "us":
            query_parameters.append("country=USA")
        elif location_input:
            query_parameters.append(f"loc_query={location_input}")

        constructed_query_string = "&".join(query_parameters)
        target_url = f"https://www.amazon.jobs/en/search.json?{constructed_query_string}"

        try:
            response = self.session.get(
                target_url,
                timeout=getattr(scraper_input, "request_timeout", 60),
            )
            if response.status_code != 200:
                return JobResponse(jobs=[])
            data = response.json()
        except Exception:
            return JobResponse(jobs=[])

        collected_jobs = []
        raw_jobs_list = data.get("jobs") if isinstance(data, dict) else None
        for item in (raw_jobs_list or []):
            if not isinstance(item, dict):
                continue
            job_id = str(item.get("id_icims") or item.get("id") or "")
            title = item.get("title", "")
            company = "Amazon"
            job_url = f"https://www.amazon.jobs{item.get('job_path', '')}"
            location_str = item.get("location") or location_input or "Global"
            description = item.get("description", "") or item.get("basic_qualifications", "")
            is_virtual_job = (
                is_remote_requested
                or item.get("is_virtual") is True
                or "remote" in location_str.lower()
                or "virtual" in location_str.lower()
            )

            collected_jobs.append(
                JobPost(
                    id=job_id,
                    title=title,
                    company_name=company,
                    job_url=job_url,
                    location=Location(country=location_str),
                    description=description,
                    is_remote=is_virtual_job,
                )
            )

        return JobResponse(jobs=collected_jobs)

