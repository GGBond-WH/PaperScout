"""
Configuration module for OpenReview Paper Filtering Tool.
Contains venue mappings and application settings.
"""

from typing import Dict, List, Optional

# ============================================================================
# VENUE MAPPINGS
# Maps user-friendly conference names to OpenReview venue/group ID patterns.
# Patterns use {year} as placeholder for the year.
# Some conferences have multiple possible patterns due to naming changes.
# ============================================================================

VENUE_MAPPINGS: Dict[str, Dict] = {
    "ICLR": {
        "display_name": "ICLR",
        "aliases": ["iclr"],
        "patterns": [
            "ICLR.cc/{year}/Conference",
        ],
        "years_available": list(range(2018, 2027)),
    },
    "NeurIPS": {
        "display_name": "NeurIPS",
        "aliases": ["neurips", "nips", "NIPS"],
        "patterns": [
            "NeurIPS.cc/{year}/Conference",
            "NIPS.cc/{year}/Conference",  # Older naming
        ],
        "years_available": list(range(2019, 2027)),
    },
    "ICML": {
        "display_name": "ICML",
        "aliases": ["icml"],
        "patterns": [
            "ICML.cc/{year}/Conference",
        ],
        "years_available": list(range(2023, 2027)),
    },
    "AAAI": {
        "display_name": "AAAI",
        "aliases": ["aaai"],
        "patterns": [
            "AAAI.org/{year}/Conference",
        ],
        "years_available": list(range(2021, 2026)), # Supported via web (2021-2025)
        "source": "web",
    },
}

# Fields that may contain review scores (in order of priority)
SCORE_FIELD_NAMES: List[str] = [
    "rating",
    "recommendation",
    "score",
    "soundness",
    "overall",
    "Overall",
    "Rating",
    "Recommendation",
    "Overall Recommendation",
    "overall_recommendation",
]

# Fields that may contain reviewer confidence
CONFIDENCE_FIELD_NAMES: List[str] = [
    "confidence",
    "Confidence",
]

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================

# Cache settings
CACHE_TTL_HOURS = 6

# Display settings
DEFAULT_PAGE_SIZE = 50
MAX_DISPLAY_RESULTS = 500

# API settings
API_RETRY_MAX = 3
API_RETRY_DELAY_BASE = 2  # seconds, exponential backoff

# Year range
MIN_YEAR = 2018
MAX_YEAR = 2026


def get_venue_id_candidates(venue_name: str, year: int) -> List[str]:
    """
    Get all possible OpenReview venue IDs for a given venue name and year.
    
    Args:
        venue_name: Conference name (case-insensitive, aliases supported)
        year: The year to query
        
    Returns:
        List of possible venue ID strings to try
    """
    # Normalize venue name
    venue_upper = venue_name.upper().strip()
    
    # Find matching venue config
    for key, config in VENUE_MAPPINGS.items():
        if venue_upper == key.upper() or venue_name.lower() in [a.lower() for a in config["aliases"]]:
            return [p.format(year=year) for p in config["patterns"]]
    
    # If not found in mappings, return the name as-is (custom venue)
    return [venue_name]


def get_available_venues() -> List[str]:
    """Get list of all available venue names for the UI dropdown."""
    return list(VENUE_MAPPINGS.keys())


def get_venue_years(venue_name: str) -> List[int]:
    """Get available years for a specific venue."""
    venue_upper = venue_name.upper().strip()
    
    for key, config in VENUE_MAPPINGS.items():
        if venue_upper == key.upper() or venue_name.lower() in [a.lower() for a in config["aliases"]]:
            return config["years_available"]
    
    # Default range for custom venues
    return list(range(MIN_YEAR, MAX_YEAR + 1))


def normalize_venue_name(venue_name: str) -> Optional[str]:
    """
    Normalize venue name to canonical form.
    Returns None if venue not found in mappings.
    """
    venue_lower = venue_name.lower().strip()
    
    for key, config in VENUE_MAPPINGS.items():
        if venue_lower == key.lower() or venue_lower in [a.lower() for a in config["aliases"]]:
            return key
    
    return None
