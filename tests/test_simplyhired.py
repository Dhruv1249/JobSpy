import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.simplyhired import SimplyHired

class TestSimplyHiredScraper(unittest.TestCase):
    """
    Unit tests for the SimplyHired jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = SimplyHired()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from SimplyHired HTML
        """
        html_content = """<html>
            <body>
                <ul>
                    <li class="SerpJob">
                        <a class="job-link" href="/job/fullstack-developer/202">Fullstack Developer</a>
                        <span class="job-company">Sourcegraph</span>
                        <span class="job-location">Remote</span>
                        <p class="job-snippet">Code intelligence platform...</p>
                    </li>
                </ul>
            </body>
        </html>"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.SIMPLYHIRED],
            search_term="Fullstack",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.title, "Fullstack Developer")
        self.assertEqual(job.company_name, "Sourcegraph")
        self.assertEqual(job.job_url, "https://www.simplyhired.com/job/fullstack-developer/202")
        self.assertEqual(job.location.display_location(), "Remote")
        self.assertIn("Code intelligence", job.description)
