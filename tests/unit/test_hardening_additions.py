"""Tests for hardening additions: throttling, new filters, new person sections."""

import pytest

from linkedin_scraper.adapters.search.url_builder import LinkedInSearchUrlBuilder
from linkedin_scraper.core.rate_limit import RequestThrottler
from linkedin_scraper.models import Person
from linkedin_scraper.models.search_filters import (
    DatePosted,
    JobSearchFilter,
    PersonSearchFilter,
    PostSearchFilter,
    SortBy,
)
from linkedin_scraper.models.search_queries import (
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
)
from linkedin_scraper.parsers.person import parse_headline, parse_skill_name
from linkedin_scraper.scrapers.person.experience import ExperienceExtractor
from linkedin_scraper.scrapers.person.skills import SkillsExtractor
from linkedin_scraper.search.filters import (
    JobSearchFilter as ReExportedJobFilter,
)
from urllib.parse import parse_qs, urlparse


@pytest.mark.unit
@pytest.mark.asyncio
async def test_throttler_serializes_and_spaces_requests():
    throttler = RequestThrottler(min_interval=0.05, jitter=0.0)
    order = []

    import asyncio

    async def worker(i):
        async with throttler:
            order.append(i)

    await asyncio.gather(*[worker(i) for i in range(4)])
    assert len(order) == 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_throttler_enforces_min_interval():
    import asyncio
    import time

    throttler = RequestThrottler(min_interval=0.05, jitter=0.0)
    start = time.monotonic()
    await throttler.acquire()
    await throttler.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.045


@pytest.mark.unit
@pytest.mark.asyncio
async def test_throttler_hourly_budget():
    from linkedin_scraper.core.exceptions import RateLimitError

    throttler = RequestThrottler(min_interval=0.0, max_requests_per_hour=2)
    await throttler.acquire()
    await throttler.acquire()
    with pytest.raises(RateLimitError):
        await throttler.acquire()


def _params(url):
    return parse_qs(urlparse(url).query)


@pytest.mark.unit
def test_person_url_new_text_filters():
    query = PersonSearchQuery(
        keywords="engineer",
        filters=PersonSearchFilter(
            first_name="Ada",
            last_name="Lovelace",
            company="Acme",
            school_name="MIT",
        ),
    )
    params = _params(LinkedInSearchUrlBuilder().build_person_url(query))
    assert params["firstName"] == ["Ada"]
    assert params["lastName"] == ["Lovelace"]
    assert params["company"] == ["Acme"]
    assert params["school"] == ["MIT"]


@pytest.mark.unit
def test_job_url_new_filters():
    query = JobSearchQuery(
        keywords="python",
        filters=JobSearchFilter(
            date_posted=DatePosted.PAST_WEEK,
            sort_by=SortBy.DATE,
            distance=25,
            job_functions=["eng", "it"],
            salary_buckets=["4", "5"],
        ),
    )
    params = _params(LinkedInSearchUrlBuilder().build_job_url(query))
    assert params["sortBy"] == ["DD"]
    assert params["distance"] == ["25"]
    assert params["f_F"] == ["eng,it"]
    assert params["f_SB2"] == ["4,5"]
    assert params["f_TPR"] == ["r604800"]


@pytest.mark.unit
def test_post_url_content_type_filter():
    query = PostSearchQuery(
        keywords="ai",
        filters=PostSearchFilter(content_types=["videos", "documents"]),
    )
    params = _params(LinkedInSearchUrlBuilder().build_post_url(query))
    from urllib.parse import unquote
    assert unquote(params["facet"][0]) == 'contentType=>["videos","documents"]'


@pytest.mark.unit
def test_filters_reexport_is_canonical():
    assert ReExportedJobFilter is JobSearchFilter


@pytest.mark.unit
def test_parse_headline_from_header_lines():
    text = (
        "Ada Lovelace\n"
        "She/Her\n"
        "Pioneer of Computing at Analytical Engine Co.\n"
        "London, England, United Kingdom\n"
        "Contact info\n"
    )
    assert parse_headline(text, "Ada Lovelace") == (
        "Pioneer of Computing at Analytical Engine Co."
    )
    assert parse_headline(text, None) is None
    assert parse_headline(None, "Ada Lovelace") is None


@pytest.mark.unit
def test_parse_skill_name_skips_metadata():
    assert parse_skill_name(["", "Python (Programming Language)"]) == (
        "Python (Programming Language)"
    )
    assert parse_skill_name(["Endorsed by 5 people"]) is None
    assert parse_skill_name(["Show all 9 skills"]) is None
    assert parse_skill_name([]) is None


class _FakeElement:
    def __init__(self, spans):
        self._spans = spans

    async def text_content(self, timeout=None):
        return " ".join(self._spans)

    async def get_attribute(self, name, timeout=None):
        return None

    async def inner_text(self):
        return " ".join(self._spans)

    async def query_selector_all(self, selector):
        if "span" in selector:
            return [_FakeSpan(s) for s in self._spans]
        return []


class _FakeSpan:
    def __init__(self, text):
        self._text = text

    async def text_content(self, timeout=None):
        return self._text


class _FakeBrowser:
    def __init__(self, items):
        self._items = items
        self.urls = []

    @property
    def url(self):
        return self.urls[-1] if self.urls else ""

    async def goto(self, url, wait_until="domcontentloaded", timeout=None):
        self.urls.append(url)

    async def wait_for_selector(self, selector, timeout=None, state=None):
        return None

    async def query_selector_all(self, selector):
        if "pvs-list" in selector or selector.startswith("main "):
            return list(self._items)
        return []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skills_extractor_parses_and_dedupes():
    items = [
        _FakeElement(["Python (Programming Language)"]),
        _FakeElement(["python (programming language)"]),
        _FakeElement(["Show all 9 skills"]),
        _FakeElement(["SQL"]),
    ]
    extractor = SkillsExtractor(_FakeBrowser(items))
    skills = await extractor.get_skills("https://www.linkedin.com/in/ada/")
    assert skills == ["Python (Programming Language)", "SQL"]
    assert extractor.browser.urls[0].endswith("/details/skills/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_volunteer_uses_volunteering_details_url():
    extractor = ExperienceExtractor(_FakeBrowser([]))
    result = await extractor.get_volunteer_experiences(
        "https://www.linkedin.com/in/ada/"
    )
    assert result == []
    assert extractor.browser.urls[0].endswith("/details/volunteering-experiences/")


@pytest.mark.unit
def test_person_model_has_new_fields():
    person = Person(linkedin_url="https://www.linkedin.com/in/ada/")
    assert person.headline is None
    assert person.skills == []
    assert person.volunteer_experiences == []
