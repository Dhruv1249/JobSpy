import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site, Country
from jobspy.remoteok import RemoteOK

class TestRemoteOKScraper(unittest.TestCase):
    """
    Unit tests for the RemoteOK jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = RemoteOK()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from RemoteOK API
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"legal": "this is a disclaimer, skip this"},
            {
                "id": "12345",
                "epoch": "1721415600",
                "company": "Supabase",
                "position": "Backend Engineer",
                "url": "https://remoteok.com/jobs/12345-backend-engineer",
                "location": "Worldwide",
                "description": "<p>Write Go code...</p>",
                "tags": ["golang", "postgres"]
            }
        ]
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.REMOTEOK],
            search_term="Backend",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "12345")
        self.assertEqual(job.title, "Backend Engineer")
        self.assertEqual(job.company_name, "Supabase")
        self.assertEqual(job.job_url, "https://remoteok.com/jobs/12345-backend-engineer")
        self.assertEqual(job.location.display_location(), "Worldwide")
        self.assertIn("Write Go code", job.description)
