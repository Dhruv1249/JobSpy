import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.wellfound import Wellfound

class TestWellfoundScraper(unittest.TestCase):
    """
    Unit tests for the Wellfound jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Wellfound()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Wellfound HTML
        """
        html_content = """<html>
            <body>
                <div class="styles_component">
                    <a class="styles_title" href="/jobs/123-frontend-engineer">Frontend Engineer</a>
                    <h2 class="styles_name">Vercel</h2>
                    <span class="styles_location">Remote</span>
                    <div class="styles_description">Building Next.js...</div>
                </div>
            </body>
        </html>"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.WELLFOUND],
            search_term="Frontend",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.title, "Frontend Engineer")
        self.assertEqual(job.company_name, "Vercel")
        self.assertEqual(job.job_url, "https://wellfound.com/jobs/123-frontend-engineer")
        self.assertEqual(job.location.display_location(), "Remote")
        self.assertIn("Building Next.js", job.description)
