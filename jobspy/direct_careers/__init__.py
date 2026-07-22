"""
Direct Company Career HTML pages scraper for JobSpy.
"""

import re
import urllib.parse
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

DIRECT_COMPANY_CAREER_URLS = [
    ("Aptos Labs", "https://aptoslabs.com/careers"),
    ("Astral", "https://astral.sh"),
    ("Ava Labs", "https://www.avalabs.org/careers"),
    ("Buoyant", "https://buoyant.io/careers"),
    ("Canonical", "https://canonical.com/careers"),
    ("Chainguard", "https://www.chainguard.dev/careers"),
    ("Chainlink Labs", "https://careers.chain.link"),
    ("Cloudflare", "https://www.cloudflare.com/careers"),
    ("Datadog", "https://careers.datadoghq.com"),
    ("Deno", "https://deno.com/jobs"),
    ("Docker", "https://www.docker.com/careers"),
    ("Ferrous Systems", "https://ferrous-systems.com/careers"),
    ("Flashbots", "https://collective.flashbots.net"),
    ("Fly.io", "https://fly.io/jobs"),
    ("GitHub", "https://github.careers"),
    ("Grafana Labs", "https://grafana.com/about/careers"),
    ("Greptime", "https://greptime.com/careers"),
    ("HashiCorp", "https://www.hashicorp.com/careers"),
    ("Isovalent", "https://isovalent.com/careers"),
    ("Kubecost", "https://www.kubecost.com/careers"),
    ("Loft Labs", "https://loft.sh/careers"),
    ("Materialize", "https://materialize.com/careers"),
    ("Matter Labs", "https://matter-labs.io/careers"),
    ("Mirantis", "https://www.mirantis.com/company/careers"),
    ("Nutanix", "https://www.nutanix.com/careers"),
    ("Oxide Computer", "https://oxide.computer/careers"),
    ("Parity Technologies", "https://www.parity.io/careers"),
    ("Pulumi", "https://www.pulumi.com/careers"),
    ("Red Hat", "https://www.redhat.com/en/jobs"),
    ("Solo.io", "https://www.solo.io/company/careers"),
    ("SUSE", "https://www.suse.com/careers"),
    ("TigerBeetle", "https://tigerbeetle.com"),
    ("Zed Industries", "https://zed.dev/jobs"),
    ("Neon", "https://neon.tech/careers"),
    ("PingCAP", "https://pingcap.com/careers"),
    ("PostHog", "https://posthog.com/careers"),
    ("Tailscale", "https://tailscale.com/careers"),
    ("ClickHouse", "https://clickhouse.com/company/careers"),
    ("Cockroach Labs", "https://www.cockroachlabs.com/careers"),
    ("Confluent", "https://www.confluent.io/careers"),
    ("Elastic", "https://www.elastic.co/careers"),
    ("Ethereum Foundation", "https://ethereum.foundation"),
    ("Kraken", "https://www.kraken.com/careers"),
    ("MongoDB", "https://www.mongodb.com/company/careers"),
    ("Mysten Labs", "https://mystenlabs.com/careers"),
    ("Offchain Labs", "https://offchainlabs.com/careers"),
    ("PlanetScale", "https://planetscale.com/careers"),
    ("ScyllaDB", "https://www.scylladb.com/careers"),
    ("Supabase", "https://supabase.com/careers"),
    ("Turso", "https://turso.tech/careers"),
    ("Qdrant", "https://qdrant.tech/careers"),
    ("Temporal.io", "https://temporal.io/careers"),
    ("Together AI", "https://together.ai/careers"),
    ("Aiven", "https://aiven.io/careers"),
    ("Akuity", "https://akuity.io/careers"),
    ("DigitalOcean", "https://www.digitalocean.com/careers"),
    ("Fastly", "https://www.fastly.com/about/careers"),
    ("GitLab", "https://about.gitlab.com/jobs"),
    ("Harness", "https://www.harness.io/careers"),
    ("Humanitec", "https://humanitec.com/careers"),
    ("JetBrains", "https://www.jetbrains.com/careers"),
    ("Netlify", "https://www.netlify.com/careers"),
    ("Sourcegraph", "https://sourcegraph.com/careers"),
    ("Vercel", "https://vercel.com/careers")
]

def resolve_company_career_urls(company_name: str) -> list[str]:
    """
    Generate candidate direct career page URLs for any company name or slug.
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
        f"https://{clean_name}.app/careers"
    ]

class DirectCareers(Scraper):
    """
    Scraper for direct company career HTML pages.
    """

    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        """
        Initialize DirectCareers scraper.
        """
        super().__init__(Site.DIRECT_CAREERS, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            })

    def scrape_single_company(self, company_name: str, career_url: str, job_link_pattern: re.Pattern) -> list[JobPost]:
        """
        Scrape a single company career HTML page directly, attempting dynamic domain URL resolution if primary URL fails.
        """
        urls_to_try = [career_url] if career_url else []
        urls_to_try.extend(resolve_company_career_urls(company_name))

        for target_url in urls_to_try:
            try:
                response = self.session.get(
                    target_url,
                    timeout=15
                )
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.content, "html.parser")
                seen_urls = set()
                company_jobs = []

                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        import json
                        script_text = script.string or script.get_text()
                        if not script_text:
                            continue
                        ld_data = json.loads(script_text)
                        if isinstance(ld_data, dict):
                            ld_items = [ld_data]
                        elif isinstance(ld_data, list):
                            ld_items = ld_data
                        else:
                            ld_items = []

                        for item in ld_items:
                            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                                title = item.get("title", "")
                                job_url = item.get("url") or target_url
                                desc = item.get("description", "")
                                loc_data = item.get("jobLocation", {})
                                loc_str = "Remote"
                                if isinstance(loc_data, dict):
                                    address = loc_data.get("address", {})
                                    if isinstance(address, dict):
                                        loc_str = address.get("addressLocality") or address.get("addressCountry") or "Remote"

                                if title and job_url not in seen_urls:
                                    seen_urls.add(job_url)
                                    company_jobs.append(
                                        JobPost(
                                            id=job_url,
                                            title=title,
                                            company_name=company_name,
                                            job_url=job_url,
                                            location=Location(country=loc_str),
                                            description=desc or f"Direct posting from {company_name}",
                                            is_remote="remote" in loc_str.lower() or item.get("applicantLocationRequirements") is not None
                                        )
                                    )
                    except Exception:
                        pass

                for iframe in soup.find_all(["iframe", "script"], src=True):
                    src = iframe.get("src", "")
                    if any(ats in src for ats in ["greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com", "myworkdaysite.com"]):
                        try:
                            emb_resp = self.session.get(src, timeout=15)
                            if emb_resp.status_code == 200:
                                emb_soup = BeautifulSoup(emb_resp.content, "html.parser")
                                for a_tag in emb_soup.find_all("a", href=True):
                                    href = a_tag.get("href", "").strip()
                                    full_url = urllib.parse.urljoin(src, href)
                                    title = a_tag.get_text(strip=True)
                                    if title and len(title) >= 4 and full_url not in seen_urls:
                                        seen_urls.add(full_url)
                                        company_jobs.append(
                                            JobPost(
                                                id=full_url,
                                                title=title,
                                                company_name=company_name,
                                                job_url=full_url,
                                                location=Location(country="Remote"),
                                                description=f"Embedded ATS posting from {company_name}",
                                                is_remote=True
                                            )
                                        )
                        except Exception:
                            pass

                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "").strip()
                    if not href or href.startswith("#") or href.startswith("javascript:"):
                        continue

                    full_url = urllib.parse.urljoin(target_url, href)
                    if full_url in seen_urls:
                        continue

                    if job_link_pattern.search(full_url) or job_link_pattern.search(href):
                        title = a_tag.get_text(strip=True)
                        if not title or len(title) < 4 or title.lower() in ["careers", "jobs", "apply", "view all", "learn more"]:
                            parent = a_tag.find_parent(["h1", "h2", "h3", "h4", "li", "div", "tr"])
                            if parent:
                                title = parent.get_text(strip=True)

                        if title and len(title) >= 4 and len(title) <= 120:
                            seen_urls.add(full_url)
                            company_jobs.append(
                                JobPost(
                                    id=full_url,
                                    title=title,
                                    company_name=company_name,
                                    job_url=full_url,
                                    location=Location(country="Remote"),
                                    description=f"Direct career posting from {company_name} at {full_url}",
                                    is_remote=True
                                )
                            )
                if company_jobs:
                    return company_jobs
            except Exception:
                continue

        return []

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrape jobs directly from official company career HTML pages concurrently.
        """
        jobs = []
        job_link_pattern = re.compile(r"/(jobs?|careers?|postings?|position|role|openings?)/", re.IGNORECASE)

        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(self.scrape_single_company, company_name, career_url, job_link_pattern)
                for company_name, career_url in DIRECT_COMPANY_CAREER_URLS
            ]
            for future in as_completed(futures):
                res = future.result()
                jobs.extend(res)

        return JobResponse(jobs=jobs[:scraper_input.results_wanted if scraper_input.results_wanted else None])
