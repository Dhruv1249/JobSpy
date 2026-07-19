import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.weworkremotely import WeWorkRemotely

class TestWeWorkRemotelyScraper(unittest.TestCase):
    """
    Unit tests for the We Work Remotely scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = WeWorkRemotely()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses RSS feed correctly
        """
        rss_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>We Work Remotely</title>
            <item>
              <title><![CDATA[Linear: Backend Engineer]]></title>
              <link>https://weworkremotely.com/remote-jobs/123</link>
              <pubDate>Sun, 19 Jul 2026 12:00:00 +0000</pubDate>
              <description><![CDATA[<p>We are hiring a backend engineer...</p>]]></description>
            </item>
          </channel>
        </rss>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = rss_content.encode("utf-8")
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.WEWORKREMOTELY],
            search_term="Backend",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)

        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.title, "Backend Engineer")
        self.assertEqual(job.company_name, "Linear")
        self.assertEqual(job.job_url, "https://weworkremotely.com/remote-jobs/123")
        self.assertIn("We are hiring a backend engineer", job.description)
