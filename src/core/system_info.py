"""
System Info utilities for timezone and approximate location detection.
Uses local system settings for time zone and public IP geolocation for location.
"""

from datetime import datetime
import time
import os
from typing import Optional, Tuple, Dict

import requests

from .logger import setup_logger

logger = setup_logger("SystemInfo")


def _safe_get_timezone_local() -> str:
    """Get local timezone name using stdlib fallbacks."""
    try:
        # Prefer IANA-style if available through datetime
        tzinfo = datetime.now().astimezone().tzinfo
        name = tzinfo.tzname(datetime.now()) if tzinfo else None
        if name:
            return name
    except Exception:
        pass

    try:
        # Windows-style or generic names
        tn = time.tzname
        if isinstance(tn, tuple) and len(tn) > 0 and tn[0]:
            return tn[0]
    except Exception:
        pass

    return "Unknown"


def _query_ipapi() -> Optional[Dict]:
    """Query ipapi.co for location data."""
    try:
        resp = requests.get("https://ipapi.co/json/", timeout=3)
        if resp.ok:
            return resp.json()
    except Exception as e:
        logger.debug(f"ipapi.co query failed: {e}")
    return None


def _query_ipapi_alt() -> Optional[Dict]:
    """Query ip-api.com as a fallback for location data."""
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=3)
        if resp.ok:
            return resp.json()
    except Exception as e:
        logger.debug(f"ip-api.com query failed: {e}")
    return None


def get_timezone() -> str:
    """Return the local timezone display name."""
    return _safe_get_timezone_local()


def get_location() -> Tuple[str, str]:
    """Return (city, country) based on public IP geolocation. Fallbacks to (Unknown, Unknown)."""
    data = _query_ipapi()
    if not data:
        data = _query_ipapi_alt()

    try:
        if data:
            # ipapi.co fields
            city = data.get("city") or data.get("regionName") or "Unknown"
            country = data.get("country_name") or data.get("country") or "Unknown"
            return city, country
    except Exception as e:
        logger.debug(f"Failed to parse location data: {e}")

    return "Unknown", "Unknown"


def get_info_text() -> str:
    """Return a compact footer text: Timezone and Location."""
    tz = get_timezone()
    city, country = get_location()
    return f"Timezone: {tz} | Location: {city}, {country}"