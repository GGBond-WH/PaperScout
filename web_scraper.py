import requests
import json
import re
from typing import List, Dict, Any

# GitHub URL template for AAAI data (maintained by Paper Copilot community)
AAAI_GITHUB_URL_TEMPLATE = "https://raw.githubusercontent.com/papercopilot/paperlists/main/aaai/aaai{year}.json"

def fetch_aaai_from_github(year: str) -> List[Dict[str, Any]]:
    """
    Fetch AAAI papers for a specific year from Paper Copilot's GitHub repository.
    Returns a list of flattened dictionaries compliant with ui_components.py.
    """
    url = AAAI_GITHUB_URL_TEMPLATE.format(year=year)
    try:
        print(f"Fetching AAAI {year} data from {url}...")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 404:
             print(f"AAAI {year} data not found on GitHub.")
             return []
             
        response.raise_for_status()
        
        data = response.json()
        notes = []
        
        for item in data:
            # Parse authors (semicolon separated in source)
            authors_str = item.get('author', '')
            authors = [a.strip() for a in authors_str.split(';')] if authors_str else []
            
            # Construct flattened paper dict matching openreview_client.py output
            title = item.get('title', 'Untitled')
            
            # Map item fields to app expectation
            note = {
                'id': item.get('id', 'unknown'),
                'forum': item.get('id', 'unknown'), # Use ID as forum
                'title': title,
                'abstract': item.get('abstract', ''),
                'authors': authors,
                'keywords': [], # Not usually in this JSON
                'tldr': "",
                'pdf': item.get('pdf', ''),
                'venue': f'AAAI {year}',
                'venue_id': f'AAAI.org/{year}/Conference',
                'year': int(year),
                
                # App defaults for missing scores
                'avg_score': None,
                'max_score': None,
                'min_score': None,
                'scored_review_count': 0,
                'score_distribution': {},
            }
            notes.append(note)
            
        print(f"Successfully fetched {len(notes)} AAAI {year} papers from GitHub.")
        return notes
        
    except Exception as e:
        print(f"Error fetching AAAI {year} data: {e}")
        return []

def scrape_venue(venue_id: str) -> List[Dict[str, Any]]:
    """
    Dispatcher for web-scraped venues.
    Parses year from venue_id to select correct fetcher.
    """
    if "AAAI" in venue_id:
        # Extract year from AAAI.org/2025/Conference
        match = re.search(r'20\d{2}', venue_id)
        if match:
            year = match.group(0)
            return fetch_aaai_from_github(year)
    
    return []
