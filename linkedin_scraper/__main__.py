"""Allow ``python -m linkedin_scraper`` to invoke the CLI."""

from .cli.main import main

raise SystemExit(main())
