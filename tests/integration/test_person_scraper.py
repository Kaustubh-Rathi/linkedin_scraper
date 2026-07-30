"""Live LinkedIn integration tests for PersonScraper."""
import pytest
from linkedin_scraper import PersonScraper
from linkedin_scraper.models import Person


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_basic(browser_with_session, test_profile_urls, silent_callback):
    """Test basic person scraping functionality."""
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape(test_profile_urls["bill_gates"])

    assert isinstance(person, Person)
    assert person.name == "Bill Gates"
    assert person.linkedin_url == test_profile_urls["bill_gates"]
    assert person.location is not None
    assert len(person.experiences) > 0
    assert len(person.educations) > 0


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_experiences(browser_with_session, test_profile_urls, silent_callback):
    """Test experience extraction."""
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape(test_profile_urls["satya_nadella"])

    assert len(person.experiences) > 0

    # Check first experience has required fields
    exp = person.experiences[0]
    assert exp.position_title is not None or exp.institution_name is not None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_education(browser_with_session, test_profile_urls, silent_callback):
    """Test education extraction."""
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape(test_profile_urls["bill_gates"])

    assert len(person.educations) > 0
    edu = person.educations[0]
    assert edu.institution_name is not None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_complex_profile(browser_with_session, test_profile_urls, silent_callback):
    """Test scraping a complex profile with many experiences."""
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape(test_profile_urls["reid_hoffman"])

    # Reid Hoffman has many experiences
    assert len(person.experiences) > 10
    assert person.name == "Reid Hoffman"
    assert person.about is not None
