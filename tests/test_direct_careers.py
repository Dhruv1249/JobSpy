import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.direct_careers import DirectCareers

class TestDirectCareersScraper(unittest.TestCase):
    """
    Unit tests for the DirectCareers jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = DirectCareers()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses job links directly from company career HTML
        """
        html_content = """<html>
            <body>
                <a href="/jobs/systems-engineer">Systems Engineer</a>
            </body>
        </html>"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.DIRECT_CAREERS],
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertGreaterEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.title, "Systems Engineer")
        self.assertIn("systems-engineer", job.job_url)
