"""
We Work Remotely job board scraper.
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

class WeWorkRemotely(Scraper):
    """
    Scraper for We Work Remotely.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize WeWorkRemotely scraper.
        """
        super().__init__(Site.WEWORKREMOTELY, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        Scrape job postings from We Work Remotely.
        """
        url = "https://weworkremotely.com/remote-jobs.rss"
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

        channel = root.find("channel")
        if channel is None:
            return JobResponse(jobs=[])

        for item in channel.findall("item"):
            title_raw = item.find("title")
            title_text = title_raw.text if title_raw is not None else ""

            if ":" in title_text:
                company, _, position = title_text.partition(":")
                company = company.strip()
                position = position.strip()
            else:
                company = ""
                position = title_text.strip()

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
