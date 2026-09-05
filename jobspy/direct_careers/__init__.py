"""
Direct Company Career HTML pages scraper for JobSpy.

Loads 997 curated company career portals from career_pages.csv and scrapes
each page for job postings using JSON-LD structured data, embedded ATS iframes,
and direct anchor-tag link pattern matching.
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Optional

from bs4 import BeautifulSoup

from jobspy.model import (
    DescriptionFormat,
    JobPost,
    JobResponse,
    Location,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy.util import create_logger, create_session, markdown_converter, plain_converter

_CORRECTED_CSV_PATH = pathlib.Path(__file__).parent.parent / "career_pages_corrected.csv"
_ORIGINAL_CSV_PATH = pathlib.Path(__file__).parent.parent / "career_pages.csv"
_CAREER_PAGES_CSV_PATH = _CORRECTED_CSV_PATH if _CORRECTED_CSV_PATH.exists() else _ORIGINAL_CSV_PATH

_ATS_EMBED_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "smartrecruiters.com",
    "myworkdaysite.com",
]

_JOB_LINK_URL_PATTERN = re.compile(
    r"/(jobs?|careers?|postings?|position|role|openings?)/",
    re.IGNORECASE,
)

_IGNORED_LINK_TEXTS = frozenset(["careers", "jobs", "apply", "view all", "learn more"])

_LOGGER = create_logger("DirectCareers")


def load_career_pages() -> list[tuple[str, str, str]]:
    """
    Load the curated company career portal list from career_pages.csv.

    Returns a list of (company_name, career_url, headquarters_footprint) tuples
    for all companies in the CSV.
    """
    entries: list[tuple[str, str, str]] = []
    with open(_CAREER_PAGES_CSV_PATH, newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            company_name = row.get("Company Name", "").strip()
            career_url = row.get("Direct Career Portal", "").strip()
            headquarters = row.get("Global Headquarters & Regional Footprint", "").strip()
            if company_name and career_url:
                entries.append((company_name, career_url, headquarters))
    return entries


_CACHED_CAREER_PAGES: Optional[list[tuple[str, str, str]]] = None


def _get_career_pages() -> list[tuple[str, str, str]]:
    """
    Return the cached career pages list, loading from CSV on first call.
    """
    global _CACHED_CAREER_PAGES
    if _CACHED_CAREER_PAGES is None:
        _CACHED_CAREER_PAGES = load_career_pages()
    return _CACHED_CAREER_PAGES


def resolve_company_career_urls(company_name: str) -> list[str]:
    """
    Generate candidate direct career page URLs for any company name or slug.

    Strips non-alphanumeric characters from the company name and produces
    a ranked list of common career URL patterns across .com, .io, .ai, and
    other top-level domains used by tech companies.
    """
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", company_name.lower())
    if not clean_name:
        return []
    return [
        f"https://www.{clean_name}.com/careers",
        f"https://www.{clean_name}.com/jobs",
        f"https://{clean_name}.com/careers",
        f"https://{clean_name}.com/jobs",
        f"https://careers.{clean_name}.com",
        f"https://jobs.{clean_name}.com",
        f"https://{clean_name}.io/careers",
        f"https://{clean_name}.io/jobs",
        f"https://{clean_name}.ai/careers",
        f"https://{clean_name}.ai/jobs",
        f"https://{clean_name}.sh/careers",
        f"https://{clean_name}.dev/jobs",
        f"https://{clean_name}.app/careers",
    ]


def _parse_date_posted(raw_date: Optional[str]) -> Optional[date]:
    """
    Parse an ISO 8601 date string from JSON-LD into a Python date object.

    Returns None if the string is absent or unparseable.
    """
    if not raw_date:
        return None
    for date_format in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_date[:19], date_format[:len(date_format)])
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw_date).date()
    except (ValueError, TypeError):
        return None


def _convert_description(raw_description: str, description_format: Optional[DescriptionFormat]) -> str:
    """
    Convert a raw HTML or plain description string to the requested output format.

    Applies markdown conversion for MARKDOWN format, plain-text stripping for
    PLAIN format, and returns the original string for all other formats.
    """
    if not raw_description:
        return raw_description
    if description_format == DescriptionFormat.MARKDOWN:
        converted = markdown_converter(raw_description)
        return converted if converted else raw_description
    if description_format == DescriptionFormat.PLAIN:
        converted = plain_converter(raw_description)
        return converted if converted else raw_description
    return raw_description


def _extract_location_from_ld_json(job_location_data: dict | list) -> tuple[str, bool]:
    """
    Extract a human-readable location string and is_remote flag from JSON-LD jobLocation data.

    Returns (location_string, is_remote) where is_remote is True when the
    location data indicates a remote or worldwide position.
    """
    location_string = "Remote"
    is_remote = True

    if isinstance(job_location_data, list):
        job_location_data = job_location_data[0] if job_location_data else {}

    if isinstance(job_location_data, dict):
        address = job_location_data.get("address", {})
        if isinstance(address, dict):
            locality = address.get("addressLocality")
            country = address.get("addressCountry")
            location_string = locality or country or "Remote"
            is_remote = "remote" in location_string.lower()

    return location_string, is_remote


class DirectCareers(Scraper):
    """
    Scraper for direct company career HTML pages.

    Reads the full curated list of 997 companies from career_pages.csv and
    concurrently fetches each company's career page. Job postings are extracted
    via three fallback strategies in order of reliability:
      1. JSON-LD structured data (schema.org/JobPosting)
      2. Embedded ATS iframes/scripts (Greenhouse, Lever, Ashby, etc.)
      3. Anchor tag URL pattern matching against common job URL path segments
    """

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        """
        Initialize the DirectCareers scraper with HTTP session and optional proxy/TLS settings.
        """
        super().__init__(Site.DIRECT_CAREERS, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.session = create_session(
            proxies=self.proxies,
            ca_cert=ca_cert,
            is_tls=False,
            has_retry=True,
            delay=5,
            clear_cookies=True,
        )
        resolved_user_agent = user_agent or "JobCruiser/1.0"
        self.session.headers.update({
            "User-Agent": resolved_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def _build_job_post_from_ld_json(
        self,
        ld_item: dict,
        company_name: str,
        career_url: str,
        description_format: Optional[DescriptionFormat],
    ) -> Optional[JobPost]:
        """
        Construct a JobPost from a single JSON-LD JobPosting dict.

        Returns None if the item lacks a title or is not a valid JobPosting.
        """
        if not isinstance(ld_item, dict) or ld_item.get("@type") != "JobPosting":
            return None

        title = ld_item.get("title", "").strip()
        if not title:
            return None

        job_url = ld_item.get("url") or career_url
        raw_description = ld_item.get("description", "")
        description = _convert_description(raw_description, description_format) or f"Direct posting from {company_name}"
        date_posted = _parse_date_posted(ld_item.get("datePosted"))
        location_string, is_remote = _extract_location_from_ld_json(ld_item.get("jobLocation", {}))

        if ld_item.get("applicantLocationRequirements") is not None:
            is_remote = True

        return JobPost(
            id=job_url,
            title=title,
            company_name=company_name,
            job_url=job_url,
            company_url=career_url,
            company_url_direct=career_url,
            location=Location(country=location_string),
            description=description,
            is_remote=is_remote,
            date_posted=date_posted,
        )

    def _scrape_json_ld_postings(
        self,
        soup: BeautifulSoup,
        company_name: str,
        career_url: str,
        seen_urls: set,
        description_format: Optional[DescriptionFormat],
    ) -> list[JobPost]:
        """
        Extract JobPost objects from JSON-LD script tags on a career page.

        Handles both single-object and array-of-objects JSON-LD payloads.
        """
        extracted_jobs: list[JobPost] = []

        for script_tag in soup.find_all("script", type="application/ld+json"):
            script_text = script_tag.string or script_tag.get_text()
            if not script_text:
                continue
            try:
                ld_data = json.loads(script_text)
            except (json.JSONDecodeError, ValueError):
                continue

            ld_items = ld_data if isinstance(ld_data, list) else [ld_data]

            for ld_item in ld_items:
                job_post = self._build_job_post_from_ld_json(
                    ld_item, company_name, career_url, description_format
                )
                if job_post and job_post.job_url not in seen_urls:
                    seen_urls.add(job_post.job_url)
                    extracted_jobs.append(job_post)

        return extracted_jobs

    def _scrape_embedded_ats_postings(
        self,
        soup: BeautifulSoup,
        company_name: str,
        career_url: str,
        seen_urls: set,
    ) -> list[JobPost]:
        """
        Extract job links from embedded ATS iframes or scripts on a career page.

        Fetches the embedded ATS page and collects anchor tag links from it.
        Supports Greenhouse, Lever, Ashby, SmartRecruiters, and Workday embeds.
        """
        extracted_jobs: list[JobPost] = []

        for embed_tag in soup.find_all(["iframe", "script"], src=True):
            embed_src = embed_tag.get("src", "")
            if not any(ats_domain in embed_src for ats_domain in _ATS_EMBED_DOMAINS):
                continue
            try:
                embed_response = self.session.get(embed_src, timeout=15)
                if embed_response.status_code != 200:
                    continue
                embed_soup = BeautifulSoup(embed_response.content, "html.parser")
                for anchor_tag in embed_soup.find_all("a", href=True):
                    href = anchor_tag.get("href", "").strip()
                    full_url = urllib.parse.urljoin(embed_src, href)
                    title = anchor_tag.get_text(strip=True)
                    if title and len(title) >= 4 and full_url not in seen_urls:
                        seen_urls.add(full_url)
                        extracted_jobs.append(
                            JobPost(
                                id=full_url,
                                title=title,
                                company_name=company_name,
                                job_url=full_url,
                                company_url=career_url,
                                company_url_direct=career_url,
                                location=Location(country="Remote"),
                                description=f"Embedded ATS posting from {company_name}",
                                is_remote=True,
                            )
                        )
            except Exception:
                pass

        return extracted_jobs

    def _scrape_anchor_tag_postings(
        self,
        soup: BeautifulSoup,
        company_name: str,
        career_url: str,
        seen_urls: set,
    ) -> list[JobPost]:
        """
        Extract job links from anchor tags matching known job URL path patterns.

        Falls back to looking at the parent element for a more descriptive title
        when the anchor text itself is a generic navigation label.
        """
        extracted_jobs: list[JobPost] = []

        for anchor_tag in soup.find_all("a", href=True):
            href = anchor_tag.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            full_url = urllib.parse.urljoin(career_url, href)
            if full_url in seen_urls:
                continue

            url_matches_job_pattern = (
                _JOB_LINK_URL_PATTERN.search(full_url)
                or _JOB_LINK_URL_PATTERN.search(href)
            )
            if not url_matches_job_pattern:
                continue

            title = anchor_tag.get_text(strip=True)
            if not title or len(title) < 4 or title.lower() in _IGNORED_LINK_TEXTS:
                parent_element = anchor_tag.find_parent(["h1", "h2", "h3", "h4", "li", "div", "tr"])
                if parent_element:
                    title = parent_element.get_text(strip=True)

            if title and 4 <= len(title) <= 120:
                seen_urls.add(full_url)
                extracted_jobs.append(
                    JobPost(
                        id=full_url,
                        title=title,
                        company_name=company_name,
                        job_url=full_url,
                        company_url=career_url,
                        company_url_direct=career_url,
                        location=Location(country="Remote"),
                        description=f"Direct career posting from {company_name} at {full_url}",
                        is_remote=True,
                    )
                )

        return extracted_jobs

    def scrape_single_company(
        self,
        company_name: str,
        career_url: str,
        description_format: Optional[DescriptionFormat] = None,
    ) -> list[JobPost]:
        """
        Scrape job postings from a single company's career page.

        Tries the known career_url first, then falls back to heuristically
        generated candidate URLs derived from the company name. Returns the
        first non-empty set of jobs found across all candidate URLs.
        """
        candidate_urls = [career_url] if career_url else []
        candidate_urls.extend(resolve_company_career_urls(company_name))

        for target_url in candidate_urls:
            try:
                response = self.session.get(target_url, timeout=15)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.content, "html.parser")
                seen_urls: set = set()

                json_ld_jobs = self._scrape_json_ld_postings(
                    soup, company_name, target_url, seen_urls, description_format
                )
                embedded_ats_jobs = self._scrape_embedded_ats_postings(
                    soup, company_name, target_url, seen_urls
                )
                anchor_tag_jobs = self._scrape_anchor_tag_postings(
                    soup, company_name, target_url, seen_urls
                )

                company_jobs = json_ld_jobs + embedded_ats_jobs + anchor_tag_jobs
                if company_jobs:
                    _LOGGER.info(f"Found {len(company_jobs)} jobs at {company_name} ({target_url})")
                    return company_jobs

            except Exception as fetch_error:
                _LOGGER.debug(f"Failed to fetch {target_url} for {company_name}: {fetch_error}")
                continue

        return []

    def _filter_companies_by_search_term(
        self,
        career_pages: list[tuple[str, str, str]],
        search_term: str,
    ) -> list[tuple[str, str, str]]:
        """
        Narrow the company list to those whose name contains the search term.

        Used when the search term looks like a company name rather than a job title.
        Falls back to the full list if no company name matches are found, so
        that search_term continues to apply as a job-title filter downstream.
        """
        lowered_term = search_term.lower()
        matched_companies = [
            entry for entry in career_pages
            if lowered_term in entry[0].lower()
        ]
        return matched_companies if matched_companies else career_pages

    def _filter_companies_by_location(
        self,
        career_pages: list[tuple[str, str, str]],
        location: str,
    ) -> list[tuple[str, str, str]]:
        """
        Filter the company list to those headquartered in or near the given location.

        Performs a case-insensitive substring match against each company's
        headquarters footprint field from the CSV. Returns the full list if
        no headquarters match found, since many remote-friendly companies may
        still be relevant.
        """
        lowered_location = location.lower()
        matched_companies = [
            entry for entry in career_pages
            if lowered_location in entry[2].lower()
        ]
        return matched_companies if matched_companies else career_pages

    def _filter_jobs_by_search_term(
        self, jobs: list[JobPost], search_term: str
    ) -> list[JobPost]:
        """
        Filter a list of JobPost objects by whether their title contains the search term.
        """
        lowered_term = search_term.lower()
        return [job for job in jobs if lowered_term in job.title.lower()]

    def _filter_jobs_by_remote(self, jobs: list[JobPost]) -> list[JobPost]:
        """
        Filter a list of JobPost objects to only include remote positions.
        """
        return [job for job in jobs if job.is_remote is True]

    def _filter_jobs_by_hours_old(
        self, jobs: list[JobPost], hours_old: int
    ) -> list[JobPost]:
        """
        Filter a list of JobPost objects to those posted within the given number of hours.

        Jobs without a date_posted field are retained because we cannot determine
        their recency from the page content alone.
        """
        cutoff_date = datetime.utcnow().replace(tzinfo=None)
        from datetime import timedelta
        cutoff_threshold = cutoff_date - timedelta(hours=hours_old)

        def is_within_threshold(job: JobPost) -> bool:
            if job.date_posted is None:
                return True
            job_datetime = datetime.combine(job.date_posted, datetime.min.time())
            return job_datetime >= cutoff_threshold

        return [job for job in jobs if is_within_threshold(job)]

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrape jobs from official company career HTML pages concurrently.

        Loads all companies from career_pages.csv, optionally narrows the
        company list by search_term and location, then fans out across
        ThreadPoolExecutor workers. Applies post-collection filters for
        is_remote, search_term title matching, and hours_old recency before
        truncating to results_wanted.
        """
        career_pages = _get_career_pages()

        if scraper_input.search_term:
            career_pages = self._filter_companies_by_search_term(
                career_pages, scraper_input.search_term
            )

        if scraper_input.location:
            career_pages = self._filter_companies_by_location(
                career_pages, scraper_input.location
            )

        _LOGGER.info(f"Scraping {len(career_pages)} company career pages")

        all_jobs: list[JobPost] = []

        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_company = {
                executor.submit(
                    self.scrape_single_company,
                    company_name,
                    career_url,
                    scraper_input.description_format,
                ): company_name
                for company_name, career_url, _ in career_pages
            }

            for future in as_completed(future_to_company):
                try:
                    company_jobs = future.result()
                    all_jobs.extend(company_jobs)
                except Exception as future_error:
                    company_name = future_to_company[future]
                    _LOGGER.warning(f"Worker failed for {company_name}: {future_error}")

        if scraper_input.search_term:
            all_jobs = self._filter_jobs_by_search_term(all_jobs, scraper_input.search_term)

        if scraper_input.is_remote:
            all_jobs = self._filter_jobs_by_remote(all_jobs)

        if scraper_input.hours_old:
            all_jobs = self._filter_jobs_by_hours_old(all_jobs, scraper_input.hours_old)

        results_cap = scraper_input.results_wanted if scraper_input.results_wanted else None
        return JobResponse(jobs=all_jobs[:results_cap])
