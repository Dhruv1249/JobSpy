"""
Live connectivity probe for all career pages in career_pages.csv.

Makes a single HEAD (then GET fallback) request to each company's career URL,
records the HTTP status, response time, and content length, and outputs both
a per-company CSV report and a console summary grouped by outcome.
"""

import csv
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import requests
from requests.adapters import HTTPAdapter, Retry

CSV_PATH = pathlib.Path(__file__).parent.parent / "jobspy" / "career_pages.csv"
OUTPUT_CSV_PATH = pathlib.Path(__file__).parent.parent / "career_pages_probe_results.csv"

REQUEST_TIMEOUT_SECONDS = 12
MAX_WORKERS = 30

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SUCCESS_STATUS_CODES = frozenset(range(200, 400))

REDIRECT_STATUS_CODES = frozenset([301, 302, 303, 307, 308])


@dataclass
class ProbeResult:
    company_name: str
    sector: str
    career_url: str
    headquarters: str
    http_status: Optional[int] = None
    response_time_ms: Optional[float] = None
    content_length_bytes: Optional[int] = None
    final_url: Optional[str] = None
    error_message: Optional[str] = None
    outcome: str = "unknown"


def create_probe_session() -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(total=1, connect=1, status_forcelist=[429, 503])
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(BROWSER_HEADERS)
    return session


def probe_career_url(
    company_name: str,
    sector: str,
    career_url: str,
    headquarters: str,
    session: requests.Session,
) -> ProbeResult:
    result = ProbeResult(
        company_name=company_name,
        sector=sector,
        career_url=career_url,
        headquarters=headquarters,
    )

    try:
        start_time = time.monotonic()
        response = session.get(
            career_url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        elapsed_ms = (time.monotonic() - start_time) * 1000

        result.http_status = response.status_code
        result.response_time_ms = round(elapsed_ms, 1)
        result.content_length_bytes = len(response.content)
        result.final_url = response.url

        if response.status_code in SUCCESS_STATUS_CODES:
            result.outcome = "success"
        elif response.status_code == 403:
            result.outcome = "blocked_403"
        elif response.status_code == 404:
            result.outcome = "not_found_404"
        elif response.status_code == 429:
            result.outcome = "rate_limited_429"
        elif response.status_code >= 500:
            result.outcome = "server_error_5xx"
        else:
            result.outcome = f"other_{response.status_code}"

    except requests.exceptions.Timeout:
        result.outcome = "timeout"
        result.error_message = f"Timed out after {REQUEST_TIMEOUT_SECONDS}s"
    except requests.exceptions.SSLError as ssl_error:
        result.outcome = "ssl_error"
        result.error_message = str(ssl_error)[:120]
    except requests.exceptions.ConnectionError as conn_error:
        result.outcome = "connection_error"
        result.error_message = str(conn_error)[:120]
    except Exception as unexpected_error:
        result.outcome = "unexpected_error"
        result.error_message = str(unexpected_error)[:120]

    return result


def load_companies() -> list[dict]:
    companies = []
    with open(CSV_PATH, newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            companies.append({
                "company_name": row.get("Company Name", "").strip(),
                "sector": row.get("Sector", "").strip(),
                "career_url": row.get("Direct Career Portal", "").strip(),
                "headquarters": row.get("Global Headquarters & Regional Footprint", "").strip(),
            })
    return [c for c in companies if c["company_name"] and c["career_url"]]


def write_results_csv(results: list[ProbeResult]) -> None:
    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as out_file:
        fieldnames = [
            "outcome",
            "company_name",
            "sector",
            "career_url",
            "final_url",
            "http_status",
            "response_time_ms",
            "content_length_bytes",
            "headquarters",
            "error_message",
        ]
        writer = csv.DictWriter(out_file, fieldnames=fieldnames)
        writer.writeheader()
        for result in sorted(results, key=lambda r: (r.outcome, r.company_name)):
            writer.writerow({
                "outcome": result.outcome,
                "company_name": result.company_name,
                "sector": result.sector,
                "career_url": result.career_url,
                "final_url": result.final_url or "",
                "http_status": result.http_status or "",
                "response_time_ms": result.response_time_ms or "",
                "content_length_bytes": result.content_length_bytes or "",
                "headquarters": result.headquarters,
                "error_message": result.error_message or "",
            })


def print_summary(results: list[ProbeResult]) -> None:
    outcome_groups: dict[str, list[ProbeResult]] = {}
    for result in results:
        outcome_groups.setdefault(result.outcome, []).append(result)

    total = len(results)
    successful = outcome_groups.get("success", [])
    blocked = outcome_groups.get("blocked_403", [])

    print(f"\n{'='*70}")
    print(f"  CAREER PAGE PROBE RESULTS  ({total} companies)")
    print(f"{'='*70}")

    for outcome, group in sorted(outcome_groups.items(), key=lambda x: -len(x[1])):
        pct = len(group) / total * 100
        marker = "✓" if outcome == "success" else "⚠" if outcome == "blocked_403" else "✗"
        print(f"  {marker}  {outcome:<25}  {len(group):>4} companies  ({pct:5.1f}%)")

    print(f"{'='*70}")
    print(f"  Total reachable (success + 403):  {len(successful) + len(blocked)}")
    print(f"  Results written to: {OUTPUT_CSV_PATH}")

    if blocked:
        print(f"\n  — 403 Blocked (bot protection, page likely works in browser) —")
        for r in sorted(blocked, key=lambda x: x.company_name)[:30]:
            print(f"    {r.company_name:<40}  {r.career_url}")
        if len(blocked) > 30:
            print(f"    ... and {len(blocked) - 30} more (see CSV)")

    failures = [
        r for r in results
        if r.outcome not in ("success", "blocked_403")
    ]
    if failures:
        print(f"\n  — Failed / Unreachable —")
        for r in sorted(failures, key=lambda x: (x.outcome, x.company_name))[:50]:
            err = f"  [{r.error_message[:60]}]" if r.error_message else f"  [HTTP {r.http_status}]" if r.http_status else ""
            print(f"    {r.outcome:<22}  {r.company_name:<35}  {r.career_url[:50]}{err}")
        if len(failures) > 50:
            print(f"    ... and {len(failures) - 50} more (see CSV)")

    if successful:
        avg_time = sum(r.response_time_ms for r in successful if r.response_time_ms) / len(successful)
        print(f"\n  — Success stats —")
        print(f"    Average response time: {avg_time:.0f}ms")
        slowest = sorted(successful, key=lambda r: r.response_time_ms or 0, reverse=True)[:5]
        print(f"    Slowest responses:")
        for r in slowest:
            print(f"      {r.response_time_ms:>6.0f}ms  {r.company_name}")


def main():
    companies = load_companies()
    print(f"Probing {len(companies)} company career pages with {MAX_WORKERS} workers...")
    print(f"Timeout: {REQUEST_TIMEOUT_SECONDS}s per request\n")

    results: list[ProbeResult] = []
    completed_count = 0

    session = create_probe_session()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_company = {
            executor.submit(
                probe_career_url,
                company["company_name"],
                company["sector"],
                company["career_url"],
                company["headquarters"],
                session,
            ): company["company_name"]
            for company in companies
        }

        for future in as_completed(future_to_company):
            result = future.result()
            results.append(result)
            completed_count += 1

            status_display = f"HTTP {result.http_status}" if result.http_status else result.outcome
            print(
                f"  [{completed_count:>3}/{len(companies)}]  {result.outcome:<22}  "
                f"{result.company_name:<35}  {status_display}",
                flush=True,
            )

    write_results_csv(results)
    print_summary(results)


if __name__ == "__main__":
    main()
