import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.builtin import BuiltIn

class TestBuiltInScraper(unittest.TestCase):
    """
    Unit tests for the BuiltIn jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = BuiltIn()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from BuiltIn HTML
        """
        html_content = """<html>
            <body>
                <div class="job-card">
                    <a class="job-title" href="/job/devops-engineer/101">DevOps Engineer</a>
                    <div class="company-name">Docker</div>
                    <div class="job-location">San Francisco, CA</div>
                    <div class="job-description">Containerization infrastructure...</div>
                </div>
            </body>
        </html>"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.BUILTIN],
            search_term="DevOps",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.title, "DevOps Engineer")
        self.assertEqual(job.company_name, "Docker")
        self.assertEqual(job.job_url, "https://builtin.com/job/devops-engineer/101")
        self.assertEqual(job.location.display_location(), "San Francisco, CA")
        self.assertIn("Containerization", job.description)
