import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.otta import Otta

class TestOttaScraper(unittest.TestCase):
    """
    Unit tests for the Otta jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Otta()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Otta API
        """
        json_data = {
            "jobs": [
                {
                    "id": "otta-303",
                    "title": "Systems Engineer",
                    "company": {"name": "Fly.io"},
                    "applyUrl": "https://otta.com/jobs/otta-303",
                    "location": "London, UK",
                    "summary": "Distributed cloud platform..."
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.OTTA],
            search_term="Systems",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "otta-303")
        self.assertEqual(job.title, "Systems Engineer")
        self.assertEqual(job.company_name, "Fly.io")
        self.assertEqual(job.job_url, "https://otta.com/jobs/otta-303")
        self.assertEqual(job.location.display_location(), "London, UK")
        self.assertIn("Distributed cloud", job.description)
