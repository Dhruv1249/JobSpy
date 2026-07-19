"""
Hacker News Who's Hiring thread scraper.
"""

from datetime import datetime
from bs4 import BeautifulSoup
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

class HNHiring(Scraper):
    """
    Scraper for the monthly Hacker News "Who is hiring?" comments.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize HNHiring scraper.
        """
        super().__init__(Site.HN_HIRING, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
        Scrape job postings from Hacker News monthly hiring thread comments.
        """
        story_search_url = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query=Ask%20HN:%20Who%20is%20hiring?&hitsPerPage=1"
        try:
            story_resp = self.session.get(
                story_search_url,
                timeout=getattr(scraper_input, "request_timeout", 60)
            )
            if story_resp.status_code != 200:
                return JobResponse(jobs=[])
            story_data = story_resp.json()
            hits = story_data.get("hits", [])
            if not hits:
                return JobResponse(jobs=[])
            story_id = hits[0].get("objectID")
        except Exception:
            return JobResponse(jobs=[])

        comments_url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage=1000"
        try:
            comments_resp = self.session.get(
                comments_url,
                timeout=getattr(scraper_input, "request_timeout", 60)
            )
            if comments_resp.status_code != 200:
                return JobResponse(jobs=[])
            comments_data = comments_resp.json()
        except Exception:
            return JobResponse(jobs=[])

        jobs = []
        search_term_lower = scraper_input.search_term.lower() if scraper_input.search_term else None

        for hit in comments_data.get("hits", []):
            comment_text_html = hit.get("comment_text", "")
            if not comment_text_html:
                continue

            description = markdown_converter(comment_text_html)
            soup = BeautifulSoup(comment_text_html, "html.parser")
            text = soup.get_text()
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if not lines:
                continue

            first_line = lines[0]
            company = "Hacker News Poster"
            position = first_line[:50]
            location_str = "Worldwide"

            if "|" in first_line:
                tokens = [t.strip() for t in first_line.split("|")]
                company = tokens[0]
                if len(tokens) > 1:
                    position = tokens[1]
                if len(tokens) > 2:
                    location_str = tokens[2]

            if search_term_lower:
                title_matches = search_term_lower in position.lower()
                company_matches = search_term_lower in company.lower()
                desc_matches = search_term_lower in description.lower()
                if not (title_matches or company_matches or desc_matches):
                    continue

            created_at_str = hit.get("created_at")
            date_posted = None
            if created_at_str:
                try:
                    date_posted = datetime.strptime(
                        created_at_str[:10],
                        "%Y-%m-%d"
                    ).date()
                except Exception:
                    pass

            comment_id = hit.get("objectID")
            job_url = f"https://news.ycombinator.com/item?id={comment_id}"
            emails = extract_emails_from_text(description)

            jobs.append(
                JobPost(
                    id=comment_id,
                    title=position,
                    company_name=company,
                    job_url=job_url,
                    location=Location(country=location_str),
                    description=description,
                    date_posted=date_posted,
                    emails=emails,
                    is_remote="remote" in location_str.lower()
                )
            )

            if len(jobs) >= scraper_input.results_wanted:
                break

        return JobResponse(jobs=jobs)
