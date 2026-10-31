"""Primijeni postavke iz prikvačene poruke na filtre u ovom procesu."""
from . import config
from .settings_store import Settings

# Snimka onoga što je proces učitao iz env/zadanog, prije naredbi.
ENV_ROLES = list(config.ROLE_KEYWORDS)
ENV_CITIES = list(config.ONSITE_CITIES)
ENV_EXCLUDE = list(config.EXCLUDE_KEYWORDS)
ENV_ALLOW_REMOTE = config.ALLOW_REMOTE


def apply(settings: Settings):
    from . import ranking
    config.ROLE_KEYWORDS = list(settings.role_keywords) if settings.role_keywords is not None else list(ENV_ROLES)
    config.ONSITE_CITIES = list(settings.onsite_cities) if settings.onsite_cities is not None else list(ENV_CITIES)
    config.EXCLUDE_KEYWORDS = list(settings.exclude_keywords) if settings.exclude_keywords is not None else list(ENV_EXCLUDE)
    config.ALLOW_REMOTE = ENV_ALLOW_REMOTE if settings.allow_remote is None else bool(settings.allow_remote)
    ranking.refresh_filters()
