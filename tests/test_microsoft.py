import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.microsoft import Microsoft

class TestMicrosoftScraper(unittest.TestCase):
    """
    Unit tests for the Microsoft jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Microsoft()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Microsoft Careers API
        """
        json_data = {
            "operationResult": {
                "result": {
                    "jobs": [
                        {
                            "jobId": "msft-888",
                            "title": "Software Engineer II",
                            "properties": {
                                "primaryLocation": "Hyderabad, India",
                                "description": "Building Azure Platform Services..."
                            }
                        }
                    ]
                }
            }
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.MICROSOFT],
            search_term="Software",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "msft-888")
        self.assertEqual(job.title, "Software Engineer II")
        self.assertEqual(job.company_name, "Microsoft")
        self.assertEqual(job.job_url, "https://jobs.careers.microsoft.com/global/en/job/msft-888")
        self.assertEqual(job.location.display_location(), "Hyderabad, India")
