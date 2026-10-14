"""
Oracle Cloud HCM Candidate Experience portal scraper for JobSpy.
Supports JPMorgan Chase and other enterprise institutions running Oracle Cloud HCM.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime

from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy.util import create_session


class OracleCloud(Scraper):
    """
    Scraper for Oracle Cloud HCM Candidate Experience job requisitions API.
    """

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
        tenant: str = "jpmc",
        site_number: str = "CX_1001",
        company_name: str = "JPMorgan Chase",
    ):
        """
        Initialize Oracle Cloud HCM scraper with tenant configuration and HTTP session.
        """
        super().__init__(Site.ORACLE_CLOUD, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.tenant = tenant
        self.site_number = site_number
        self.company_name = company_name
        self.session = create_session(
            proxies=self.proxies,
            ca_cert=ca_cert,
            is_tls=False,
            has_retry=True,
            delay=5,
            clear_cookies=True,
        )
        resolved_user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        self.session.headers.update({
            "User-Agent": resolved_user_agent,
            "Accept": "application/json",
        })

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrapes job requisitions from Oracle Cloud HCM Candidate Experience REST endpoint.
        """
        search_term = scraper_input.search_term or "engineer"
        results_limit = min(scraper_input.results_wanted or 50, 100)

        finder_clause = f"findReqs;siteNumber={self.site_number},limit={results_limit},keyword={urllib.parse.quote(search_term)}"
        api_endpoint = (
            f"https://{self.tenant}.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
            f"?onlyData=true&expand=requisitionList&finder={finder_clause}"
        )

        timeout_duration = getattr(scraper_input, "request_timeout", 30)
        try:
            response = self.session.get(api_endpoint, timeout=timeout_duration)
            if response.status_code != 200:
                return JobResponse(jobs=[])
            response_payload = response.json()
        except Exception:
            return JobResponse(jobs=[])

        return self._parse_requisitions(response_payload, scraper_input)

    def _parse_requisitions(self, response_payload: dict, scraper_input: ScraperInput) -> JobResponse:
        """
        Converts Oracle Cloud HCM requisition list items into normalized JobPost objects.
        """
        items_list = response_payload.get("items", [])
        if not items_list:
            return JobResponse(jobs=[])

        first_container = items_list[0]
        raw_requisitions = first_container.get("requisitionList", [])
        collected_jobs: list[JobPost] = []

        for requisition in raw_requisitions:
            requisition_id = str(requisition.get("Id") or "")
            job_title = (requisition.get("Title") or "").strip()
            if not job_title or not requisition_id:
                continue

            primary_location = requisition.get("PrimaryLocation") or "United States"
            if scraper_input.location and scraper_input.location.lower() not in primary_location.lower():
                country_code = requisition.get("PrimaryLocationCountry") or ""
                if scraper_input.location.lower() not in country_code.lower():
                    continue

            job_url = f"https://{self.tenant}.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/{self.site_number}/job/{requisition_id}"
            
            short_description = requisition.get("ShortDescriptionStr") or ""
            job_family = requisition.get("JobFamily") or ""
            organization_name = requisition.get("Organization") or ""
            department_name = requisition.get("Department") or ""

            description_segments = [job_title]
            if organization_name or department_name:
                description_segments.append(f"Organization: {organization_name} - {department_name}")
            if job_family:
                description_segments.append(f"Job Family: {job_family}")
            description_segments.append(f"Location: {primary_location}")
            if short_description:
                description_segments.append(short_description)

            compiled_description = "\n\n".join(description_segments)
            workplace_type = str(requisition.get("WorkplaceType") or "")
            is_remote_position = (
                scraper_input.is_remote
                or "remote" in primary_location.lower()
                or "remote" in workplace_type.lower()
            )

            posted_date_raw = requisition.get("PostedDate")
            parsed_posted_date = None
            if posted_date_raw:
                try:
                    parsed_posted_date = datetime.fromisoformat(posted_date_raw.replace("Z", "+00:00")).date()
                except Exception:
                    parsed_posted_date = None

            collected_jobs.append(
                JobPost(
                    id=requisition_id,
                    title=job_title,
                    company_name=self.company_name,
                    job_url=job_url,
                    location=Location(country=primary_location),
                    description=compiled_description,
                    is_remote=is_remote_position,
                    date_posted=parsed_posted_date,
                )
            )

            if scraper_input.results_wanted and len(collected_jobs) >= scraper_input.results_wanted:
                break

        return JobResponse(jobs=collected_jobs)
