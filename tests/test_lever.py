import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.lever import Lever

class TestLeverScraper(unittest.TestCase):
    """
    Unit tests for the Lever direct jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Lever()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Lever postings API
        """
        json_data = [
            {
                "id": "lever-123",
                "title": "Backend Engineer",
                "hostedUrl": "https://jobs.lever.co/spotify/lever-123",
                "createdAt": 1721415600000,
                "description": "<p>Write Scala...</p>",
                "categories": {"location": "Stockholm"},
                "lists": []
            }
        ]
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.LEVER],
            search_term="spotify",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "lever-123")
        self.assertEqual(job.title, "Backend Engineer")
        self.assertEqual(job.company_name, "Spotify")
        self.assertEqual(job.job_url, "https://jobs.lever.co/spotify/lever-123")
        self.assertEqual(job.location.display_location(), "Stockholm")
        self.assertIn("Write Scala", job.description)
        self.assertIsNotNone(job.date_posted)
