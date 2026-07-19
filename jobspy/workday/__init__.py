"""
Workday ATS job board scraper.
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

class Workday(Scraper):
    """
    Scraper for Workday careers site JSON API.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize Workday scraper.
        """
        super().__init__(Site.WORKDAY, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        Scrape jobs for the company slug provided in search_term.
        """
        company = scraper_input.search_term
        if not company:
            return JobResponse(jobs=[])

        url = f"https://{company}.wd5.myworkdaysite.com/wday/cxs/{company}/External/jobs"
        payload = {"limit": 100, "offset": 0, "searchText": ""}
        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=getattr(scraper_input, "request_timeout", 60)
            )
            if response.status_code != 200:
                return JobResponse(jobs=[])
            data = response.json()
        except Exception:
            return JobResponse(jobs=[])

        jobs = []
        for posting in data.get("jobPostings", []):
            path = posting.get("externalPath")
            if not path:
                continue

            job_id = ""
            description_text = ""
            detail_url = f"https://{company}.wd5.myworkdaysite.com/wday/cxs/{company}/External{path}"
            try:
                detail_resp = self.session.get(detail_url, timeout=20)
                if detail_resp.status_code == 200:
                    detail_data = detail_resp.json()
                    info = detail_data.get("jobPostingInfo", {})
                    job_id = info.get("id", "")
                    desc_html = info.get("jobDescription", "")
                    if desc_html:
                        soup = BeautifulSoup(desc_html, "html.parser")
                        description_text = soup.get_text(separator=" ", strip=True)
            except Exception:
                pass

            if not job_id:
                job_id = path.split("_")[-1] if "_" in path else path.split("/")[-1]

            location_name = posting.get("locationsText", "Remote")

            jobs.append(
                JobPost(
                    id=str(job_id),
                    title=posting.get("title", ""),
                    company_name=company.capitalize(),
                    job_url=f"https://{company}.wd5.myworkdaysite.com/en-US/{company}/details/{job_id}" if job_id else f"https://{company}.wd5.myworkdaysite.com/en-US/{company}/details{path}",
                    location=Location(country=location_name),
                    description=description_text,
                    is_remote="remote" in location_name.lower()
                )
            )

        return JobResponse(jobs=jobs)
