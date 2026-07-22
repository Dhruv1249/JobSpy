import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.amazon import Amazon

class TestAmazonScraper(unittest.TestCase):
    """
    Unit tests for the Amazon jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Amazon()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Amazon Jobs API
        """
        json_data = {
            "jobs": [
                {
                    "id_icims": "amz-999",
                    "title": "Software Development Engineer",
                    "job_path": "/jobs/amz-999/sde-1",
                    "location": "Bengaluru, IND",
                    "description": "Building AWS Cloud Services..."
                }
            ]
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.AMAZON],
            search_term="Software",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "amz-999")
        self.assertEqual(job.title, "Software Development Engineer")
        self.assertEqual(job.company_name, "Amazon")
        self.assertEqual(job.job_url, "https://www.amazon.jobs/jobs/amz-999/sde-1")
        self.assertEqual(job.location.display_location(), "Bengaluru, IND")
