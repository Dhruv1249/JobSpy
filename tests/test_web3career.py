import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.web3career import Web3Career

class TestWeb3CareerScraper(unittest.TestCase):
    """
    Unit tests for the Web3 Career jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Web3Career()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Web3 Career RSS
        """
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Protocol Engineer at Flashbots</title>
                    <link>https://web3.career/jobs/flashbots-protocol-engineer</link>
                    <description>Working on MEV research...</description>
                    <pubDate>Mon, 20 Jul 2026 00:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = xml_content.encode("utf-8")
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.WEB3_CAREER],
            search_term="Engineer",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.title, "Protocol Engineer")
        self.assertEqual(job.company_name, "Flashbots")
        self.assertEqual(job.job_url, "https://web3.career/jobs/flashbots-protocol-engineer")
        self.assertEqual(job.location.display_location(), "Worldwide")
        self.assertIn("MEV research", job.description)
