import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.cord import Cord

class TestCordScraper(unittest.TestCase):
    """
    Unit tests for the cord.co jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Cord()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from cord.co HTML
        """
        html_content = """<html>
            <body>
                <div class="job-card">
                    <h3><a href="/job/505-backend-engineer">Backend Engineer</a></h3>
                    <span class="company">Canonical</span>
                    <span class="location">Remote</span>
                    <p>Building Ubuntu cloud services...</p>
                </div>
            </body>
        </html>"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.CORD],
            search_term="Backend",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.title, "Backend Engineer")
        self.assertEqual(job.company_name, "Canonical")
        self.assertEqual(job.job_url, "https://cord.co/job/505-backend-engineer")
        self.assertEqual(job.location.display_location(), "Remote")
        self.assertIn("Ubuntu cloud", job.description)
