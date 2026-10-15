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
        self.assertEqual(job.location.display_location(), "Bengaluru, IND")

    def test_scrape_null_jobs_handled(self):
        """
        Verify that Amazon scraper gracefully handles null jobs key in response without TypeError.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jobs": None}
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.AMAZON],
            search_term="Software",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        self.assertEqual(len(response.jobs), 0)

    def test_scrape_india_country_mapping(self):
        """
        Verify that Amazon scraper correctly maps India location to country=IND in target URL.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jobs": []}
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.AMAZON],
            search_term="Software Engineer",
            location="India",
            results_wanted=10,
        )
        self.scraper.scrape(scraper_input)

        called_url = self.mock_session.get.call_args[0][0]
        self.assertIn("country=IND", called_url)
        self.assertTrue("base_query=Software+Engineer" in called_url or "base_query=Software Engineer" in called_url)


    def test_scrape_remote_query_mapping(self):
        """
        Verify that Amazon scraper appends remote keyword when is_remote is requested.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jobs": []}
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.AMAZON],
            search_term="Backend Developer",
            is_remote=True,
            results_wanted=10,
        )
        self.scraper.scrape(scraper_input)

        called_url = self.mock_session.get.call_args[0][0]
        self.assertIn("remote", called_url.lower())

