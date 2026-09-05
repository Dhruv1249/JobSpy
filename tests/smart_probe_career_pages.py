"""
Smart career page validation probe for all entries in career_pages.csv.

For each company, validates that the URL:
  1. Returns HTTP 200 (or a redirect chain ending in 200)
  2. Did NOT redirect to the company homepage (final URL check)
  3. Contains career-related keywords in the page body
  4. Contains at least one of: job listing links, JSON-LD JobPosting, or
     a recognisable ATS embed (Greenhouse, Lever, Ashby, Workday, etc.)

Outcomes:
  - has_jobs          : page has parseable job listings right on the page
  - careers_page_ok   : confirmed careers page but no individual jobs scraped yet
                        (e.g. JS-rendered, needs pagination, or currently 0 openings)
  - homepage_redirect : URL redirected to root / homepage — wrong URL in CSV
  - no_career_signals : server returned 200 but page has no career-related content
  - blocked_403       : bot protection (page likely works in browser)
  - not_found_404     : URL path does not exist on the server
  - connection_error  : domain unreachable
  - ssl_error         : TLS handshake failure
  - timeout           : server did not respond within timeout
  - server_error_5xx  : server-side error
  - other_NNN         : any other HTTP status
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

CAREER_PAGES_CSV_PATH = pathlib.Path(__file__).parent.parent / "jobspy" / "career_pages.csv"
OUTPUT_CSV_PATH = pathlib.Path(__file__).parent.parent / "career_pages_smart_probe_results.csv"

REQUEST_TIMEOUT_SECONDS = 15
MAX_WORKERS = 25

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CAREER_BODY_KEYWORDS = re.compile(
    r"\b(job|jobs|career|careers|open.?position|opening|vacancy|vacancies|"
    r"join.?us|join.?our.?team|we.?re.?hiring|apply.?now|work.?with.?us|"
    r"employment|opportunities|engineer|developer|analyst|internship|recruiter)\b",
    re.IGNORECASE,
)

JOB_LINK_PATTERN = re.compile(
    r"/(jobs?|careers?|postings?|positions?|roles?|openings?|vacancies?|"
    r"apply|join|opportunities?)/",
    re.IGNORECASE,
)

ATS_EMBED_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "smartrecruiters.com",
    "myworkdaysite.com",
    "myworkday.com",
    "icims.com",
    "taleo.net",
    "successfactors.com",
    "jobvite.com",
    "breezy.hr",
    "recruitee.com",
    "teamtailor.com",
    "pinpoint.com",
]

HOMEPAGE_PATH_PATTERNS = re.compile(r"^/?(\?.*)?$")


@dataclass
class SmartProbeResult:
    company_name: str
    sector: str
    original_url: str
    headquarters: str
    outcome: str = "unknown"
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    response_time_ms: Optional[float] = None
    content_length_bytes: Optional[int] = None
    job_count_on_page: int = 0
    has_json_ld_jobs: bool = False
    has_ats_embed: bool = False
    career_keyword_count: int = 0
    redirected_to_homepage: bool = False
    error_message: Optional[str] = None
    validation_notes: str = ""


def create_probe_session() -> requests.Session:
    """
    Create a requests session with browser-like headers, retry logic, and redirect following.
    """
    session = requests.Session()
    retry_strategy = Retry(total=1, connect=1, status_forcelist=[429, 503], backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(BROWSER_HEADERS)
    return session


def detect_homepage_redirect(requested_url: str, final_url: str) -> bool:
    """
    Determine whether the server redirected us away from the careers path to a homepage.

    Compares the path of the originally requested URL with the final resolved URL.
    If the final URL has a root-level path (/, /en/, /us/, etc.) and the original
    had a meaningful path (/careers, /jobs, etc.), we classify it as a homepage redirect.
    """
    try:
        original_parsed = urllib.parse.urlparse(requested_url)
        final_parsed = urllib.parse.urlparse(final_url)

        original_path = original_parsed.path.rstrip("/")
        final_path = final_parsed.path.rstrip("/")

        if not original_path or original_path in ("/", ""):
            return False

        final_path_is_root = bool(HOMEPAGE_PATH_PATTERNS.fullmatch(final_parsed.path))

        short_locale_path = re.fullmatch(r"/[a-z]{2}(-[a-zA-Z]{2,4})?/?", final_parsed.path)
        final_path_is_locale_root = bool(short_locale_path)

        return final_path_is_root or final_path_is_locale_root

    except Exception:
        return False


def count_career_keywords(text: str) -> int:
    """
    Count the number of career-related keyword matches in page body text.
    """
    return len(CAREER_BODY_KEYWORDS.findall(text))


def extract_job_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """
    Extract anchor tag hrefs that match known job listing URL patterns.
    """
    job_links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full_url = urllib.parse.urljoin(base_url, href)
        if full_url not in seen and (
            JOB_LINK_PATTERN.search(full_url) or JOB_LINK_PATTERN.search(href)
        ):
            seen.add(full_url)
            job_links.append(full_url)

    return job_links


def count_json_ld_job_postings(soup: BeautifulSoup) -> int:
    """
    Count the number of schema.org/JobPosting items in JSON-LD script tags.
    """
    count = 0
    for script_tag in soup.find_all("script", type="application/ld+json"):
        raw = script_tag.string or script_tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
            items = data if isinstance(data, list) else [data]
            count += sum(
                1 for item in items
                if isinstance(item, dict) and item.get("@type") == "JobPosting"
            )
        except (json.JSONDecodeError, ValueError):
            continue
    return count


def detect_ats_embed(soup: BeautifulSoup) -> Optional[str]:
    """
    Detect whether the page embeds a known ATS (Greenhouse, Lever, Workday, etc.)
    via an iframe or script src attribute.

    Returns the matched ATS domain name, or None if no embed found.
    """
    for tag in soup.find_all(["iframe", "script"], src=True):
        src = tag.get("src", "")
        for ats_domain in ATS_EMBED_DOMAINS:
            if ats_domain in src:
                return ats_domain
    return None


def smart_probe(
    company_name: str,
    sector: str,
    career_url: str,
    headquarters: str,
    session: requests.Session,
) -> SmartProbeResult:
    """
    Perform a smart validation probe against a single company career URL.

    Goes beyond a simple HTTP status check by inspecting the page content for
    career-specific signals: keyword density, job listing links, JSON-LD structured
    data, embedded ATS widgets, and redirect destination analysis.
    """
    result = SmartProbeResult(
        company_name=company_name,
        sector=sector,
        original_url=career_url,
        headquarters=headquarters,
    )

    try:
        start_time = time.monotonic()
        response = session.get(career_url, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        elapsed_ms = (time.monotonic() - start_time) * 1000

        result.http_status = response.status_code
        result.response_time_ms = round(elapsed_ms, 1)
        result.content_length_bytes = len(response.content)
        result.final_url = response.url

        if response.status_code == 403:
            result.outcome = "blocked_403"
            return result

        if response.status_code == 404:
            result.outcome = "not_found_404"
            return result

        if response.status_code >= 500:
            result.outcome = f"server_error_5xx"
            return result

        if response.status_code not in range(200, 400):
            result.outcome = f"other_{response.status_code}"
            return result

        result.redirected_to_homepage = detect_homepage_redirect(career_url, response.url)
        if result.redirected_to_homepage:
            result.outcome = "homepage_redirect"
            result.validation_notes = f"Redirected to {response.url}"
            return result

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            result.outcome = "non_html_200"
            result.validation_notes = f"Content-Type: {content_type}"
            return result

        soup = BeautifulSoup(response.content, "html.parser")

        for tag in soup(["script", "style", "noscript", "meta"]):
            tag.decompose()
        visible_text = soup.get_text(separator=" ", strip=True)

        result.career_keyword_count = count_career_keywords(visible_text)

        json_ld_jobs = count_json_ld_job_postings(soup)
        result.has_json_ld_jobs = json_ld_jobs > 0

        ats_embed = detect_ats_embed(soup)
        result.has_ats_embed = ats_embed is not None

        job_links = extract_job_links(soup, response.url)
        result.job_count_on_page = len(job_links)

        notes_parts: list[str] = []
        if json_ld_jobs > 0:
            notes_parts.append(f"{json_ld_jobs} JSON-LD jobs")
        if ats_embed:
            notes_parts.append(f"ATS embed: {ats_embed}")
        if job_links:
            notes_parts.append(f"{len(job_links)} job links")
        if result.career_keyword_count > 0:
            notes_parts.append(f"{result.career_keyword_count} career keywords")
        result.validation_notes = "; ".join(notes_parts)

        has_jobs_on_page = (
            result.has_json_ld_jobs
            or result.has_ats_embed
            or result.job_count_on_page >= 2
        )

        if has_jobs_on_page:
            result.outcome = "has_jobs"
        elif result.career_keyword_count >= 5:
            result.outcome = "careers_page_ok"
        else:
            result.outcome = "no_career_signals"

    except requests.exceptions.Timeout:
        result.outcome = "timeout"
        result.error_message = f"Timed out after {REQUEST_TIMEOUT_SECONDS}s"
    except requests.exceptions.SSLError as ssl_error:
        result.outcome = "ssl_error"
        result.error_message = str(ssl_error)[:150]
    except requests.exceptions.ConnectionError as conn_error:
        result.outcome = "connection_error"
        result.error_message = str(conn_error)[:150]
    except Exception as unexpected_error:
        result.outcome = "unexpected_error"
        result.error_message = str(unexpected_error)[:150]

    return result


def load_companies() -> list[dict]:
    """
    Load company name, sector, career URL, and headquarters from career_pages.csv.
    """
    companies: list[dict] = []
    with open(CAREER_PAGES_CSV_PATH, newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            company_name = row.get("Company Name", "").strip()
            career_url = row.get("Direct Career Portal", "").strip()
            sector = row.get("Sector", "").strip()
            headquarters = row.get("Global Headquarters & Regional Footprint", "").strip()
            if company_name and career_url:
                companies.append({
                    "company_name": company_name,
                    "sector": sector,
                    "career_url": career_url,
                    "headquarters": headquarters,
                })
    return companies


def write_results_csv(results: list[SmartProbeResult]) -> None:
    """
    Write all probe results to a CSV file sorted by outcome then company name.
    """
    fieldnames = [
        "outcome",
        "company_name",
        "sector",
        "original_url",
        "final_url",
        "http_status",
        "response_time_ms",
        "content_length_bytes",
        "job_count_on_page",
        "has_json_ld_jobs",
        "has_ats_embed",
        "career_keyword_count",
        "redirected_to_homepage",
        "validation_notes",
        "headquarters",
        "error_message",
    ]
    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as out_file:
        writer = csv.DictWriter(out_file, fieldnames=fieldnames)
        writer.writeheader()
        for result in sorted(results, key=lambda r: (r.outcome, r.company_name)):
            writer.writerow({
                "outcome": result.outcome,
                "company_name": result.company_name,
                "sector": result.sector,
                "original_url": result.original_url,
                "final_url": result.final_url or "",
                "http_status": result.http_status or "",
                "response_time_ms": result.response_time_ms or "",
                "content_length_bytes": result.content_length_bytes or "",
                "job_count_on_page": result.job_count_on_page,
                "has_json_ld_jobs": result.has_json_ld_jobs,
                "has_ats_embed": result.has_ats_embed,
                "career_keyword_count": result.career_keyword_count,
                "redirected_to_homepage": result.redirected_to_homepage,
                "validation_notes": result.validation_notes,
                "headquarters": result.headquarters,
                "error_message": result.error_message or "",
            })


def print_summary(results: list[SmartProbeResult]) -> None:
    """
    Print a grouped summary of all probe outcomes to stdout.
    """
    from collections import defaultdict
    total = len(results)
    by_outcome: dict[str, list[SmartProbeResult]] = defaultdict(list)
    for r in results:
        by_outcome[r.outcome].append(r)

    print(f"\n{'='*72}")
    print(f"  SMART CAREER PAGE PROBE RESULTS  ({total} companies)")
    print(f"{'='*72}")

    outcome_order = [
        "has_jobs", "careers_page_ok", "blocked_403",
        "homepage_redirect", "no_career_signals",
        "not_found_404", "connection_error", "ssl_error",
        "timeout", "server_error_5xx", "non_html_200", "unexpected_error",
    ]
    other_outcomes = [o for o in by_outcome if o not in outcome_order]

    for outcome in outcome_order + other_outcomes:
        group = by_outcome.get(outcome, [])
        if not group:
            continue
        pct = len(group) / total * 100
        if outcome in ("has_jobs", "careers_page_ok"):
            marker = "✓"
        elif outcome == "blocked_403":
            marker = "⚠"
        else:
            marker = "✗"
        print(f"  {marker}  {outcome:<28}  {len(group):>4}  ({pct:5.1f}%)")

    verified_ok = len(by_outcome.get("has_jobs", [])) + len(by_outcome.get("careers_page_ok", []))
    usable = verified_ok + len(by_outcome.get("blocked_403", []))
    print(f"{'='*72}")
    print(f"  Verified working (jobs + career page): {verified_ok}  ({verified_ok/total*100:.1f}%)")
    print(f"  Usable incl. bot-blocked:              {usable}  ({usable/total*100:.1f}%)")
    print(f"\n  Output CSV: {OUTPUT_CSV_PATH}")

    homepage_redirects = by_outcome.get("homepage_redirect", [])
    if homepage_redirects:
        print(f"\n  — Homepage Redirects (wrong URL in CSV) —")
        for r in sorted(homepage_redirects, key=lambda x: x.company_name)[:20]:
            print(f"    {r.company_name:<40}  {r.original_url}  →  {r.final_url}")
        if len(homepage_redirects) > 20:
            print(f"    ... and {len(homepage_redirects) - 20} more (see CSV)")

    no_signals = by_outcome.get("no_career_signals", [])
    if no_signals:
        print(f"\n  — No Career Signals (URL works but page doesn't look like careers) —")
        for r in sorted(no_signals, key=lambda x: x.company_name)[:20]:
            print(f"    {r.company_name:<40}  {r.original_url}")
        if len(no_signals) > 20:
            print(f"    ... and {len(no_signals) - 20} more (see CSV)")

    has_jobs = by_outcome.get("has_jobs", [])
    if has_jobs:
        times = [r.response_time_ms for r in has_jobs if r.response_time_ms]
        times.sort()
        avg = sum(times) / len(times)
        total_jobs = sum(r.job_count_on_page for r in has_jobs)
        print(f"\n  — has_jobs stats —")
        print(f"    Total job links found across all pages: {total_jobs}")
        print(f"    Average response time: {avg:.0f}ms")
        print(f"    Median response time:  {times[len(times)//2]:.0f}ms")
        ats_count = sum(1 for r in has_jobs if r.has_ats_embed)
        jld_count = sum(1 for r in has_jobs if r.has_json_ld_jobs)
        print(f"    With ATS embed:    {ats_count}")
        print(f"    With JSON-LD jobs: {jld_count}")


def main():
    companies = load_companies()
    print(f"Smart-probing {len(companies)} company career pages ({MAX_WORKERS} workers)...")
    print(f"Timeout: {REQUEST_TIMEOUT_SECONDS}s | Validating: redirects, keywords, job links, JSON-LD, ATS embeds\n")

    results: list[SmartProbeResult] = []
    session = create_probe_session()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_name = {
            executor.submit(
                smart_probe,
                c["company_name"],
                c["sector"],
                c["career_url"],
                c["headquarters"],
                session,
            ): c["company_name"]
            for c in companies
        }

        completed = 0
        for future in as_completed(future_to_name):
            result = future.result()
            results.append(result)
            completed += 1
            notes = f"  [{result.validation_notes}]" if result.validation_notes else ""
            status = f"HTTP {result.http_status}" if result.http_status else result.outcome
            print(
                f"  [{completed:>3}/{len(companies)}]  {result.outcome:<28}  "
                f"{result.company_name:<35}  {status}{notes}",
                flush=True,
            )

    write_results_csv(results)
    print_summary(results)


if __name__ == "__main__":
    main()
