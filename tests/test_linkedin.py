import unittest
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
from jobspy.linkedin import LinkedIn
from jobspy.model import DescriptionFormat, ScraperInput, Site


class TestLinkedInScraper(unittest.TestCase):
    """
    Unit test suite validating search ingestion, detail retrieval, HTML selector fallbacks, and anti-bot redirect handling for LinkedIn scraper.
    """

    def setUp(self):
        self.mock_session = Mock()
        self.scraper = LinkedIn()
        self.scraper.session = self.mock_session

    def test_scrape_without_fetching_description(self):
        """
        Verify that search cards are parsed and job details are not requested when linkedin_fetch_description is False.
        """
        search_html = """
        <div>
            <div class="base-search-card">
                <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/software-engineer-101?trk=public_jobs"></a>
                <span class="sr-only">Software Engineer</span>
                <h4 class="base-search-card__subtitle">
                    <a href="https://www.linkedin.com/company/acme">Acme Corp</a>
                </h4>
                <div class="base-search-card__metadata">
                    <span class="job-search-card__location">Bengaluru, Karnataka, India</span>
                    <time class="job-search-card__listdate" datetime="2026-07-20">2026-07-20</time>
                </div>
            </div>
        </div>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = search_html
        self.mock_session.get.return_value = mock_response

        scraper_input = ScraperInput(
            site_type=[Site.LINKEDIN],
            search_term="Software Engineer",
            results_wanted=1,
            linkedin_fetch_description=False,
        )
        response = self.scraper.scrape(scraper_input)

        self.assertEqual(len(response.jobs), 1)
        job_result = response.jobs[0]
        self.assertEqual(job_result.id, "li-101")
        self.assertEqual(job_result.title, "Software Engineer")
        self.assertEqual(job_result.company_name, "Acme Corp")
        self.assertEqual(job_result.location.city, "Bengaluru")
        self.assertIsNone(job_result.description)
        self.assertEqual(self.mock_session.get.call_count, 1)

    def test_scrape_with_fetching_description_markup_selector(self):
        """
        Verify that full job description is retrieved using the show-more-less-html__markup selector when enabled.
        """
        search_html = """
        <div>
            <div class="base-search-card">
                <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/backend-developer-202"></a>
                <span class="sr-only">Backend Developer</span>
                <h4 class="base-search-card__subtitle">
                    <a>Stripe</a>
                </h4>
                <div class="base-search-card__metadata">
                    <span class="job-search-card__location">Remote</span>
                </div>
            </div>
        </div>
        """
        detail_html = """
        <html>
            <body>
                <div class="show-more-less-html__markup">
                    <p>We are looking for an experienced Golang and Python backend developer.</p>
                </div>
            </body>
        </html>
        """
        mock_search_response = Mock()
        mock_search_response.status_code = 200
        mock_search_response.text = search_html

        mock_detail_response = Mock()
        mock_detail_response.status_code = 200
        mock_detail_response.text = detail_html
        mock_detail_response.url = "https://www.linkedin.com/jobs/view/202"

        self.mock_session.get.side_effect = [mock_search_response, mock_detail_response]

        scraper_input = ScraperInput(
            site_type=[Site.LINKEDIN],
            search_term="Backend Developer",
            results_wanted=1,
            linkedin_fetch_description=True,
            description_format=DescriptionFormat.MARKDOWN,
        )
        response = self.scraper.scrape(scraper_input)

        self.assertEqual(len(response.jobs), 1)
        job_result = response.jobs[0]
        self.assertIsNotNone(job_result.description)
        self.assertIn("Golang and Python backend developer", job_result.description)
        self.assertEqual(self.mock_session.get.call_count, 2)

    def test_get_job_details_description_text_selector_with_buttons(self):
        """
        Verify that description__text selector extracts content while removing show-more-less buttons.
        """
        detail_html = """
        <html>
            <body>
                <div class="description__text description__text--rich">
                    <p>Primary duties include distributed systems design and microservices implementation.</p>
                    <button class="show-more-less-html__button show-more-less-button">Show more</button>
                    <button class="show-more-less-html__button--less">Show less</button>
                </div>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = detail_html
        mock_response.url = "https://www.linkedin.com/jobs/view/303"
        self.mock_session.get.return_value = mock_response

        self.scraper.scraper_input = ScraperInput(
            site_type=[Site.LINKEDIN],
            search_term="Engineer",
            results_wanted=1,
            description_format=DescriptionFormat.MARKDOWN,
        )
        job_details = self.scraper._get_job_details("303")

        self.assertIn("distributed systems design", job_details["description"])
        self.assertNotIn("Show more", job_details["description"])
        self.assertNotIn("Show less", job_details["description"])

    def test_get_job_details_redirect_authwall_returns_empty(self):
        """
        Verify that redirects to authwall or signup return an empty dictionary.
        """
        blocked_urls = [
            "https://www.linkedin.com/authwall?trk=rip",
            "https://www.linkedin.com/signup/cold-join",
            "https://www.linkedin.com/checkpoint/challenge",
            "https://www.linkedin.com/jobs/search?trk=expired_jd_redirect",
        ]
        for blocked_url in blocked_urls:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Redirected</body></html>"
            mock_response.url = blocked_url
            self.mock_session.get.return_value = mock_response

            self.scraper.scraper_input = ScraperInput(
                site_type=[Site.LINKEDIN],
                search_term="Engineer",
                results_wanted=1,
            )
            job_details = self.scraper._get_job_details("404")
            self.assertEqual(job_details, {})

    def test_get_job_details_http_error_returns_empty(self):
        """
        Verify that network timeouts or HTTP failure status codes return an empty dictionary safely.
        """
        self.mock_session.get.side_effect = Exception("Connection timed out")

        self.scraper.scraper_input = ScraperInput(
            site_type=[Site.LINKEDIN],
            search_term="Engineer",
            results_wanted=1,
        )
        job_details = self.scraper._get_job_details("500")
        self.assertEqual(job_details, {})
