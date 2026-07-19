import unittest
from unittest.mock import Mock, patch
from jobspy.model import ScraperInput, Site
from jobspy.hn_hiring import HNHiring

class TestHNHiringScraper(unittest.TestCase):
    """
    Unit tests for the Hacker News Who's Hiring scraper
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = HNHiring()
        self.scraper.session = self.mock_session

    def test_scrape_success(self):
        """
        Verify scrape finds monthly thread and parses comments correctly
        """
        mock_story_response = Mock()
        mock_story_response.status_code = 200
        mock_story_response.json.return_value = {
            "hits": [
                {
                    "objectID": "999999",
                    "title": "Ask HN: Who is hiring? (July 2026)"
                }
            ]
        }

        mock_comments_response = Mock()
        mock_comments_response.status_code = 200
        mock_comments_response.json.return_value = {
            "hits": [
                {
                    "objectID": "888888",
                    "created_at": "2026-07-19T20:00:00Z",
                    "author": "john_doe",
                    "comment_text": "Notion | Software Engineer | SF | Full-time<br><br>We are hiring engineers..."
                }
            ]
        }

        self.mock_session.get.side_effect = [mock_story_response, mock_comments_response]

        scraper_input = ScraperInput(
            site_type=[Site.HN_HIRING],
            search_term="Engineer",
            results_wanted=1
        )
        response = self.scraper.scrape(scraper_input)

        self.assertEqual(len(response.jobs), 1)
        job = response.jobs[0]
        self.assertEqual(job.id, "888888")
        self.assertEqual(job.title, "Software Engineer")
        self.assertEqual(job.company_name, "Notion")
        self.assertEqual(job.job_url, "https://news.ycombinator.com/item?id=888888")
        self.assertIn("We are hiring engineers", job.description)
