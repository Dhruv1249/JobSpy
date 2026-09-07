"""
Dice tech job board scraper module for JobSpy.
"""

from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy.util import create_session, create_logger

log = create_logger("dice")

class Dice(Scraper):
    """
    Scraper for Dice technology job listings.
    """

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        """
        Initialize Dice scraper with browser session headers.
        """
        super().__init__(Site.DICE, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.session = create_session(
            proxies=self.proxies,
            ca_cert=ca_cert,
            is_tls=False,
            has_retry=True,
            delay=5,
            clear_cookies=True,
        )
        browser_user_agent = (
            user_agent
            or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        self.session.headers.update(
            {
                "User-Agent": browser_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrapes job search results from Dice HTML pages.
        """
        search_query = scraper_input.search_term or "developer"
        log.info(f"[dice] Starting scrape for {search_query}")
        encoded_query = quote_plus(search_query)
        target_url = f"https://www.dice.com/jobs?q={encoded_query}"
        request_timeout_seconds = getattr(scraper_input, "request_timeout", 60)

        try:
            http_response = self.session.get(target_url, timeout=request_timeout_seconds)
            if http_response.status_code != 200:
                log.error(f"[dice] HTTP {http_response.status_code}: {target_url}")
                return JobResponse(jobs=[])
            html_content = http_response.text
        except Exception as e:
            log.error(f"[dice] Error: {type(e).__name__}: {e}")
            return JobResponse(jobs=[])

        html_parser = BeautifulSoup(html_content, "html.parser")
        job_link_elements = [
            anchor
            for anchor in html_parser.find_all("a")
            if anchor.get("href") and "/job-detail/" in anchor.get("href") and anchor.get_text(strip=True)
        ]
        log.info(f"[dice] Page 1: fetched {len(job_link_elements)} listings")

        collected_jobs = []
        seen_job_identifiers = set()

        for anchor_element in job_link_elements:
            relative_job_url = anchor_element.get("href", "")
            absolute_job_url = (
                f"https://www.dice.com{relative_job_url}"
                if relative_job_url.startswith("/")
                else relative_job_url
            )
            job_identifier = absolute_job_url.rstrip("/").split("/")[-1]

            if job_identifier in seen_job_identifiers:
                continue
            seen_job_identifiers.add(job_identifier)

            card_container = (
                anchor_element.parent.parent.parent.parent
                if anchor_element.parent
                and anchor_element.parent.parent
                and anchor_element.parent.parent.parent
                else anchor_element
            )
            extracted_strings = [
                text_item.strip() for text_item in card_container.stripped_strings if text_item.strip()
            ]

            job_title = anchor_element.get_text(strip=True)
            company_name = extracted_strings[1] if len(extracted_strings) > 1 else ""
            location_string = extracted_strings[2] if len(extracted_strings) > 2 else "Remote"
            is_remote_position = "remote" in location_string.lower() or "remote" in job_title.lower()

            collected_jobs.append(
                JobPost(
                    id=job_identifier,
                    title=job_title,
                    company_name=company_name,
                    job_url=absolute_job_url,
                    location=Location(country=location_string),
                    description=" ".join(extracted_strings),
                    is_remote=is_remote_position,
                )
            )

            if len(collected_jobs) >= scraper_input.results_wanted:
                break

        log.info(f"[dice] Complete: {len(collected_jobs)} jobs found")
        return JobResponse(jobs=collected_jobs)
