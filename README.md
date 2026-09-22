# LinkedIn Scraper

[![PyPI version](https://badge.fury.io/py/linkedin-scraper.svg)](https://badge.fury.io/py/linkedin-scraper)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Async LinkedIn scraper built with Playwright for extracting profile, company, and job data from LinkedIn.

## ⚠️ Breaking Changes in v3.0.0

**Version 3.0.0 introduces breaking changes and is NOT backwards compatible with previous versions.**

### What Changed:
- **Playwright instead of Selenium** - Complete rewrite using Playwright for better performance and reliability
- **Async/await throughout** - All methods are now async and require `await`
- **New package structure** - Imports have changed (e.g., `from linkedin_scraper import PersonScraper`)
- **Updated data models** - Using Pydantic models instead of simple objects
- **Different API** - Method signatures and return types have changed

### Migration Guide:

**Before (v2.x with Selenium):**
```python
from linkedin_scraper import Person

person = Person("https://linkedin.com/in/username", driver=driver)
print(person.name)
```

**After (v3.0+ with Playwright):**
```python
import asyncio
from linkedin_scraper import BrowserManager, PersonScraper

async def main():
    async with BrowserManager() as browser:
        await browser.load_session("session.json")
        scraper = PersonScraper(browser.page)
        person = await scraper.scrape("https://linkedin.com/in/username")
        print(person.name)

asyncio.run(main())
```

**If you need the old Selenium-based version:**
```bash
pip install linkedin-scraper==2.11.2
```
## Quick start (CLI)

```bash
pip install -e ".[dev]"
playwright install chromium

# One-time: create an authenticated session (opens a browser)
linkedin-scraper login

# Scrape
linkedin-scraper person https://www.linkedin.com/in/williamhgates/
linkedin-scraper company https://www.linkedin.com/company/microsoft/
linkedin-scraper jobs --keywords "software engineer" --location "Toronto" --limit 5
linkedin-scraper posts https://www.linkedin.com/company/microsoft/ --limit 10

# Optional: write JSON to a file
linkedin-scraper person https://www.linkedin.com/in/williamhgates/ -o person.json
```

You can also run `python -m linkedin_scraper ...` with the same arguments.

---

## Features

- **Person Profiles** - Scrape comprehensive profile information
  - Basic info (name, location, about, open-to-work)
  - Work experience with details
  - Education history
  - Interests, accomplishments, and contacts
  
- **Company Pages** - Extract company information
  - Company overview and details
  - Industry and size
  - Headquarters location
  
- **Company Posts** - Scrape posts from company pages
  - Post content and text
  - Reactions, comments, reposts counts
  - Posted date and images
  
- **Job Listings** - Scrape job postings
  - Job details and requirements
  - Company information
  - Application links

- **Async/Await** - Modern async Python with Playwright
- **Type Safety** - Full Pydantic models for all data
- **Progress Callbacks** - Track scraping progress
- **Session Management** - Reuse authenticated sessions

## Installation

```bash
pip install linkedin-scraper
```

### Install Playwright browsers:

```bash
playwright install chromium
```

## Quick Start

### CLI

```bash
linkedin-scraper login
linkedin-scraper person https://linkedin.com/in/username -o out.json
```

### Python library

```python
import asyncio
from linkedin_scraper import BrowserManager, PersonScraper

async def main():
    # Initialize browser
    async with BrowserManager(headless=False) as browser:
        # Load authenticated session
        await browser.load_session("linkedin_session.json")
        
        # Create scraper
        scraper = PersonScraper(browser.page)
        
        # Scrape a profile
        person = await scraper.scrape("https://linkedin.com/in/williamhgates/")
        
        # Access data
        print(f"Name: {person.name}")
        print(f"Location: {person.location}")
        print(f"About: {(person.about or '')[:200]}")
        print(f"Experiences: {len(person.experiences)}")
        print(f"Education: {len(person.educations)}")

asyncio.run(main())
```

### Company Scraping

```python
from linkedin_scraper import CompanyScraper

async def scrape_company():
    async with BrowserManager(headless=False) as browser:
        await browser.load_session("session.json")
        
        scraper = CompanyScraper(browser.page)
        company = await scraper.scrape("https://linkedin.com/company/microsoft/")
        
        print(f"Company: {company.name}")
        print(f"Industry: {company.industry}")
        print(f"Size: {company.company_size}")
        print(f"About: {company.about_us[:200]}...")

asyncio.run(scrape_company())
```

### Job Scraping

```python
from linkedin_scraper import BrowserManager, JobScraper, JobSearchScraper

async def search_jobs():
    async with BrowserManager(headless=False) as browser:
        await browser.load_session("session.json")
        
        search_scraper = JobSearchScraper(browser.page)
        job_urls = await search_scraper.search(
            keywords="Python Developer",
            location="San Francisco",
            limit=10
        )
        
        job_scraper = JobScraper(browser.page)
        for url in job_urls:
            job = await job_scraper.scrape(url)
            print(f"{job.job_title} at {job.company}")
            print(f"Location: {job.location}")
            print(f"Link: {job.linkedin_url}")
            print("---")

async def search_jobs_facade():
    from linkedin_scraper import LinkedInSearchFacade
    from linkedin_scraper.search.queries import JobSearchQuery

    async with BrowserManager(headless=False) as browser:
        await browser.load_session("session.json")
        facade = LinkedInSearchFacade(browser.browser_port)
        page = await facade.search_jobs(JobSearchQuery(keywords="Python", limit=5))
        for item in page.items:
            print(f"{item.job_title} at {item.company} - {item.linkedin_url}")

asyncio.run(search_jobs())
```

### Company Posts Scraping

```python
from linkedin_scraper import BrowserManager, CompanyPostsScraper

async def scrape_company_posts():
    async with BrowserManager(headless=False) as browser:
        await browser.load_session("session.json")
        
        scraper = CompanyPostsScraper(browser.page)
        posts = await scraper.scrape(
            "https://linkedin.com/company/microsoft/",
            limit=10
        )
        
        for post in posts:
            print(f"Posted: {post.posted_date}")
            print(f"Text: {post.text[:200]}...")
            print(f"Reactions: {post.reactions_count}")
            print(f"Comments: {post.comments_count}")
            print(f"URL: {post.linkedin_url}")
            print("---")

asyncio.run(scrape_company_posts())
```

## Authentication

LinkedIn requires authentication. Create a session once:

### Option 1: CLI (recommended)

```bash
linkedin-scraper login
# saves linkedin_session.json in the current directory
```

### Option 2: Manual login in Python

```python
import asyncio
from linkedin_scraper import BrowserManager, wait_for_manual_login

async def create_session():
    async with BrowserManager(headless=False) as browser:
        await browser.page.goto("https://www.linkedin.com/login")
        print("Please log in to LinkedIn...")
        await wait_for_manual_login(browser.page, timeout=300000)
        await browser.save_session("linkedin_session.json")
        print("Session saved!")

asyncio.run(create_session())
```

### Option 3: Programmatic Login

```python
from linkedin_scraper import BrowserManager, login_with_credentials
import os

async def login():
    async with BrowserManager(headless=False) as browser:
        # Login with credentials
        await login_with_credentials(
            browser.page,
            email=os.getenv("LINKEDIN_EMAIL"),
            password=os.getenv("LINKEDIN_PASSWORD")
        )
        
        # Save session for reuse
        await browser.save_session("session.json")

asyncio.run(login())
```

## Progress Tracking

Track scraping progress with callbacks:

```python
from linkedin_scraper import ConsoleCallback, PersonScraper

async def scrape_with_progress():
    callback = ConsoleCallback()  # Prints progress to console
    
    async with BrowserManager(headless=False) as browser:
        await browser.load_session("session.json")
        
        scraper = PersonScraper(browser.page, callback=callback)
        person = await scraper.scrape("https://linkedin.com/in/williamhgates/")

asyncio.run(scrape_with_progress())
```

### Custom Callbacks

```python
from linkedin_scraper import ProgressCallback

class MyCallback(ProgressCallback):
    async def on_start(self, scraper_type: str, url: str):
        print(f"Starting {scraper_type} scraping: {url}")
    
    async def on_progress(self, message: str, percent: int):
        print(f"[{percent}%] {message}")
    
    async def on_complete(self, scraper_type: str, url: str):
        print(f"Completed {scraper_type}: {url}")
    
    async def on_error(self, error: Exception):
        print(f"Error: {error}")
```

## Data Models

All scraped data is returned as Pydantic models:

### Person

```python
class Person(BaseModel):
    linkedin_url: str
    name: Optional[str]
    location: Optional[str]
    about: Optional[str]
    open_to_work: bool
    experiences: List[Experience]
    educations: List[Education]
    interests: List[Interest]
    accomplishments: List[Accomplishment]
    contacts: List[Contact]
```

### Company

```python
class Company(BaseModel):
    linkedin_url: str
    name: Optional[str]
    about_us: Optional[str]
    website: Optional[str]
    headquarters: Optional[str]
    founded: Optional[str]
    industry: Optional[str]
    company_type: Optional[str]
    company_size: Optional[str]
    specialties: Optional[str]
    # Reserved (not yet populated by CompanyScraper):
    # headcount, showcase_pages, affiliated_companies, employees
```

### Job

```python
class Job(BaseModel):
    linkedin_url: str
    job_title: Optional[str]
    company: Optional[str]
    company_linkedin_url: Optional[str]
    location: Optional[str]
    posted_date: Optional[str]
    applicant_count: Optional[str]
    job_description: Optional[str]
    benefits: Optional[str]
```

### Post

```python
class Post(BaseModel):
    linkedin_url: Optional[str]
    urn: Optional[str]
    text: Optional[str]
    posted_date: Optional[str]
    reactions_count: Optional[int]
    comments_count: Optional[int]
    reposts_count: Optional[int]
    image_urls: List[str]
```

## Advanced Usage

### Browser Configuration

```python
browser = BrowserManager(
    headless=False,  # Show browser window
    slow_mo=100,     # Slow down operations (ms)
    viewport={"width": 1920, "height": 1080},
    user_agent="Custom User Agent"
)
```

### Error Handling

```python
from linkedin_scraper import (
    AuthenticationError,
    RateLimitError,
    ScrapingError,
)

try:
    person = await scraper.scrape(url)
except AuthenticationError:
    print("Not logged in - session expired")
except RateLimitError:
    print("Rate limited by LinkedIn")
except ScrapingError as e:
    print(f"Scraping failed: {e}")
```

## Best Practices

1. **Rate Limiting** - Add delays between requests
   ```python
   import asyncio
   await asyncio.sleep(2)  # 2 second delay
   ```

2. **Session Reuse** - Save and reuse sessions to avoid frequent logins

3. **Error Handling** - Always handle exceptions (rate limits, auth errors, etc.)

4. **Headless Mode** - Use `headless=False` during development, `True` for production

5. **Respect LinkedIn** - Don't scrape aggressively, respect rate limits

## Requirements

- Python 3.8+
- Playwright
- Pydantic 2.0+
- python-dotenv (optional, for credentials)

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is for educational purposes only. Make sure to comply with LinkedIn's Terms of Service and use responsibly. The authors are not responsible for any misuse of this tool.

## Links

- [GitHub Repository](https://github.com/joeyism/linkedin_scraper)
- [Issue Tracker](https://github.com/joeyism/linkedin_scraper/issues)
- [PyPI Package](https://pypi.org/project/linkedin-scraper/)
