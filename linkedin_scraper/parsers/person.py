"""Pure, browser-independent parsing logic for LinkedIn person profiles."""

from __future__ import annotations

import re
from typing import Sequence

from ..models import Accomplishment, Contact, Education, Experience, Interest
from .person_links import (
    classify_link,
    contact_type_from_heading,
    merge_contacts,
    profile_detail_url,
    unwrap_href,
)

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
DATE_RANGE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})\b"
    r".*(?:\s[-\u2013\u2014]\s|\s-\s)"
)
DEGREE_KEYWORDS = (
    "bachelor",
    "master",
    "doctor",
    "phd",
    "ph.d",
    "mba",
    "b.tech",
    "btech",
    "m.tech",
    "mtech",
    "b.s",
    "b.a",
    "m.s",
    "m.sc",
    "degree",
    "diploma",
)
EDUCATION_METADATA_PREFIXES = (
    "grade:",
    "skills:",
    "activities:",
    "activities and societies:",
)
UI_LINES = {
    "Show all experiences",
    "Show all education",
    "Show more",
    "See more",
}
EMPLOYMENT_TYPE_MARKERS = (
    "full-time",
    "part-time",
    "internship",
    "contract",
    "self-employed",
    "freelance",
    "apprenticeship",
    "seasonal",
    "temporary",
)
JOB_TITLE_HINTS = (
    "ceo",
    "chairman",
    "chair",
    "president",
    "founder",
    "co-founder",
    "director",
    "manager",
    "engineer",
    "developer",
    "intern",
    "officer",
    "lead",
    "head of",
    "vice president",
    "vp ",
    "consultant",
    "analyst",
    "scientist",
    "architect",
    "specialist",
    "researcher",
)

SECTION_HEADINGS = {
    "About",
    "Featured",
    "Activity",
    "Experience",
    "Education",
    "Skills",
    "Interests",
    "Analytics",
    "Explore Premium profiles",
    "People also viewed",
    "Ad Options",
}


def clean_lines(text: str) -> list[str]:
    """Return stripped, non-empty lines without adjacent duplicates."""
    result: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line and (not result or result[-1] != line):
            result.append(line)
    return result


def section_lines(text: str, header: str, stop_headers: set[str]) -> list[str]:
    """Return section lines, or an empty list when the heading is absent."""
    lines = clean_lines(text)
    try:
        start = lines.index(header) + 1
    except ValueError:
        return []

    result = []
    for line in lines[start:]:
        if line in stop_headers or line.startswith("LinkedIn Corporation"):
            break
        if line not in UI_LINES:
            result.append(line)
    return result


def parse_work_times(
    work_times: str,
) -> tuple[str | None, str | None, str | None]:
    """Split a LinkedIn work date range and duration."""
    if not work_times:
        return None, None, None
    parts = work_times.split("·")
    times = parts[0].strip()
    duration = parts[1].strip() if len(parts) > 1 else None
    normalized = re.sub(r"\s*[-\u2013\u2014]\s*", " - ", times)
    date_parts = normalized.split(" - ", 1)
    return (
        date_parts[0].strip() or None,
        date_parts[1].strip() if len(date_parts) > 1 else None,
        duration,
    )


def parse_education_times(times: str) -> tuple[str | None, str | None]:
    """Extract one or two years from an education date line."""
    years = YEAR_RE.findall(times or "")
    if len(years) >= 2:
        return years[0], years[1]
    if len(years) == 1:
        return years[0], years[0]
    return None, None


def looks_like_date_line(line: str) -> bool:
    return bool(YEAR_RE.search(line)) and (
        any(separator in line for separator in ("-", "–", "—"))
        or line.strip().isdigit()
    )


def looks_like_degree(line: str) -> bool:
    lower = line.lower()
    return any(keyword in lower for keyword in DEGREE_KEYWORDS)


def is_education_metadata(line: str) -> bool:
    lower = line.lower()
    return any(lower.startswith(prefix) for prefix in EDUCATION_METADATA_PREFIXES)


def is_valid_institution(line: str) -> bool:
    return bool(
        line
        and not is_education_metadata(line)
        and not looks_like_date_line(line)
        and not (looks_like_degree(line) and len(line) < 120)
    )


def _is_duration_only(line: str) -> bool:
    lower = line.lower()
    return bool(re.search(r"\b\d+\s+(?:yr|yrs|mo|mos)\b", lower)) and not bool(
        YEAR_RE.search(line)
    )


def _has_employment_type(line: str) -> bool:
    lower = line.lower()
    return " · " in line or any(marker in lower for marker in EMPLOYMENT_TYPE_MARKERS)


def _looks_like_job_title(line: str) -> bool:
    lower = line.lower()
    return any(hint in lower for hint in JOB_TITLE_HINTS)


def _single_role_title_and_company(
    lines: Sequence[str], date_index: int
) -> tuple[str, str]:
    """
    Resolve title/company for a single-role card.

    LinkedIn emits both:
    - Title, Company · type, Dates
    - Company, Title, Dates
    - Company, Title · type, Dates (company logo/name first)
    """
    before = lines[date_index - 1] if date_index >= 1 else ""
    before2 = lines[date_index - 2] if date_index >= 2 else ""
    if not before:
        return before2, ""

    before_name = before.split(" · ", 1)[0]
    before2_name = before2.split(" · ", 1)[0] if before2 else ""

    if _has_employment_type(before) and before2:
        if _looks_like_job_title(before_name) and not _looks_like_job_title(
            before2_name
        ):
            return before_name, before2_name
        return before2_name, before_name

    if (
        before2
        and _looks_like_job_title(before_name)
        and not _looks_like_job_title(before2_name)
    ):
        return before_name, before2_name

    if before2:
        return before2_name, before_name
    return before_name, ""


def parse_experience_lines(
    lines: Sequence[str], linkedin_url: str | None = None
) -> list[Experience]:
    """Parse one experience card, including grouped roles."""
    lines = [line for line in lines if line not in UI_LINES]
    date_indexes = [
        index for index, line in enumerate(lines) if DATE_RANGE_RE.search(line)
    ]
    if not date_indexes:
        return []

    is_grouped = len(date_indexes) > 1 or (
        date_indexes[0] >= 3 and _is_duration_only(lines[1])
    )
    if is_grouped:
        title_indexes = [max(0, index - 1) for index in date_indexes]
    else:
        title_indexes = [max(0, date_indexes[0] - 2)]
    grouped_company = None
    if is_grouped and title_indexes[0] >= 2:
        candidate = lines[0]
        if not DATE_RANGE_RE.search(candidate) and not _is_duration_only(candidate):
            grouped_company = candidate.split(" · ", 1)[0]

    experiences = []
    for role_index, date_index in enumerate(date_indexes):
        title_index = title_indexes[role_index]
        if grouped_company:
            title = lines[title_index]
            company = grouped_company
        elif is_grouped:
            title = lines[title_index]
            company_line = lines[title_index - 1] if title_index > 0 else ""
            if company_line and not _is_duration_only(company_line):
                company = company_line.split(" · ", 1)[0]
            else:
                company = lines[0].split(" · ", 1)[0] if lines else ""
        else:
            title, company = _single_role_title_and_company(lines, date_index)

        next_title = (
            title_indexes[role_index + 1]
            if role_index + 1 < len(title_indexes)
            else len(lines)
        )
        trailing = list(lines[date_index + 1 : next_title])
        location = None
        if trailing and not _is_duration_only(trailing[0]):
            location = trailing.pop(0).split(" · ", 1)[0]
        description = "\n".join(trailing).strip() or None
        from_date, to_date, duration = parse_work_times(lines[date_index])

        if title:
            experiences.append(
                Experience(
                    position_title=title,
                    institution_name=company or None,
                    linkedin_url=linkedin_url,
                    from_date=from_date,
                    to_date=to_date,
                    duration=duration,
                    location=location,
                    description=description,
                )
            )
    return experiences


def parse_experiences_text(text: str) -> list[Experience]:
    """Fallback parser for captured detail-page text."""
    lines = section_lines(
        text,
        "Experience",
        {
            "Education",
            "More profiles for you",
            "People also viewed",
            "LinkedIn Corporation",
            "Footer",
        },
    )
    date_indexes = [
        index for index, line in enumerate(lines) if DATE_RANGE_RE.search(line)
    ]
    experiences: list[Experience] = []
    for index, date_index in enumerate(date_indexes):
        if date_index < 2:
            continue
        next_date = (
            date_indexes[index + 1] if index + 1 < len(date_indexes) else len(lines)
        )
        end = next_date - 2 if next_date - 2 > date_index else next_date
        end = max(end, date_index + 1)
        chunk = lines[date_index - 2 : end]
        experiences.extend(parse_experience_lines(chunk))
    return experiences


def parse_education_lines(
    lines: Sequence[str], linkedin_url: str | None = None
) -> Education | None:
    """Parse one education card while retaining metadata as description."""
    lines = [line for line in lines if line not in UI_LINES]
    if not lines:
        return None
    institution = lines[0]
    if not is_valid_institution(institution):
        return None

    degree = None
    from_date = to_date = None
    description_lines = []
    for line in lines[1:]:
        if looks_like_date_line(line) and from_date is None:
            from_date, to_date = parse_education_times(line)
        elif degree is None and looks_like_degree(line):
            degree = line
        else:
            description_lines.append(line)
    return Education(
        institution_name=institution,
        degree=degree,
        linkedin_url=linkedin_url,
        from_date=from_date,
        to_date=to_date,
        description="\n".join(description_lines).strip() or None,
    )


def parse_educations_text(text: str) -> list[Education]:
    """Fallback parser for captured detail-page text."""
    lines = section_lines(
        text,
        "Education",
        {
            "More profiles for you",
            "People also viewed",
            "LinkedIn Corporation",
            "Footer",
        },
    )
    educations = []
    index = 0
    while index < len(lines):
        if not is_valid_institution(lines[index]):
            index += 1
            continue
        end = index + 1
        while end < len(lines):
            if (
                is_valid_institution(lines[end])
                and not looks_like_degree(lines[end])
                and not is_education_metadata(lines[end])
            ):
                break
            end += 1
        education = parse_education_lines(lines[index:end])
        if education:
            educations.append(education)
        index = end
    return educations



def location_from_header_lines(text: str, name: str) -> str | None:
    """
    Location sits after name/(pronouns)/headline and before Contact info.
    Taking the last header line avoids picking suggested-profile headlines.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header: list[str] = []
    past_name = False
    for line in lines:
        if not past_name:
            if line == name:
                past_name = True
            continue
        lower = line.lower()
        if "contact info" in lower or "contact-info" in lower:
            clean_part = line.split("·")[0].split("•")[0].strip()
            if clean_part and clean_part.lower() not in ("contact info", "contact-info", "contact"):
                header.append(clean_part)
            break
        if (
            lower.startswith("contact")
            or "follower" in lower
            or "connection" in lower
        ):
            break
        if line in {"·", "•"}:
            continue
        if (
            "/" in line
            and len(line) <= 20
            and any(p in line for p in ("Him", "Her", "Them"))
        ):
            continue
        header.append(line)
    if not header:
        return None
    return header[-1]


def parse_name_and_location(
    h1_text: str | None, h2_texts: Sequence[str], main_text: str | None
) -> tuple[str | None, str | None]:
    """Parse name and location from raw text elements."""
    name = (h1_text or "").strip()
    if not name:
        for txt in h2_texts:
            txt_clean = (txt or "").strip()
            if (
                txt_clean
                and txt_clean not in SECTION_HEADINGS
                and "notification" not in txt_clean.lower()
            ):
                name = txt_clean
                break

    location = None
    if name and main_text:
        location = location_from_header_lines(main_text, name)

    return name if name else None, location


def parse_open_to_work(img_title: str | None) -> bool:
    """Determine open_to_work status from img title attribute."""
    if not img_title:
        return False
    return "#OPEN_TO_WORK" in img_title.upper()


def parse_about_section(section_texts: Sequence[str]) -> str | None:
    """Parse about text from section texts."""
    for txt in section_texts:
        lines = [line.strip() for line in (txt or "").splitlines() if line.strip()]
        if not lines or lines[0] != "About":
            continue
        body = []
        for line in lines[1:]:
            if line in SECTION_HEADINGS or line in {"… more", "... more"}:
                break
            body.append(line)
        if body:
            return "\n".join(body).strip()
    return None


def parse_accomplishment_item(
    spans: Sequence[str], credential_url: str | None, category: str
) -> Accomplishment | None:
    """Parse raw text spans and credential URL into an Accomplishment model."""
    title = ""
    issuer = ""
    issued_date = ""
    credential_id = ""

    for i, text in enumerate(spans[:5]):
        if not text:
            continue
        text = text.strip()
        if len(text) > 500:
            continue

        if i == 0:
            title = text
        elif "Issued by" in text:
            parts = text.split("·")
            issuer = parts[0].replace("Issued by", "").strip()
            if len(parts) > 1:
                issued_date = parts[1].strip()
        elif "Issued " in text and not issued_date:
            issued_date = text.replace("Issued ", "")
        elif "Credential ID" in text:
            credential_id = text.replace("Credential ID ", "")
        elif i == 1 and not issuer:
            issuer = text
        elif (
            any(
                month in text
                for month in [
                    "Jan",
                    "Feb",
                    "Mar",
                    "Apr",
                    "May",
                    "Jun",
                    "Jul",
                    "Aug",
                    "Sep",
                    "Oct",
                    "Nov",
                    "Dec",
                ]
            )
            and not issued_date
        ):
            if "·" in text:
                parts = text.split("·")
                issued_date = parts[0].strip()
            else:
                issued_date = text

    if not title or len(title) > 200:
        return None

    return Accomplishment(
        category=category,
        title=title,
        issuer=issuer if issuer else None,
        issued_date=issued_date if issued_date else None,
        credential_id=credential_id if credential_id else None,
        credential_url=credential_url,
    )


def map_interest_tab_to_category(tab_name: str) -> str:
    """Map interest tab heading to normalized category."""
    tab_lower = tab_name.lower()
    if "compan" in tab_lower:
        return "company"
    elif "group" in tab_lower:
        return "group"
    elif "school" in tab_lower:
        return "school"
    elif "newsletter" in tab_lower:
        return "newsletter"
    elif "voice" in tab_lower or "influencer" in tab_lower:
        return "influencer"
    else:
        return tab_lower


def parse_interest_item(
    unique_texts: Sequence[str], href: str | None, category: str
) -> Interest | None:
    """Parse interest item text and URL into Interest model."""
    name = unique_texts[0] if unique_texts else None
    if name and href:
        return Interest(
            name=name,
            category=category,
            linkedin_url=href,
        )
    return None


def parse_contact_dialog_heading_and_links(
    heading_text: str,
    link_items: Sequence[tuple[str, str, str | None]],
    plain_container_text: str | None,
) -> list[Contact]:
    """Parse contact info section heading, links, or plain text into Contact objects."""
    contacts: list[Contact] = []
    contact_type = contact_type_from_heading(heading_text)
    if not contact_type:
        return contacts

    if link_items:
        for raw_href, text, label in link_items:
            if not raw_href:
                continue
            href = unwrap_href(raw_href)
            if href.startswith("mailto:"):
                value = href[7:]
            elif href.startswith("tel:"):
                value = href[4:]
            elif contact_type in {"linkedin", "website", "twitter"}:
                value = href
            else:
                value = text or href

            if contact_type == "website":
                contacts.append(classify_link(value, label))
            else:
                contacts.append(
                    Contact(
                        type=contact_type,
                        value=value,
                        label=label,
                    )
                )
    elif plain_container_text:
        lines = [
            line.strip()
            for line in plain_container_text.splitlines()
            if line.strip() and line.strip().lower() != heading_text.lower()
        ]
        plain_value = "\n".join(lines).strip() or None
        if plain_value:
            contacts.append(Contact(type=contact_type, value=plain_value))

    return contacts


# Direct canonical exports
parse_experiences = parse_experience_lines
parse_educations = parse_education_lines
parse_accomplishments = parse_accomplishment_item
parse_interests = parse_interest_item
parse_contacts = parse_contact_dialog_heading_and_links
parse_person_profile = parse_name_and_location

# Re-export pure link/contact helpers
__all__ = [
    "clean_lines",
    "section_lines",
    "parse_work_times",
    "parse_education_times",
    "looks_like_date_line",
    "looks_like_degree",
    "is_education_metadata",
    "is_valid_institution",
    "parse_experience_lines",
    "parse_experiences_text",
    "parse_education_lines",
    "parse_educations_text",
    "location_from_header_lines",
    "parse_name_and_location",
    "parse_open_to_work",
    "parse_about_section",
    "parse_accomplishment_item",
    "map_interest_tab_to_category",
    "parse_interest_item",
    "parse_contact_dialog_heading_and_links",
    "parse_experiences",
    "parse_educations",
    "parse_accomplishments",
    "parse_interests",
    "parse_contacts",
    "parse_person_profile",
    "classify_link",
    "contact_type_from_heading",
    "merge_contacts",
    "profile_detail_url",
    "unwrap_href",
]

