"""Centralized CSS selector registry for all LinkedIn UI coupling.

Hexagonal architecture note
---------------------------
Every CSS selector, ARIA query, or UI-marker string the library depends on
lives in this single module. Scrapers, extractors, adapters, and core helpers
MUST import selectors from here instead of hard-coding them.

When LinkedIn changes its UI, this file is the *only* place that needs to be
updated for Python-side selectors. JavaScript extraction bodies in
``adapters/search`` embed their selectors inline (Playwright ``evaluate``
cannot reference Python constants), but their entry-point card selectors are
sourced from here so adapters stay consistent.

Selectors are grouped by surface area and documented with what they target.
Prefer resilient selectors (data attributes, ARIA roles, href fragments) over
obfuscated class names where possible; keep legacy class selectors as fallbacks
in tuples/lists so callers can try them in order.
"""

from __future__ import annotations


class Page:
    """Generic page-structure selectors."""

    MAIN = "main"
    ARTICLE = "article"
    SECTION = "section"
    H1 = "h1"
    H2 = "h2"


class Auth:
    """Login form and authenticated-shell markers."""

    LOGIN_USERNAME = "#username"
    LOGIN_PASSWORD = "#password"
    LOGIN_SUBMIT = 'button[type="submit"]'
    #: Elements that only render for authenticated sessions.
    NAV_MARKERS = (
        '.global-nav__primary-link, [data-control-name="nav.settings"], '
        'nav a[href*="/feed"], .global-nav, #global-nav, nav a[href*="/mynetwork"]'
    )


class RateLimit:
    """Rate-limit / security-challenge detection selectors."""

    CAPTCHA = 'iframe[title*="captcha" i], iframe[src*="captcha" i], div[class*="captcha" i]'
    BANNERS = (
        '[data-testid="rate-limit-banner"]',
        ".rate-limit-message",
        ".artdeco-toast-item--error",
        ".artdeco-banner--error",
        '[class*="rate-limit"]',
        '[class*="rateLimit"]',
    )


class PageActions:
    """Progressive-disclosure and overlay controls."""

    SEE_MORE_BUTTONS = (
        'button:has-text("See more"), button:has-text("Show more"), '
        'button:has-text("show all")'
    )
    MODAL_DISMISS = (
        'button[aria-label="Dismiss"], button[aria-label="Close"], '
        "button.artdeco-modal__dismiss"
    )


class PersonProfile:
    """Person profile page and detail-page selectors."""

    # Generic page-structure aliases for profile pages
    MAIN = Page.MAIN
    SECTION = Page.SECTION
    H1 = Page.H1
    H2 = Page.H2
    #: Shared card selector for profile detail lists (experience, education, ...).
    COMPONENT_ITEMS = (
        'main [data-view-name="profile-component-entity"], '
        "main .pvs-list__paged-list-item"
    )
    OPEN_TO_WORK_IMAGE = ".pv-top-card-profile-picture img"
    NOTHING_TO_SEE = 'text="Nothing to see for now"'
    ENTITY = 'div[data-view-name="profile-component-entity"]'
    HIDDEN_SPAN = 'span[aria-hidden="true"]'
    CREDENTIAL_LINK = 'a[href*="credential"], a[href*="verify"]'
    #: Accomplishment/skill list items (most-specific first).
    DETAIL_LIST_ITEMS = (
        ".pvs-list__container .pvs-list__paged-list-item, "
        "main ul .pvs-list__paged-list-item, "
        "main ol .pvs-list__paged-list-item, "
        ".pvs-list__container > li, "
        "main ul > li, "
        "main ol > li"
    )
    # Interests tab strip
    TABS = '[role="tab"], tab'
    TAB_PANELS = '[role="tabpanel"], tabpanel'
    INTEREST_ITEMS = "li, listitem, .pvs-list__paged-list-item"
    INTEREST_TEXT_SPANS = 'span[aria-hidden="true"], div > span'
    # Contact-info dialog
    CONTACT_DIALOG_WAIT = "main, [role='dialog']"
    CONTACT_DIALOG = 'dialog, [role="dialog"]'
    CONTACT_SECTION = "section"
    CONTACT_HEADING = "h3"
    CONTACT_LINK = "a[href]"
    CONTACT_LABEL_SPANS = "span, generic"
    MAIN_ANCHORS = "main a[href]"


class Company:
    """Company page selectors."""

    NAME_HEADINGS = "main h2, h2"
    OVERVIEW_INFO_ITEM = ".org-top-card-summary-info-list__info-item"
    DEFINITION_LIST = "dl"
    DEFINITION_TERM = "dt"
    DEFINITION_VALUE = "dd"
    ALL_ANCHORS = "a"


class Job:
    """Job posting page selectors."""

    TOP_CARD_CONTAINERS = (
        ".job-details-jobs-unified-top-card__primary-description-container",
        ".job-details-jobs-unified-top-card__primary-description",
        ".jobs-unified-top-card__subtitle-primary-grouping",
        ".jobs-unified-top-card__metadata-container",
    )
    DESCRIPTION_CONTENT = (
        ".jobs-description__content, .jobs-box__html-content, #job-details"
    )
    MAIN_TEXT_BLOCKS = "main span, main div"
    TEXT_BLOCKS = "span, div"


class SearchCards:
    """Entry-point card selectors for the search adapters (per entity)."""

    PERSON_CARD = 'a[href*="/in/"]'
    COMPANY_CARD = 'a[href*="/company/"]'
    JOB_CARD = 'a[href*="/jobs/view/"]'
    POST_CARD = 'a[href*="/feed/update/"], a[href*="/posts/"]'
    EMPLOYEE_CARD = PERSON_CARD

    PERSON_URL_MARKERS = ("/in/",)
    COMPANY_URL_MARKERS = ("/company/",)
    JOB_URL_MARKERS = ("/jobs/view/",)
    POST_URL_MARKERS = ("/feed/update/", "/posts/")
    EMPLOYEE_URL_MARKERS = PERSON_URL_MARKERS
