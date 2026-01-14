"""
Parsing utilities for OpenReview Paper Filtering Tool.
Handles score parsing, keyword matching, and statistics computation.
"""

import re
from typing import List, Dict, Optional, Any, Tuple
from config import SCORE_FIELD_NAMES, CONFIDENCE_FIELD_NAMES


def parse_score(text: Any) -> Optional[float]:
    """
    Extract numeric score from a review field value.
    
    Handles various formats:
    - "6: Strong Accept" -> 6.0
    - "8 (Top 10%)" -> 8.0
    - "3.5" -> 3.5
    - 7 -> 7.0
    - "Accept" -> None
    
    Args:
        text: The field value (string, int, float, or other)
        
    Returns:
        Extracted float score or None if not parseable
    """
    if text is None:
        return None
    
    # If already numeric
    if isinstance(text, (int, float)):
        return float(text)
    
    # Convert to string
    text_str = str(text).strip()
    if not text_str:
        return None
    
    # Try to find the first number (int or float) in the string
    # Pattern matches: optional negative, digits, optional decimal part
    match = re.search(r'-?\d+\.?\d*', text_str)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    
    return None


def extract_review_scores(review: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract score and confidence from a review dict.
    
    Args:
        review: Review dictionary containing content fields
        
    Returns:
        Tuple of (score, confidence), either may be None
    """
    content = review.get("content", {})
    
    # Extract score (try multiple field names in priority order)
    score = None
    for field_name in SCORE_FIELD_NAMES:
        if field_name in content:
            value = content[field_name]
            # Handle nested dict format (OpenReview v2 API)
            if isinstance(value, dict) and "value" in value:
                value = value["value"]
            parsed = parse_score(value)
            if parsed is not None:
                score = parsed
                break
    
    # Extract confidence
    confidence = None
    for field_name in CONFIDENCE_FIELD_NAMES:
        if field_name in content:
            value = content[field_name]
            if isinstance(value, dict) and "value" in value:
                value = value["value"]
            parsed = parse_score(value)
            if parsed is not None:
                confidence = parsed
                break
    
    return score, confidence


def compute_score_stats(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute score statistics from a list of reviews.
    
    Args:
        reviews: List of review dictionaries
        
    Returns:
        Dict with keys: max_score, avg_score, min_score, 
                       review_count, scored_review_count, scores, confidences
    """
    scores = []
    confidences = []
    
    for review in reviews:
        score, confidence = extract_review_scores(review)
        if score is not None:
            scores.append(score)
        if confidence is not None:
            confidences.append(confidence)
    
    result = {
        "review_count": len(reviews),
        "scored_review_count": len(scores),
        "scores": scores,
        "confidences": confidences,
        "max_score": max(scores) if scores else None,
        "min_score": min(scores) if scores else None,
        "avg_score": sum(scores) / len(scores) if scores else None,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else None,
    }
    
    return result


def match_keywords(
    text: str, 
    keywords: List[str], 
    logic: str = "OR"
) -> bool:
    """
    Check if text matches keywords based on logic.
    
    Args:
        text: Text to search in
        keywords: List of keywords to match
        logic: "AND" (all keywords must match) or "OR" (any keyword matches)
        
    Returns:
        True if text matches according to logic
    """
    if not keywords or not text:
        return True  # No keywords means everything matches
    
    text_lower = text.lower()
    
    if logic.upper() == "AND":
        return all(kw.lower() in text_lower for kw in keywords)
    else:  # OR
        return any(kw.lower() in text_lower for kw in keywords)


def filter_paper_by_keywords(
    paper: Dict[str, Any],
    keywords: List[str],
    field_scope: str = "title_or_abstract",
    logic: str = "OR"
) -> bool:
    """
    Check if a paper matches keyword criteria.
    
    Args:
        paper: Paper dictionary with 'title' and 'abstract' fields
        keywords: List of keywords
        field_scope: One of "title", "abstract", "title_or_abstract", "title_and_abstract"
        logic: "AND" or "OR" for keyword matching within a field
        
    Returns:
        True if paper matches criteria
    """
    if not keywords:
        return True
    
    title = paper.get("title", "") or ""
    abstract = paper.get("abstract", "") or ""
    
    if field_scope == "title":
        return match_keywords(title, keywords, logic)
    elif field_scope == "abstract":
        return match_keywords(abstract, keywords, logic)
    elif field_scope == "title_or_abstract":
        return match_keywords(title, keywords, logic) or match_keywords(abstract, keywords, logic)
    elif field_scope == "title_and_abstract":
        return match_keywords(title, keywords, logic) and match_keywords(abstract, keywords, logic)
    else:
        return match_keywords(title + " " + abstract, keywords, logic)


def filter_paper_by_scores(
    paper: Dict[str, Any],
    min_avg_score: Optional[float] = None,
    min_max_score: Optional[float] = None,
    min_review_count: Optional[int] = None,
    min_confidence: Optional[float] = None,
) -> bool:
    """
    Check if a paper meets score filter criteria.
    
    Args:
        paper: Paper dictionary with score stats
        min_avg_score: Minimum average score required
        min_max_score: Minimum max score required
        min_review_count: Minimum number of scored reviews required
        min_confidence: Minimum average confidence required
        
    Returns:
        True if paper meets all criteria
    """
    avg_score = paper.get("avg_score")
    max_score = paper.get("max_score")
    scored_count = paper.get("scored_review_count", 0)
    avg_confidence = paper.get("avg_confidence")
    
    # Check average score
    if min_avg_score is not None:
        if avg_score is None or avg_score < min_avg_score:
            return False
    
    # Check max score
    if min_max_score is not None:
        if max_score is None or max_score < min_max_score:
            return False
    
    # Check review count
    if min_review_count is not None:
        if scored_count < min_review_count:
            return False
    
    # Check confidence
    if min_confidence is not None:
        if avg_confidence is None or avg_confidence < min_confidence:
            return False
    
    return True


def highlight_keywords(text: str, keywords: List[str]) -> str:
    """
    Highlight keywords in text using HTML markup.
    
    Args:
        text: Original text
        keywords: Keywords to highlight
        
    Returns:
        HTML string with highlighted keywords
    """
    if not keywords or not text:
        return text
    
    result = text
    for kw in keywords:
        if not kw:
            continue
        # Case-insensitive replacement with highlight
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        result = pattern.sub(
            lambda m: f'<mark style="background-color: #ffeb3b; padding: 0 2px;">{m.group()}</mark>',
            result
        )
    
    return result


def parse_keywords_input(input_str: str) -> List[str]:
    """
    Parse user keyword input string into list of keywords.
    Supports comma and space separation.
    
    Args:
        input_str: User input like "transformer, attention" or "transformer attention"
        
    Returns:
        List of non-empty keyword strings
    """
    if not input_str:
        return []
    
    # First split by comma
    parts = input_str.replace(",", " ").split()
    
    # Filter empty strings and strip whitespace
    keywords = [kw.strip() for kw in parts if kw.strip()]
    
    return keywords


def sort_papers(
    papers: List[Dict[str, Any]], 
    sort_by: str = "avg_score", 
    ascending: bool = False
) -> List[Dict[str, Any]]:
    """
    Sort papers by specified field.
    
    Args:
        papers: List of paper dictionaries
        sort_by: Field to sort by (avg_score, max_score, review_count, year, title)
        ascending: Sort order
        
    Returns:
        Sorted list of papers
    """
    def get_sort_key(paper):
        value = paper.get(sort_by)
        if value is None:
            # Put None values at the end
            return (1, 0) if not ascending else (0, float('inf'))
        if isinstance(value, str):
            return (0, value.lower())
        return (0, value)
    
    return sorted(papers, key=get_sort_key, reverse=not ascending)
