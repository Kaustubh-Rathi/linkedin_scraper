"""Unit tests for linkedin_scraper.scrapers.person.links module."""

import pytest

from linkedin_scraper.models import Education, Experience
from linkedin_scraper.scrapers.person.links import (
    attach_organization_urls,
    extract_item_text_and_url,
)


class MockElementForLinks:
    def __init__(self, href=None, text="", children=None):
        self._href = href
        self._text = text
        self._children = children or []

    async def get_attribute(self, name, timeout=2000):
        if name == "href":
            return self._href
        return None

    async def text_content(self, timeout=2000):
        return self._text

    async def inner_text(self):
        return self._text

    async def query_selector_all(self, selector):
        return self._children


class MockBrowserForLinks:
    def __init__(self, elements=None, should_fail=False):
        self._elements = elements or []
        self._should_fail = should_fail

    async def query_selector_all(self, selector):
        if self._should_fail:
            raise RuntimeError("DOM query failed")
        return self._elements


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_item_text_and_url_with_element_port():
    link_el = MockElementForLinks(href="/school/stanford-university/", text="Stanford University")
    item = MockElementForLinks(
        text="Stanford University\nMaster of Science\n2018 - 2020",
        children=[link_el],
    )

    lines, href = await extract_item_text_and_url(item, "/school/")
    assert lines == ["Stanford University", "Master of Science", "2018 - 2020"]
    assert href == "https://www.linkedin.com/school/stanford-university/"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_attach_organization_urls():
    link1 = MockElementForLinks(href="/company/acme-corp/", text="Acme Corp")
    link2 = MockElementForLinks(href="https://www.linkedin.com/company/beta-inc/", text="Beta Inc")

    browser = MockBrowserForLinks(elements=[link1, link2])

    experiences = [
        Experience(institution_name="Acme Corp", position_title="Engineer"),
        Experience(institution_name="Beta Inc", position_title="Manager"),
        Experience(institution_name="Already Set", position_title="Lead", linkedin_url="https://www.linkedin.com/company/preset/"),
        Experience(institution_name=None, position_title="Freelance"),
    ]

    enriched = await attach_organization_urls(browser, experiences, "/company/")
    assert len(enriched) == 4
    assert enriched[0].linkedin_url == "https://www.linkedin.com/company/acme-corp/"
    assert enriched[1].linkedin_url == "https://www.linkedin.com/company/beta-inc/"
    assert enriched[2].linkedin_url == "https://www.linkedin.com/company/preset/"
    assert enriched[3].linkedin_url is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_attach_organization_urls_exception_handled():
    browser = MockBrowserForLinks(should_fail=True)
    educations = [Education(institution_name="Stanford University")]
    res = await attach_organization_urls(browser, educations, "/school/")
    assert res == educations
