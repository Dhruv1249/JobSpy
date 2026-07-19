import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.workingnomads import WorkingNomads

class TestWorkingNomadsScraper(unittest.TestCase):
    """
    Unit tests for the Working Nomads jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = WorkingNomads()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Working Nomads API
        """
        json_data = [
            {
                "id": 99999,
                "title": "DevOps Engineer",
                "company_name": "Chainguard",
                "url": "https://www.workingnomads.com/jobs/99999-devops-engineer",
                "location": "Global",
                "description": "<p>Secure containers...</p>",
                "pub_date": "2026-07-20T00:00:00Z"
            }
        ]
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.WORKING_NOMADS],
            search_term="Chainguard",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "99999")
        self.assertEqual(job.title, "DevOps Engineer")
        self.assertEqual(job.company_name, "Chainguard")
        self.assertEqual(job.job_url, "https://www.workingnomads.com/jobs/99999-devops-engineer")
        self.assertEqual(job.location.display_location(), "Global")
        self.assertIn("Secure containers", job.description)
