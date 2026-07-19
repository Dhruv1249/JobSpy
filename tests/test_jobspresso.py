import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.jobspresso import Jobspresso

class TestJobspressoScraper(unittest.TestCase):
    """
    Unit tests for the Jobspresso jobspy scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = Jobspresso()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape fetches and parses jobs correctly from Jobspresso RSS
        """
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Backend Developer @ Supabase (Remote)</title>
                    <link>https://jobspresso.co/job/backend-developer-supabase-remote/</link>
                    <description>Writing Go and Postgres...</description>
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
            site_type=[Site.JOBSPRESSO],
            search_term="Developer",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)
        
        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.title, "Backend Developer")
        self.assertEqual(job.company_name, "Supabase")
        self.assertEqual(job.job_url, "https://jobspresso.co/job/backend-developer-supabase-remote/")
        self.assertEqual(job.location.display_location(), "Remote")
        self.assertIn("Writing Go", job.description)
