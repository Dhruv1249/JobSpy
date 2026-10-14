"""
Unit tests for the GoogleCareers JobSpy scraper.
"""

import unittest
from unittest.mock import Mock

from jobspy.google_careers import GoogleCareers
from jobspy.model import ScraperInput, Site


class TestGoogleCareersScraper(unittest.TestCase):
    """
    Unit test suite validating GoogleCareers HTML extraction, parsing, and resilience.
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = GoogleCareers()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify GoogleCareers scraper parses job cards correctly from search results HTML.
        """
        sample_html = """
        <html>
            <body>
                <ul>
                    <li>
                        <a href="jobs/results/123456789-software-engineer-cloud?q=software">
                            <h3 class="QJPWVe">Software Engineer III, Cloud Infrastructure</h3>
                        </a>
                        <span class="r0wTof">Bengaluru, Karnataka, India</span>
                        <span class="wVSTAb">Mid</span>
                        <p>Work on scalable distributed infrastructure systems.</p>
                    </li>
                </ul>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = sample_html
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.GOOGLE_CAREERS],
            search_term="software engineer",
            location="India",
            results_wanted=5,
        )
        response = self.scraper.scrape(scraper_input)

        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "123456789")
        self.assertEqual(job.title, "Software Engineer III, Cloud Infrastructure")
        self.assertEqual(job.company_name, "Google")
        self.assertIn("Bengaluru", job.location.country)
        self.assertIn("123456789-software-engineer-cloud", job.job_url)

    def test_scrape_http_failure_handled(self):
        """
        Verify GoogleCareers scraper returns empty job list when HTTP request returns non-200.
        """
        mock_response = Mock()
        mock_response.status_code = 500
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.GOOGLE_CAREERS],
            search_term="software",
            results_wanted=5,
        )
        response = self.scraper.scrape(scraper_input)
        self.assertEqual(len(response.jobs), 0)

    def test_scrape_exception_handled(self):
        """
        Verify GoogleCareers scraper handles network exceptions gracefully without crashing.
        """
        self.mock_session.get.side_effect = RuntimeError("Network timeout")

        scraper_input = ScraperInput(
            site_type=[Site.GOOGLE_CAREERS],
            search_term="software",
            results_wanted=5,
        )
        response = self.scraper.scrape(scraper_input)
        self.assertEqual(len(response.jobs), 0)

    def test_scrape_skips_non_job_links(self):
        """
        Verify GoogleCareers scraper skips sign-in and non-job cards.
        """
        sample_html = """
        <html>
            <body>
                <ul>
                    <li>
                        <a href="https://accounts.google.com/ServiceLogin">
                            <h3>Sign in</h3>
                        </a>
                    </li>
                    <li>
                        <a href="jobs/results/999-ai-researcher">
                            <h3 class="QJPWVe">AI Research Scientist</h3>
                        </a>
                        <span class="r0wTof">Mountain View, CA, USA</span>
                    </li>
                </ul>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = sample_html
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.GOOGLE_CAREERS],
            search_term="research",
            results_wanted=5,
        )
        response = self.scraper.scrape(scraper_input)
        self.assertEqual(len(response.jobs), 1)
        self.assertEqual(response.jobs[0].title, "AI Research Scientist")
