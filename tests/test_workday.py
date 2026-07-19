import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.workday import Workday

class TestWorkdayScraper(unittest.TestCase):
    """
    Unit tests for the Workday direct jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Workday()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Workday cxs API
        """
        json_data = {
            "jobPostings": [
                {
                    "title": "Principal Engineer",
                    "externalPath": "/salesforce/job/Principal-Engineer_JR123",
                    "locationsText": "Boston, MA",
                    "postedOn": "2026-07-20"
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        
        detail_response = Mock()
        detail_response.status_code = 200
        detail_response.json.return_value = {
            "jobPostingInfo": {
                "id": "JR123",
                "jobDescription": "<p>Write java...</p>"
            }
        }
        
        self.mock_session.post.return_value = mock_response
        self.mock_session.get.return_value = detail_response

        scraper_input = ScraperInput(
            site_type=[Site.WORKDAY],
            search_term="salesforce",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "JR123")
        self.assertEqual(job.title, "Principal Engineer")
        self.assertEqual(job.company_name, "Salesforce")
        self.assertEqual(job.job_url, "https://salesforce.wd5.myworkdaysite.com/en-US/salesforce/details/JR123")
        self.assertEqual(job.location.display_location(), "Boston, MA")
        self.assertIn("Write java", job.description)
