"""
OpenReview API Client for Paper Filtering Tool.
Handles API interactions, caching, and retry logic.
FIXED: Uses details=replies to get reviews in batch.
"""

import time
import streamlit as st
from typing import List, Dict, Any, Optional, Callable, Tuple
import openreview
from config import (
    get_venue_id_candidates,
    API_RETRY_MAX,
    API_RETRY_DELAY_BASE,
    CACHE_TTL_HOURS,
)
from parsing import compute_score_stats, parse_score


class OpenReviewClientError(Exception):
    """Custom exception for OpenReview API errors."""
    pass


# Global client cache
_client_cache = {}


def create_client() -> openreview.api.OpenReviewClient:
    """Create cached OpenReview API client."""
    if 'client' in _client_cache:
        return _client_cache['client']
    
    try:
        client = openreview.api.OpenReviewClient(
            baseurl="https://api2.openreview.net"
        )
        _client_cache['client'] = client
        return client
    except Exception:
        client = openreview.Client(
            baseurl="https://api.openreview.net"
        )
        _client_cache['client'] = client
        return client


def retry_with_backoff(
    func: Callable, 
    max_retries: int = API_RETRY_MAX,
    base_delay: float = API_RETRY_DELAY_BASE
) -> Any:
    """Execute a function with exponential backoff retry."""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
    
    raise OpenReviewClientError(f"API failed after {max_retries} attempts: {last_error}")


# Keys that indicate a reply is a review
# Keys that indicate a reply is a review
REVIEW_INDICATOR_KEYS = {
    'rating', 'recommendation', 'soundness', 'contribution', 'summary', 'weaknesses',
    'strengths_and_weaknesses', 'quality', 'clarity', 'significance', 'originality',
    'confidence', 'questions', 'limitations', 'Overall Recommendation',
    'overall_recommendation', # Added for ICML snake_case
}


def is_review_reply(reply: Dict[str, Any]) -> bool:
    """Check if a reply looks like a review."""
    content = reply.get('content', {})
    if not content:
        return False
        
    content_keys = set(content.keys())
    matches = len(content_keys & REVIEW_INDICATOR_KEYS)
    return matches >= 1  # Relaxed from 3 to 1 to ensure we catch reviews with few fields


def extract_scores_from_replies(replies: List[Dict]) -> Dict[str, Any]:
    """Extract scores from reply list, return stats."""
    scores = []
    confidences = []
    review_count = 0
    
    for reply in replies:
        if not is_review_reply(reply):
            continue
            
        review_count += 1
        content = reply.get('content', {})
        
        # Extract rating
        rating = (
            content.get('rating') or 
            content.get('recommendation') or 
            content.get('score') or 
            content.get('Overall Recommendation') or
            content.get('overall_recommendation')
        )
        if rating:
            if isinstance(rating, dict):
                rating = rating.get('value', '')
            score = parse_score(rating)
            if score is not None:
                scores.append(score)
        
        # Extract confidence
        confidence = content.get('confidence')
        if confidence:
            if isinstance(confidence, dict):
                confidence = confidence.get('value', '')
            conf_val = parse_score(confidence)
            if conf_val is not None:
                confidences.append(conf_val)
    
    return {
        "review_count": review_count,
        "scored_review_count": len(scores),
        "scores": scores,
        "confidences": confidences,
        "max_score": max(scores) if scores else None,
        "min_score": min(scores) if scores else None,
        "avg_score": sum(scores) / len(scores) if scores else None,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else None,
    }


@st.cache_data(ttl=CACHE_TTL_HOURS * 3600, show_spinner=False)
def fetch_submissions_with_reviews(venue_id: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Fetch submissions WITH reviews using details=replies.
    For web-sourced venues (e.g. AAAI 2025), delegates to scrape_venue.
    """
    # Web Source Delegation
    import config
    # Check if this venue is configured as 'web' source
    for v_name, v_opts in config.VENUE_MAPPINGS.items():
        if v_opts.get("source") == "web":
            # Loose check: if venue name (AAAI) is in venue_id
            if v_name in venue_id:
                import web_scraper
                return web_scraper.scrape_venue(venue_id), ""

    client = create_client()
    papers = []
    
    try:
        # Fetch with details=replies to get reviews
        notes = retry_with_backoff(
            lambda: list(client.get_all_notes(
                invitation=f"{venue_id}/-/Submission",
                details="replies"
            ))
        )
        
        if not notes:
            # Try alternative patterns
            for pattern in [f"{venue_id}/-/Blind_Submission", f"{venue_id}/-/Paper"]:
                try:
                    notes = retry_with_backoff(
                        lambda p=pattern: list(client.get_all_notes(
                            invitation=p,
                            details="replies"
                        ))
                    )
                    if notes:
                        break
                except Exception:
                    continue
        
        
        # --- V1 API Fallback for legacy conferences (e.g. ICLR 2023) ---
        if not notes:
            print(f"No notes found on V2 for {venue_id}. Trying V1 API...")
            try:
                # Initialize V1 client fallback
                try:
                    v1_client = openreview.Client(baseurl='https://api.openreview.net')
                except AttributeError:
                    import openreview as opr
                    v1_client = opr.Client(baseurl='https://api.openreview.net')

                # Try patterns on V1
                v1_patterns = [
                    f"{venue_id}/-/Submission",
                    f"{venue_id}/-/Blind_Submission",
                    f"{venue_id}/-/Paper"
                ]
                
                for p in v1_patterns:
                    try:
                        # Use tools to iterate all notes if available
                        if hasattr(openreview, 'tools') and hasattr(openreview.tools, 'iterget_notes'):
                            print(f"Using iterget_notes for {p}")
                            iterator = openreview.tools.iterget_notes(v1_client, invitation=p, details='replies')
                            notes = list(iterator)
                        else:
                            # Simple fetch
                            print(f"Using get_notes for {p}")
                            notes = v1_client.get_notes(invitation=p, limit=3000, details='replies')
                            
                        if notes:
                            print(f"Found {len(notes)} notes on V1 with {p}")
                            break
                    except Exception as e:
                        # print(f"V1 attempt failed for {p}: {e}")
                        continue
            except Exception as e:
                print(f"V1 Fallback failed: {e}")

        for note in notes:
            content = note.content if hasattr(note, 'content') else {}
            
            def get_val(key):
                val = content.get(key)
                if isinstance(val, dict) and 'value' in val:
                    return val['value']
                return val
            
            # Extract replies (reviews)
            replies = []
            if hasattr(note, 'details') and note.details:
                replies = note.details.get('replies', [])
            
            # Calculate scores from replies
            score_stats = extract_scores_from_replies(replies)
            
            paper = {
                "id": note.id,
                "forum": note.forum if hasattr(note, 'forum') else note.id,
                "title": get_val("title") or "Untitled",
                "abstract": get_val("abstract") or "",
                "authors": get_val("authors") or [],
                "keywords": get_val("keywords") or [],
                "tldr": get_val("TL;DR") or get_val("tldr") or "",
                "pdf": get_val("pdf") or "",
                "venue_id": venue_id,
                **score_stats,
            }
            
            # Build URLs
            base_url = "https://openreview.net"
            paper["openreview_url"] = f"{base_url}/forum?id={paper['forum']}"
            if paper["pdf"] and not paper["pdf"].startswith("http"):
                paper["pdf_url"] = f"{base_url}{paper['pdf']}"
            else:
                paper["pdf_url"] = paper["pdf"]
            
            papers.append(paper)
        
        reviewed_count = sum(1 for p in papers if p.get("scored_review_count", 0) > 0)
        return papers, f"Fetched {len(papers)} papers ({reviewed_count} with reviews)"
        
    except Exception as e:
        return [], f"Error: {str(e)}"


# Keep the simple fetch for cases where we don't need reviews
@st.cache_data(ttl=CACHE_TTL_HOURS * 3600, show_spinner=False)
def fetch_submissions_cached(venue_id: str) -> Tuple[List[Dict[str, Any]], str]:
    """Fetch submissions only (fast, no reviews)."""
    client = create_client()
    submissions = []
    
    try:
        try:
            notes = retry_with_backoff(
                lambda: list(client.get_all_notes(invitation=f"{venue_id}/-/Submission"))
            )
        except Exception:
            notes = []
        
        if not notes:
            for pattern in [f"{venue_id}/-/Blind_Submission", f"{venue_id}/-/Paper"]:
                try:
                    notes = retry_with_backoff(
                        lambda p=pattern: list(client.get_all_notes(invitation=p))
                    )
                    if notes:
                        break
                except Exception:
                    continue
        
        for note in notes:
            content = note.content if hasattr(note, 'content') else {}
            
            def get_val(key):
                val = content.get(key)
                if isinstance(val, dict) and 'value' in val:
                    return val['value']
                return val
            
            submission = {
                "id": note.id,
                "forum": note.forum if hasattr(note, 'forum') else note.id,
                "title": get_val("title") or "Untitled",
                "abstract": get_val("abstract") or "",
                "authors": get_val("authors") or [],
                "keywords": get_val("keywords") or [],
                "tldr": get_val("TL;DR") or get_val("tldr") or "",
                "pdf": get_val("pdf") or "",
                "venue_id": venue_id,
            }
            
            base_url = "https://openreview.net"
            submission["openreview_url"] = f"{base_url}/forum?id={submission['forum']}"
            if submission["pdf"] and not submission["pdf"].startswith("http"):
                submission["pdf_url"] = f"{base_url}{submission['pdf']}"
            else:
                submission["pdf_url"] = submission["pdf"]
            
            submissions.append(submission)
        
        return submissions, f"Fetched {len(submissions)} submissions"
        
    except Exception as e:
        return [], f"Error: {str(e)}"
