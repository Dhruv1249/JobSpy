import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.dice import Dice

class TestDiceScraper(unittest.TestCase):
    """
    Unit tests for the Dice jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Dice()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Dice API
        """
        html_data = """
        <html>
            <body>
                <div class="card">
                    <a href="/job-detail/dice-101?query=Architect" class="card-title-link">Cloud Architect</a>
                    <div class="company-name">Datadog</div>
                    <div class="location">Remote</div>
                    <div class="card-description">Building observability...</div>
                </div>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_data
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.DICE],
            search_term="Architect",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "dice-101")
        self.assertEqual(job.title, "Cloud Architect")
        self.assertEqual(job.company_name, "Datadog")
        self.assertEqual(job.job_url, "https://www.dice.com/job-detail/dice-101?query=Architect")
        self.assertEqual(job.location.display_location(), "Remote")
        self.assertIn("Building observability", job.description)
