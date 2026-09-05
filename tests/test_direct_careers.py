"""
Unit tests for the DirectCareers jobspy scraper.
"""

import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

from jobspy.direct_careers import (
    DirectCareers,
    _get_career_pages,
    _parse_date_posted,
    load_career_pages,
    resolve_company_career_urls,
)
from jobspy.model import DescriptionFormat, ScraperInput, Site


class TestLoadCareerPages(unittest.TestCase):
    """
    Tests for the CSV-based company career page loader.
    """

    def test_csv_loading_populates_company_list(self):
        """
        Verify that load_career_pages reads the CSV and returns a non-empty list of tuples.
        """
        pages = load_career_pages()
        self.assertIsInstance(pages, list)
        self.assertGreater(len(pages), 0)

    def test_csv_entries_have_three_fields(self):
        """
        Verify each entry is a 3-tuple of (company_name, career_url, headquarters).
        """
        pages = load_career_pages()
        for entry in pages:
            self.assertEqual(len(entry), 3)
            company_name, career_url, headquarters = entry
            self.assertIsInstance(company_name, str)
            self.assertIsInstance(career_url, str)
            self.assertIsInstance(headquarters, str)

    def test_csv_entries_have_non_empty_names_and_urls(self):
        """
        Verify all loaded entries have non-empty company names and career URLs.
        """
        pages = load_career_pages()
        for company_name, career_url, _ in pages:
            self.assertTrue(company_name, f"Empty company name found")
            self.assertTrue(career_url, f"Empty career URL for {company_name}")

    def test_cached_career_pages_returns_same_object(self):
        """
        Verify _get_career_pages returns the same cached list on repeated calls.
        """
        first_call = _get_career_pages()
        second_call = _get_career_pages()
        self.assertIs(first_call, second_call)


class TestResolveCompanyCareerUrls(unittest.TestCase):
    """
    Tests for the heuristic company career URL generator.
    """

    def test_generates_candidate_urls_for_simple_name(self):
        """
        Verify that a simple company name produces a non-empty list of URL candidates.
        """
        candidates = resolve_company_career_urls("Acme")
        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)

    def test_generated_urls_contain_company_slug(self):
        """
        Verify that each generated URL includes the cleaned company name slug.
        """
        candidates = resolve_company_career_urls("OpenAI")
        for url in candidates:
            self.assertIn("openai", url.lower())

    def test_strips_special_characters_from_company_name(self):
        """
        Verify that special characters are stripped before generating URL slugs,
        so the resulting slug embedded in URLs contains no dots from the original name.
        """
        candidates = resolve_company_career_urls("Fly.io")
        for url in candidates:
            self.assertIn("flyio", url)

    def test_returns_empty_list_for_empty_name(self):
        """
        Verify that an empty or symbol-only company name produces no candidates.
        """
        self.assertEqual(resolve_company_career_urls(""), [])
        self.assertEqual(resolve_company_career_urls("---"), [])

    def test_includes_dotcom_and_dotio_variants(self):
        """
        Verify that both .com and .io domain variants are included in candidates.
        """
        candidates = resolve_company_career_urls("TestCo")
        urls_joined = " ".join(candidates)
        self.assertIn(".com", urls_joined)
        self.assertIn(".io", urls_joined)


class TestParseDatePosted(unittest.TestCase):
    """
    Tests for the JSON-LD date parsing utility.
    """

    def test_parses_iso_date_string(self):
        """
        Verify that a standard ISO 8601 date string is parsed to a date object.
        """
        result = _parse_date_posted("2024-03-15")
        self.assertIsNotNone(result)

    def test_parses_iso_datetime_string(self):
        """
        Verify that an ISO 8601 datetime string is parsed correctly.
        """
        result = _parse_date_posted("2024-03-15T12:00:00Z")
        self.assertIsNotNone(result)

    def test_returns_none_for_none_input(self):
        """
        Verify that None input returns None without raising.
        """
        self.assertIsNone(_parse_date_posted(None))

    def test_returns_none_for_invalid_string(self):
        """
        Verify that an unparseable string returns None without raising.
        """
        self.assertIsNone(_parse_date_posted("not-a-date"))

    def test_returns_none_for_empty_string(self):
        """
        Verify that an empty string returns None.
        """
        self.assertIsNone(_parse_date_posted(""))


class TestDirectCareersScraper(unittest.TestCase):
    """
    Unit tests for the DirectCareers scraper's scraping and filtering logic.
    """

    def setUp(self):
        self.scraper = DirectCareers()
        self.mock_session = MagicMock()
        self.scraper.session = self.mock_session

    def _make_mock_response(self, html: str, status_code: int = 200) -> Mock:
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.content = html.encode("utf-8")
        return mock_response

    def _make_scraper_input(self, **kwargs) -> ScraperInput:
        defaults = {"site_type": [Site.DIRECT_CAREERS], "results_wanted": 50}
        defaults.update(kwargs)
        return ScraperInput(**defaults)

    def test_scrape_with_json_ld_job_posting(self):
        """
        Verify that a JSON-LD JobPosting on a career page is parsed into a JobPost.
        """
        ld_json_payload = json.dumps({
            "@type": "JobPosting",
            "title": "Senior Backend Engineer",
            "url": "https://example.com/jobs/senior-backend-engineer",
            "description": "We are looking for a senior engineer.",
            "datePosted": "2024-06-01",
            "jobLocation": {
                "address": {"addressLocality": "San Francisco"}
            }
        })
        html = f'<html><head><script type="application/ld+json">{ld_json_payload}</script></head><body></body></html>'
        self.mock_session.get.return_value = self._make_mock_response(html)

        result = self.scraper.scrape_single_company(
            "ExampleCorp", "https://example.com/careers"
        )

        self.assertEqual(len(result), 1)
        job = result[0]
        self.assertEqual(job.title, "Senior Backend Engineer")
        self.assertEqual(job.job_url, "https://example.com/jobs/senior-backend-engineer")
        self.assertEqual(job.company_name, "ExampleCorp")
        self.assertIsNotNone(job.date_posted)

    def test_scrape_with_anchor_tag_pattern(self):
        """
        Verify that anchor tags matching job URL patterns are extracted as JobPost objects.
        """
        html = """<html><body>
            <a href="/jobs/software-engineer">Software Engineer</a>
            <a href="/jobs/product-manager">Product Manager</a>
        </body></html>"""
        self.mock_session.get.return_value = self._make_mock_response(html)

        result = self.scraper.scrape_single_company(
            "AnchorCorp", "https://anchorcorp.com/careers"
        )

        self.assertGreaterEqual(len(result), 1)
        titles = [job.title for job in result]
        self.assertIn("Software Engineer", titles)

    def test_scrape_with_embedded_ats_iframe(self):
        """
        Verify that an embedded Greenhouse iframe triggers a nested fetch for job links.
        """
        outer_html = '<html><body><iframe src="https://boards.greenhouse.io/embed/acme"></iframe></body></html>'
        inner_html = '<html><body><a href="/jobs/1234">Staff Engineer</a></body></html>'

        def session_get_side_effect(url, **kwargs):
            if "greenhouse" in url:
                return self._make_mock_response(inner_html)
            return self._make_mock_response(outer_html)

        self.mock_session.get.side_effect = session_get_side_effect

        result = self.scraper.scrape_single_company(
            "AcmeCorp", "https://acmecorp.com/careers"
        )

        self.assertGreater(len(result), 0)

    def test_scrape_handles_http_error_gracefully(self):
        """
        Verify that a non-200 HTTP response from all URLs returns an empty list without raising.
        """
        self.mock_session.get.return_value = self._make_mock_response("", status_code=404)

        result = self.scraper.scrape_single_company(
            "BrokenCorp", "https://brokencorp.com/careers"
        )

        self.assertEqual(result, [])

    def test_scrape_handles_network_exception_gracefully(self):
        """
        Verify that a network-level exception from session.get returns an empty list without raising.
        """
        self.mock_session.get.side_effect = ConnectionError("Network unreachable")

        result = self.scraper.scrape_single_company(
            "OfflineCorp", "https://offlinecorp.com/careers"
        )

        self.assertEqual(result, [])

    def test_scrape_date_posted_from_json_ld(self):
        """
        Verify that the datePosted field in JSON-LD is reflected in the JobPost date_posted attribute.
        """
        ld_json_payload = json.dumps({
            "@type": "JobPosting",
            "title": "Data Engineer",
            "url": "https://example.com/jobs/data-engineer",
            "datePosted": "2024-01-20",
        })
        html = f'<html><head><script type="application/ld+json">{ld_json_payload}</script></head><body></body></html>'
        self.mock_session.get.return_value = self._make_mock_response(html)

        result = self.scraper.scrape_single_company("DateCorp", "https://datecorp.com/careers")

        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].date_posted)

    def test_scrape_respects_results_wanted(self):
        """
        Verify that the total result count is capped at results_wanted.
        """
        html = "\n".join(
            f'<a href="/jobs/role-{i}">Role Title {i}</a>' for i in range(100)
        )
        html = f"<html><body>{html}</body></html>"
        self.mock_session.get.return_value = self._make_mock_response(html)

        with patch(
            "jobspy.direct_careers._get_career_pages",
            return_value=[("OnlyCo", "https://onlyco.com/careers", "USA")],
        ):
            scraper_input = self._make_scraper_input(results_wanted=3)
            response = self.scraper.scrape(scraper_input)

        self.assertLessEqual(len(response.jobs), 3)

    def test_scrape_search_term_filters_job_titles(self):
        """
        Verify that only jobs whose titles contain the search_term are returned.
        """
        html = """<html><body>
            <a href="/jobs/python-engineer">Python Engineer</a>
            <a href="/jobs/java-developer">Java Developer</a>
            <a href="/jobs/python-architect">Python Architect</a>
        </body></html>"""
        self.mock_session.get.return_value = self._make_mock_response(html)

        with patch(
            "jobspy.direct_careers._get_career_pages",
            return_value=[("FilterCo", "https://filterco.com/careers", "USA")],
        ):
            scraper_input = self._make_scraper_input(
                search_term="python", results_wanted=50
            )
            response = self.scraper.scrape(scraper_input)

        for job in response.jobs:
            self.assertIn("python", job.title.lower())

    def test_scrape_is_remote_filter_excludes_non_remote(self):
        """
        Verify that is_remote=True filters out jobs where is_remote is not True.
        """
        ld_json_payload = json.dumps({
            "@type": "JobPosting",
            "title": "On-Site Engineer",
            "url": "https://example.com/jobs/onsite",
            "jobLocation": {"address": {"addressLocality": "New York"}},
        })
        html = f'<html><head><script type="application/ld+json">{ld_json_payload}</script></head><body></body></html>'
        self.mock_session.get.return_value = self._make_mock_response(html)

        with patch(
            "jobspy.direct_careers._get_career_pages",
            return_value=[("OfficeOnly", "https://officeonly.com/careers", "New York")],
        ):
            scraper_input = self._make_scraper_input(is_remote=True, results_wanted=50)
            response = self.scraper.scrape(scraper_input)

        for job in response.jobs:
            self.assertTrue(job.is_remote)

    def test_scrape_description_format_markdown_applied(self):
        """
        Verify that HTML descriptions are converted to markdown when description_format=MARKDOWN.
        """
        ld_json_payload = json.dumps({
            "@type": "JobPosting",
            "title": "ML Engineer",
            "url": "https://example.com/jobs/ml",
            "description": "<p>We need a <strong>talented</strong> engineer.</p>",
        })
        html = f'<html><head><script type="application/ld+json">{ld_json_payload}</script></head><body></body></html>'
        self.mock_session.get.return_value = self._make_mock_response(html)

        result = self.scraper.scrape_single_company(
            "MLCorp",
            "https://mlcorp.com/careers",
            description_format=DescriptionFormat.MARKDOWN,
        )

        self.assertEqual(len(result), 1)
        description = result[0].description
        self.assertIsNotNone(description)
        self.assertNotIn("<p>", description)

    def test_scrape_description_format_plain_applied(self):
        """
        Verify that HTML descriptions are stripped to plain text when description_format=PLAIN.
        """
        ld_json_payload = json.dumps({
            "@type": "JobPosting",
            "title": "DevOps Engineer",
            "url": "https://example.com/jobs/devops",
            "description": "<p>Join our <em>amazing</em> team.</p>",
        })
        html = f'<html><head><script type="application/ld+json">{ld_json_payload}</script></head><body></body></html>'
        self.mock_session.get.return_value = self._make_mock_response(html)

        result = self.scraper.scrape_single_company(
            "DevOpsCorp",
            "https://devopscorp.com/careers",
            description_format=DescriptionFormat.PLAIN,
        )

        self.assertEqual(len(result), 1)
        description = result[0].description
        self.assertIsNotNone(description)
        self.assertNotIn("<em>", description)

    def test_scrape_company_url_populated_on_job_post(self):
        """
        Verify that company_url and company_url_direct are set on parsed JobPost objects.
        """
        ld_json_payload = json.dumps({
            "@type": "JobPosting",
            "title": "Frontend Engineer",
            "url": "https://frontendco.com/jobs/frontend",
        })
        html = f'<html><head><script type="application/ld+json">{ld_json_payload}</script></head><body></body></html>'
        self.mock_session.get.return_value = self._make_mock_response(html)

        result = self.scraper.scrape_single_company(
            "FrontendCo", "https://frontendco.com/careers"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].company_url, "https://frontendco.com/careers")
        self.assertEqual(result[0].company_url_direct, "https://frontendco.com/careers")

    def test_scrape_location_filter_narrows_company_list(self):
        """
        Verify that providing a location reduces the company list to those with matching HQ.
        """
        self.mock_session.get.return_value = self._make_mock_response(
            "<html><body></body></html>"
        )

        career_pages_stub = [
            ("SFCo", "https://sfco.com/careers", "San Francisco, CA, USA"),
            ("NYCo", "https://nyco.com/careers", "New York, NY, USA"),
        ]

        with patch(
            "jobspy.direct_careers._get_career_pages",
            return_value=career_pages_stub,
        ):
            scraper_input = self._make_scraper_input(
                location="San Francisco", results_wanted=50
            )
            self.scraper.scrape(scraper_input)

        called_urls = [call.args[0] for call in self.mock_session.get.call_args_list]
        self.assertTrue(
            any("sfco" in url for url in called_urls),
            "Expected SFCo to be scraped for San Francisco location filter",
        )

    def test_scrape_deduplicate_job_urls_within_single_company(self):
        """
        Verify that duplicate job URLs from different extraction strategies are not added twice.
        """
        job_url = "https://example.com/jobs/unique-role"
        ld_json_payload = json.dumps({
            "@type": "JobPosting",
            "title": "Unique Role",
            "url": job_url,
        })
        html = f"""<html>
            <head><script type="application/ld+json">{ld_json_payload}</script></head>
            <body>
                <a href="{job_url}">Unique Role</a>
            </body>
        </html>"""
        self.mock_session.get.return_value = self._make_mock_response(html)

        result = self.scraper.scrape_single_company("DedupCo", "https://example.com/careers")

        job_urls = [job.job_url for job in result]
        self.assertEqual(len(job_urls), len(set(job_urls)), "Duplicate job URLs found in results")


if __name__ == "__main__":
    unittest.main()
