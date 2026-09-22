import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from linkedin_scraper import BrowserManager, PersonScraper
from linkedin_scraper.callbacks import SilentCallback

SESSION_FILE = Path(__file__).resolve().parent.parent / "linkedin_session.json"
PROFILE_URL = "https://www.linkedin.com/in/kaustubh-rathi-9228ab255/"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "kaustubh_profile.json"


def format_person(person):
    lines = [
        "=== PROFILE EXTRACTION RESULT ===",
        f"URL: {person.linkedin_url}",
        f"Name: {person.name}",
        f"Location: {person.location}",
        f"About: {(person.about or 'N/A')[:200]}",
        f"Open to work: {person.open_to_work}",
        f"Experiences: {len(person.experiences)}",
        f"Educations: {len(person.educations)}",
        f"Interests: {len(person.interests)}",
        f"Accomplishments: {len(person.accomplishments)}",
        f"Contacts: {len(person.contacts)}",
        "",
        "--- EXPERIENCES ---",
    ]
    for exp in person.experiences:
        lines.append(
            f"  - {exp.position_title or 'N/A'} at {exp.institution_name or 'N/A'} ({exp.from_date or 'N/A'} - {exp.to_date or 'N/A'})"
        )
    lines.append("--- EDUCATIONS ---")
    for edu in person.educations:
        lines.append(
            f"  - {edu.degree or 'N/A'} from {edu.institution_name or 'N/A'} ({edu.from_date or 'N/A'} - {edu.to_date or 'N/A'})"
        )
    lines.append("--- INTERESTS ---")
    for interest in person.interests:
        lines.append(f"  - [{interest.category}] {interest.name}")
    lines.append("--- ACCOMPLISHMENTS ---")
    for acc in person.accomplishments:
        lines.append(f"  - [{acc.category}] {acc.title} ({acc.issuer or 'N/A'})")
    lines.append("--- CONTACTS ---")
    for contact in person.contacts:
        lines.append(f"  - [{contact.type}] {contact.value} ({contact.label or 'N/A'})")
    lines.append("--- MISSING SECTIONS ---")
    lines.append("  - Skills: NOT extracted (no skills field in Person model)")
    lines.append("  - Languages: extracted only within accomplishments")
    lines.append("  - Volunteer work: merged into experiences")
    lines.append("  - Featured section: not extracted")
    lines.append("=================================")
    return "\n".join(lines)


async def main():
    if not SESSION_FILE.exists():
        print("ERROR: Session file not found", file=sys.stderr)
        sys.exit(1)

    async with BrowserManager(headless=False) as browser:
        await browser.load_session(str(SESSION_FILE))
        scraper = PersonScraper(browser.browser_port, callback=SilentCallback())
        person = await scraper.scrape(PROFILE_URL)

        output = format_person(person)
        print(output)
        OUTPUT_FILE.write_text(json.dumps(person.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
