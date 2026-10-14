"""
Unit tests for the OracleCloud JobSpy scraper.
"""

import unittest
from unittest.mock import Mock

from jobspy.model import ScraperInput, Site
from jobspy.oracle_cloud import OracleCloud


class TestOracleCloudScraper(unittest.TestCase):
    """
    Unit test suite validating OracleCloud HCM Candidate Experience API scraping and parsing.
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = OracleCloud(tenant="jpmc", site_number="CX_1001", company_name="JPMorgan Chase")
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify OracleCloud scraper parses requisition list correctly from JSON response.
        """
        payload = {
            "items": [
                {
                    "TotalJobsCount": 100,
                    "requisitionList": [
                        {
                            "Id": 210775950,
                            "Title": "Lead Software Engineer - Python",
                            "PrimaryLocation": "Bengaluru, Karnataka, India",
                            "PrimaryLocationCountry": "IN",
                            "ShortDescriptionStr": "Build high-throughput quantitative analytics platforms.",
                            "JobFamily": "Software Engineering",
                            "Organization": "Corporate & Investment Bank",
                            "Department": "Global Markets",
                            "WorkplaceType": "Hybrid",
                            "PostedDate": "2026-10-01T12:00:00Z",
                        }
                    ],
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.ORACLE_CLOUD],
            search_term="Python",
            location="India",
            results_wanted=5,
        )
        response = self.scraper.scrape(scraper_input)

        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "210775950")
        self.assertEqual(job.title, "Lead Software Engineer - Python")
        self.assertEqual(job.company_name, "JPMorgan Chase")
        self.assertEqual(job.location.country, "Bengaluru, Karnataka, India")
        self.assertIn("CX_1001/job/210775950", job.job_url)
        self.assertIn("Global Markets", job.description)

    def test_scrape_filters_by_location(self):
        """
        Verify OracleCloud scraper discards jobs outside requested location filter.
        """
        payload = {
            "items": [
                {
                    "requisitionList": [
                        {
                            "Id": 111,
                            "Title": "Software Engineer",
                            "PrimaryLocation": "London, United Kingdom",
                            "PrimaryLocationCountry": "GB",
                        },
                        {
                            "Id": 222,
                            "Title": "Software Engineer",
                            "PrimaryLocation": "Mumbai, Maharashtra, India",
                            "PrimaryLocationCountry": "IN",
                        },
                    ],
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.ORACLE_CLOUD],
            search_term="Software",
            location="India",
            results_wanted=5,
        )
        response = self.scraper.scrape(scraper_input)

        self.assertEqual(len(response.jobs), 1)
        self.assertEqual(response.jobs[0].id, "222")

    def test_scrape_http_error_handled(self):
        """
        Verify OracleCloud scraper handles non-200 responses without throwing unhandled exceptions.
        """
        mock_response = Mock()
        mock_response.status_code = 502
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.ORACLE_CLOUD],
            search_term="Software",
            results_wanted=5,
        )
        response = self.scraper.scrape(scraper_input)
        self.assertEqual(len(response.jobs), 0)

    def test_scrape_empty_items_handled(self):
        """
        Verify OracleCloud scraper handles empty items array cleanly.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.ORACLE_CLOUD],
            search_term="NonexistentRole",
            results_wanted=5,
        )
        response = self.scraper.scrape(scraper_input)
        self.assertEqual(len(response.jobs), 0)
