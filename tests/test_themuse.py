import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.themuse import TheMuse

class TestTheMuseScraper(unittest.TestCase):
    """
    Unit tests for The Muse scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = TheMuse()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses job listings correctly from The Muse API
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 777777,
                    "name": "Frontend Developer",
                    "publication_date": "2026-07-19T20:00:00Z",
                    "refs": {
                        "landing_page": "https://www.themuse.com/jobs/ava-labs/frontend-developer"
                    },
                    "locations": [{"name": "Brooklyn, NY"}],
                    "contents": "<div>We are looking for a frontend developer...</div>",
                    "company": {
                        "name": "Ava Labs"
                    }
                }
            ]
        }
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.THE_MUSE],
            search_term="Frontend",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)

        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "777777")
        self.assertEqual(job.title, "Frontend Developer")
        self.assertEqual(job.company_name, "Ava Labs")
        self.assertEqual(job.job_url, "https://www.themuse.com/jobs/ava-labs/frontend-developer")
        self.assertEqual(job.location.display_location(), "Brooklyn, NY")
        self.assertIn("We are looking for a frontend developer", job.description)
