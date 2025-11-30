# scrapers/__init__.py
# Expose the site-specific scrapers registry for app.py to import.

from .site_specific import SITE_SCRAPERS

__all__ = ["SITE_SCRAPERS"]
