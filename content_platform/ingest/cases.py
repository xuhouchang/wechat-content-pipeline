from urllib.parse import quote

from lib import is_monday


PODCASTS = [
    {"name": "HBR Podcasts", "search_query": "hbr.org/podcast AI enterprise workforce organization"},
    {"name": "a16z Podcast", "url": "https://podscripts.co/podcasts/a16z-podcast/"},
    {"name": "McKinsey on AI", "url": "https://www.audioscrape.com/podcast/mckinsey-on-ai"},
    {"name": "The AI in Business (Emerj)", "url": "https://podcast.emergj.com/"},
    {"name": "Me, Myself, and AI (MIT SMR+BCG)", "search_query": '"Me Myself and AI" podcast transcript'},
]


def load_case_materials(date_str: str, force: bool = False) -> list[dict]:
    if not is_monday() and not force:
        return []

    materials = []
    for podcast in PODCASTS:
        summary = podcast.get("search_query", podcast.get("url", ""))
        url = podcast.get("url", f"https://search.local/?q={quote(summary)}")
        materials.append(
            {
                "url": url,
                "title": podcast["name"],
                "summary": summary,
                "content_text": summary,
                "source_type": "podcasts",
                "source_name": podcast["name"],
                "date": date_str,
            }
        )

    return materials
