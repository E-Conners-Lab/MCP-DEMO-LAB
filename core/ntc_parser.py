"""NTC Templates integration for structured CLI parsing.

Thin wrapper around ntc-templates that provides graceful degradation
when the library is not installed.
"""

import logging

logger = logging.getLogger(__name__)

_NTC_AVAILABLE = False
try:
    from ntc_templates.parse import parse_output as _ntc_parse
    _NTC_AVAILABLE = True
except ImportError:
    logger.info("ntc-templates not installed — structured parsing unavailable")


def is_available() -> bool:
    """Return True if ntc-templates is installed."""
    return _NTC_AVAILABLE


def parse(platform: str, command: str, data: str) -> list[dict]:
    """Parse CLI output using ntc-templates.

    Args:
        platform: NTC platform (e.g. ``cisco_ios``)
        command: The command that produced the output
        data: Raw CLI output text

    Returns:
        List of parsed dicts, or empty list on failure

    Raises:
        ImportError: If ntc-templates is not installed
    """
    if not _NTC_AVAILABLE:
        raise ImportError(
            "NTC Templates is not installed. "
            "Install with: pip install ntc-templates"
        )
    try:
        result = _ntc_parse(platform=platform, command=command, data=data)
        return result if result else []
    except Exception as exc:
        logger.warning("NTC parse failed for '%s' on %s: %s", command, platform, exc)
        return []
