"""
Google Careers direct portal scraper for JobSpy.
"""

from __future__ import annotations

import re
import urllib.parse
from bs4 import BeautifulSoup

from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy.util import create_session


class GoogleCareers(Scraper):
    """
    Scraper for Google Careers search portal.
    """

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        """
        Initialize Google Careers scraper with configured HTTP session.
        """
        super().__init__(Site.GOOGLE_CAREERS, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrapes jobs from Google Careers search results page.
        """
        search_term = scraper_input.search_term or "software engineer"
        query_parameters = {"q": search_term}
        if scraper_input.location:
            query_parameters["location"] = scraper_input.location

        encoded_query_string = urllib.parse.urlencode(query_parameters)
        target_url = f"https://www.google.com/about/careers/applications/jobs/results/?{encoded_query_string}"

        timeout_duration = getattr(scraper_input, "request_timeout", 30)
        try:
            response = self.session.get(target_url, timeout=timeout_duration)
            if response.status_code != 200:
                return JobResponse(jobs=[])
            html_content = response.text
        except Exception:
            return JobResponse(jobs=[])

        return self._parse_html(html_content, scraper_input)

    def _parse_html(self, html_content: str, scraper_input: ScraperInput) -> JobResponse:
        """
        Parses Google Careers search results HTML into structured JobPost objects.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        collected_jobs: list[JobPost] = []
        seen_job_ids: set[str] = set()

        for list_item in soup.find_all("li"):
            anchor_tag = list_item.find("a", href=lambda destination: destination and "jobs/results/" in destination)
            if not anchor_tag:
                continue

            relative_job_path = anchor_tag.get("href", "")
            full_job_url = urllib.parse.urljoin("https://www.google.com/about/careers/applications/", relative_job_path)

            job_id_match = re.search(r"jobs/results/(\d+)", relative_job_path)
            job_identifier = job_id_match.group(1) if job_id_match else relative_job_path
            if job_identifier in seen_job_ids:
                continue
            seen_job_ids.add(job_identifier)

            title_element = list_item.find("h3", class_="QJPWVe") or list_item.find("h3") or anchor_tag.find("h3")
            job_title = title_element.get_text(strip=True) if title_element else anchor_tag.get_text(strip=True)
            if not job_title or job_title.lower() in ("sign in", "learn more"):
                continue

            location_element = list_item.find("span", class_="r0wTof")
            location_text = location_element.get_text(strip=True) if location_element else (scraper_input.location or "United States")

            job_description = list_item.get_text(separator="\n", strip=True)
            is_remote_position = (
                scraper_input.is_remote
                or "remote" in location_text.lower()
                or "remote" in job_description.lower()
            )

            collected_jobs.append(
                JobPost(
                    id=job_identifier,
                    title=job_title,
                    company_name="Google",
                    job_url=full_job_url,
                    location=Location(country=location_text),
                    description=job_description,
                    is_remote=is_remote_position,
                )
            )

            if scraper_input.results_wanted and len(collected_jobs) >= scraper_input.results_wanted:
                break

        return JobResponse(jobs=collected_jobs)
