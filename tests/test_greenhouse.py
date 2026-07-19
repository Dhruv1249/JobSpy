import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.greenhouse import Greenhouse

class TestGreenhouseScraper(unittest.TestCase):
    """
    Unit tests for the Greenhouse direct jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Greenhouse()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Greenhouse API
        """
        json_data = {
            "jobs": [
                {
                    "id": 12345,
                    "title": "Software Engineer",
                    "absolute_url": "https://boards.greenhouse.io/stripe/jobs/12345",
                    "location": {"name": "San Francisco, CA"},
                    "content": "<p>Write ruby code...</p>"
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.GREENHOUSE],
            search_term="stripe",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "12345")
        self.assertEqual(job.title, "Software Engineer")
        self.assertEqual(job.company_name, "Stripe")
        self.assertEqual(job.job_url, "https://boards.greenhouse.io/stripe/jobs/12345")
        self.assertEqual(job.location.display_location(), "San Francisco, CA")
        self.assertIn("Write ruby code", job.description)
