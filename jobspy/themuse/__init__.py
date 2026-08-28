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
        Scrape job postings from The Muse public REST API with pagination.
        """
        base_endpoint_url = "https://www.themuse.com/api/public/jobs"
        collected_job_posts = []
        current_page_number = 1
        maximum_results_wanted = scraper_input.results_wanted or 100
        request_timeout_seconds = getattr(scraper_input, "request_timeout", 60)

        while len(collected_job_posts) < maximum_results_wanted:
            query_parameters = {
                "page": current_page_number,
                "category": "Software Engineering",
            }
            try:
                api_response = self.session.get(
                    base_endpoint_url,
                    params=query_parameters,
                    timeout=request_timeout_seconds,
                )
                if api_response.status_code != 200:
                    break
                response_json_payload = api_response.json()
            except Exception:
                break

            page_job_results = response_json_payload.get("results", [])
            if not page_job_results:
                break

            for job_record in page_job_results:
                job_title = job_record.get("name", "")
                company_name = job_record.get("company", {}).get("name", "")
                description_html = job_record.get("contents", "")
                parsed_description = markdown_converter(description_html) if description_html else ""

                location_entries = job_record.get("locations", [])
                location_name = location_entries[0].get("name", "USA") if location_entries else "USA"
                location_object = Location(country=location_name)

                job_landing_url = job_record.get("refs", {}).get("landing_page", "")
                extracted_emails = extract_emails_from_text(parsed_description) if parsed_description else []

                collected_job_posts.append(
                    JobPost(
                        id=str(job_record.get("id")),
                        title=job_title,
                        company_name=company_name,
                        job_url=job_landing_url,
                        location=location_object,
                        description=parsed_description,
                        emails=extracted_emails,
                        is_remote="remote" in location_name.lower(),
                    )
                )

                if len(collected_job_posts) >= maximum_results_wanted:
                    break

            total_pages_available = response_json_payload.get("page_count", 1)
            if current_page_number >= total_pages_available:
                break
            current_page_number += 1

        return JobResponse(jobs=collected_job_posts)
