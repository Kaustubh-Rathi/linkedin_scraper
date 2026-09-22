"""Allow ``python -m linkedin_scraper`` to invoke the CLI."""

from .cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
