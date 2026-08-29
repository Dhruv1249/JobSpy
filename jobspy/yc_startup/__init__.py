"""
Y Combinator startup job board scraper for YC portfolio positions.
"""

from __future__ import annotations

import json
from datetime import datetime
from bs4 import BeautifulSoup

from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy.util import (
    create_session,
    markdown_converter,
)


class YCStartup(Scraper):
    """
    Scraper for Y Combinator startup job listings across role and location feeds.
    """

    TARGET_ENDPOINTS = [
        "https://www.ycombinator.com/jobs/role/software-engineer",
        "https://www.ycombinator.com/jobs/role/engineering",
        "https://www.ycombinator.com/jobs/location/remote",
        "https://www.ycombinator.com/jobs/location/india",
        "https://www.ycombinator.com/jobs/location/bengaluru",
    ]

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        """
        Initializes the YCStartup scraper with session headers and proxy support.
        """
        super().__init__(Site.YC_STARTUP, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.session = create_session(
            proxies=self.proxies,
            ca_cert=ca_cert,
            is_tls=False,
            has_retry=True,
            delay=2,
            clear_cookies=True,
        )
        if user_agent:
            self.session.headers.update({"User-Agent": user_agent})
        else:
            self.session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
            )

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrapes job postings from Y Combinator's Inertia.js job feeds.
        """
        collected_jobs: list[JobPost] = []
        seen_job_identifiers: set[str] = set()
        request_timeout = getattr(scraper_input, "request_timeout", 60)

        for target_url in self.TARGET_ENDPOINTS:
            try:
                response = self.session.get(target_url, timeout=request_timeout)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                data_page_element = soup.find(attrs={"data-page": True})
                if not data_page_element:
                    continue

                page_payload = json.loads(data_page_element["data-page"])
                job_postings = page_payload.get("props", {}).get("jobPostings", [])

                for posting in job_postings:
                    posting_id = str(posting.get("id", ""))
                    if not posting_id or posting_id in seen_job_identifiers:
                        continue

                    job_title = posting.get("title", "").strip()
                    if not job_title:
                        continue

                    company_name = posting.get("companyName") or posting.get("companyOneLiner") or "YC Startup"
                    relative_url = posting.get("url", "")
                    job_url = f"https://www.ycombinator.com{relative_url}" if relative_url.startswith("/") else relative_url
                    if not job_url:
                        job_url = f"https://www.ycombinator.com/jobs/{posting_id}"

                    location_text = str(posting.get("location") or "Worldwide")
                    is_remote_flag = "remote" in location_text.lower() or posting.get("roleSpecificType") == "remote"

                    skills_list = posting.get("skills", [])
                    skills_string = ", ".join(skills_list) if isinstance(skills_list, list) else ""
                    salary_range = posting.get("salaryRange") or ""
                    equity_range = posting.get("equityRange") or ""
                    company_summary = posting.get("companyOneLiner") or ""

                    description_sections = []
                    if company_summary:
                        description_sections.append(f"Company: {company_summary}")
                    if salary_range:
                        description_sections.append(f"Salary: {salary_range}")
                    if equity_range:
                        description_sections.append(f"Equity: {equity_range}")
                    if skills_string:
                        description_sections.append(f"Skills: {skills_string}")

                    raw_description = "\n".join(description_sections)
                    formatted_description = markdown_converter(raw_description) if raw_description else ""

                    date_posted = None
                    created_at_raw = posting.get("createdAt")
                    if created_at_raw:
                        try:
                            date_posted = datetime.strptime(str(created_at_raw)[:10], "%Y-%m-%d").date()
                        except Exception:
                            pass

                    job_post = JobPost(
                        id=posting_id,
                        title=job_title,
                        company_name=company_name,
                        job_url=job_url,
                        job_url_direct=posting.get("applyUrl"),
                        location=Location(country=location_text),
                        description=formatted_description,
                        date_posted=date_posted,
                        is_remote=is_remote_flag,
                    )

                    collected_jobs.append(job_post)
                    seen_job_identifiers.add(posting_id)

                    if len(collected_jobs) >= scraper_input.results_wanted:
                        break

            except Exception:
                continue

            if len(collected_jobs) >= scraper_input.results_wanted:
                break

        return JobResponse(jobs=collected_jobs)
