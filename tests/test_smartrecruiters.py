import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.smartrecruiters import SmartRecruiters

class TestSmartRecruitersScraper(unittest.TestCase):
    """
    Unit tests for the SmartRecruiters direct jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = SmartRecruiters()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from SmartRecruiters API
        """
        json_data = {
            "content": [
                {
                    "id": "sr-123",
                    "name": "Staff Engineer",
                    "releasedDate": "2026-07-20T00:00:00.000Z",
                    "location": {
                        "city": "London",
                        "country": "GB"
                    }
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        
        detail_response = Mock()
        detail_response.status_code = 200
        detail_response.json.return_value = {
            "jobAd": {
                "sections": {
                    "jobDescription": {
                        "text": "<p>Write python...</p>"
                    }
                }
            }
        }
        
        self.mock_session.get.side_effect = [mock_response, detail_response]

        scraper_input = ScraperInput(
            site_type=[Site.SMARTRECRUITERS],
            search_term="visa",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "sr-123")
        self.assertEqual(job.title, "Staff Engineer")
        self.assertEqual(job.company_name, "Visa")
        self.assertEqual(job.job_url, "https://jobs.smartrecruiters.com/visa/sr-123")
        self.assertEqual(job.location.display_location(), "London, GB")
        self.assertIn("Write python", job.description)
