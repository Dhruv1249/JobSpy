import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.levelsfyi import LevelsFyi

class TestLevelsFyiScraper(unittest.TestCase):
    """
    Unit tests for the Levels.fyi jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = LevelsFyi()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Levels.fyi API
        """
        json_data = {
            "jobs": [
                {
                    "id": "levels-404",
                    "title": "Database Engineer",
                    "companyName": "Cockroach Labs",
                    "link": "https://www.levels.fyi/jobs/levels-404",
                    "location": "New York, NY",
                    "description": "Distributed SQL database..."
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.LEVELSFYI],
            search_term="Database",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "levels-404")
        self.assertEqual(job.title, "Database Engineer")
        self.assertEqual(job.company_name, "Cockroach Labs")
        self.assertEqual(job.job_url, "https://www.levels.fyi/jobs/levels-404")
        self.assertEqual(job.location.display_location(), "New York, NY")
        self.assertIn("Distributed SQL", job.description)
