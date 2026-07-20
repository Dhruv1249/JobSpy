import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.dice import Dice

class TestDiceScraper(unittest.TestCase):
    """
    Unit tests for the Dice jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Dice()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Dice API
        """
        json_data = {
            "resultItemList": [
                {
                    "id": "dice-101",
                    "title": "Cloud Architect",
                    "company": "Datadog",
                    "detailUrl": "https://www.dice.com/job/dice-101",
                    "location": "Remote",
                    "snippet": "Building observability..."
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.DICE],
            search_term="Architect",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "dice-101")
        self.assertEqual(job.title, "Cloud Architect")
        self.assertEqual(job.company_name, "Datadog")
        self.assertEqual(job.job_url, "https://www.dice.com/job/dice-101")
        self.assertEqual(job.location.display_location(), "Remote")
        self.assertIn("Building observability", job.description)
