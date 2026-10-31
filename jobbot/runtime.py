"""Primijeni postavke iz prikvačene poruke na filtre u ovom procesu."""
from . import config
from .settings_store import Settings

# Snimka onoga što je proces učitao iz env/zadanog, prije naredbi.
ENV_ROLES = list(config.ROLE_KEYWORDS)
ENV_CITIES = list(config.ONSITE_CITIES)


def apply(settings: Settings):
    from . import ranking
    config.ROLE_KEYWORDS = list(settings.role_keywords) if settings.role_keywords is not None else list(ENV_ROLES)
    config.ONSITE_CITIES = list(settings.onsite_cities) if settings.onsite_cities is not None else list(ENV_CITIES)
    ranking.refresh_filters()
