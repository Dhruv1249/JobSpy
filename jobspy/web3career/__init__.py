"""
Web3 Career job board scraper.
"""

from datetime import datetime
import xml.etree.ElementTree as ET
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

class Web3Career(Scraper):
    """
    Scraper for Web3 Career.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Web3 Career scraper.
        """
        super().__init__(Site.WEB3_CAREER, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        Scrape job postings from Web3 Career.
        """
        url = "https://web3.career/rss"
        try:
            response = self.session.get(
                url,
                timeout=getattr(scraper_input, "request_timeout", 60)
            )
            if response.status_code != 200:
                return JobResponse(jobs=[])
            root = ET.fromstring(response.content)
        except Exception:
            return JobResponse(jobs=[])

        jobs = []
        search_term_lower = scraper_input.search_term.lower() if scraper_input.search_term else None

        channel = root.find("channel")
        if channel is None:
            return JobResponse(jobs=[])

        for item in channel.findall("item"):
            title_raw = item.find("title")
            title_text = title_raw.text if title_raw is not None else ""

            if " at " in title_text:
                position, _, company = title_text.partition(" at ")
                position = position.strip()
                company = company.strip()
            else:
                position = title_text.strip()
                company = "Unknown"

            link_raw = item.find("link")
            job_url = link_raw.text if link_raw is not None else ""

            description_raw = item.find("description")
            description_html = description_raw.text if description_raw is not None else ""
            description = markdown_converter(description_html) if description_html else ""

            pub_date_raw = item.find("pubDate")
            date_posted = None
            if pub_date_raw is not None and pub_date_raw.text:
                try:
                    pub_date_parsed = datetime.strptime(
                        pub_date_raw.text.strip()[:25].strip(),
                        "%a, %d %b %Y %H:%M:%S"
                    )
                    date_posted = pub_date_parsed.date()
                except Exception:
                    pass

            emails = extract_emails_from_text(description) if description else []

            jobs.append(
                JobPost(
                    title=position,
                    company_name=company,
                    job_url=job_url,
                    location=Location(country="Worldwide"),
                    description=description,
                    date_posted=date_posted,
                    emails=emails,
                    is_remote=True
                )
            )

            if len(jobs) >= scraper_input.results_wanted:
                break

        return JobResponse(jobs=jobs)
