import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.cryptojobs import CryptoJobs

class TestCryptoJobsScraper(unittest.TestCase):
    """
    Unit tests for the Crypto Jobs List jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = CryptoJobs()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Crypto Jobs List RSS
        """
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Solidity Auditor at OpenZeppelin</title>
                    <link>https://cryptojobslist.com/jobs/openzeppelin-solidity-auditor</link>
                    <description>Auditing smart contracts...</description>
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
            site_type=[Site.CRYPTO_JOBS],
            search_term="Solidity",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.title, "Solidity Auditor")
        self.assertEqual(job.company_name, "OpenZeppelin")
        self.assertEqual(job.job_url, "https://cryptojobslist.com/jobs/openzeppelin-solidity-auditor")
        self.assertEqual(job.location.display_location(), "Worldwide")
        self.assertIn("Auditing smart", job.description)
