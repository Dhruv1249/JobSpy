import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.ashby import Ashby

class TestAshbyScraper(unittest.TestCase):
    """
    Unit tests for the Ashby direct jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Ashby()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Ashby API
        """
        json_data = {
            "jobs": [
                {
                    "id": "ashby-123",
                    "title": "Software Engineer",
                    "jobUrl": "https://jobs.ashbyhq.com/notion/ashby-123",
                    "location": "New York, NY",
                    "descriptionHtml": "<p>Write React...</p>"
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.ASHBY],
            search_term="notion",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "ashby-123")
        self.assertEqual(job.title, "Software Engineer")
        self.assertEqual(job.company_name, "Notion")
        self.assertEqual(job.job_url, "https://jobs.ashbyhq.com/notion/ashby-123")
        self.assertEqual(job.location.display_location(), "New York, NY")
        self.assertIn("Write React", job.description)
