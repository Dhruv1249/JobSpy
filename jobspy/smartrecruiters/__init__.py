"""
SmartRecruiters ATS job board scraper.
"""

from bs4 import BeautifulSoup
from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Scraper,
    ScraperInput,
    Site
)
from jobspy.util import create_session

class SmartRecruiters(Scraper):
    """
    Scraper for SmartRecruiters API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize SmartRecruiters scraper.
        """
        super().__init__(Site.SMARTRECRUITERS, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        self.base_url = "https://api.smartrecruiters.com/v1/companies"

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrape jobs for the company slug provided in search_term.
        """
        company = scraper_input.search_term
        if not company:
            return JobResponse(jobs=[])

        url = f"{self.base_url}/{company}/postings"
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
        for posting in data.get("content", []):
            posting_id = posting.get("id")
            if not posting_id:
                continue

            description_text = ""
            detail_url = f"{self.base_url}/{company}/postings/{posting_id}"
            try:
                detail_resp = self.session.get(detail_url, timeout=20)
                if detail_resp.status_code == 200:
                    detail_data = detail_resp.json()
                    desc_html = detail_data.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "")
                    if desc_html:
                        soup = BeautifulSoup(desc_html, "html.parser")
                        description_text = soup.get_text(separator=" ", strip=True)
            except Exception:
                pass

            loc = posting.get("location", {})
            loc_parts = []
            for k in ["city", "region", "country"]:
                val = loc.get(k)
                if val:
                    loc_parts.append(val)
            location_name = ", ".join(loc_parts) if loc_parts else "Remote"

            jobs.append(
                JobPost(
                    id=str(posting_id),
                    title=posting.get("name", ""),
                    company_name=company.capitalize(),
                    job_url=f"https://jobs.smartrecruiters.com/{company}/{posting_id}",
                    location=Location(country=location_name),
                    description=description_text,
                    is_remote="remote" in location_name.lower()
                )
            )

        return JobResponse(jobs=jobs)
