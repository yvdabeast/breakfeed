#!/usr/bin/env python3
"""
Breakfeed — Daily Data Fetcher
Pulls data from:
  1. follow-builders repo (Twitter + YouTube, public JSON)
  2. Product Hunt (RSS feed)
  3. GitHub Trending (HTML scrape)
Outputs: dist/data/feed.json
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import re
import ssl

import feedparser
import requests
from bs4 import BeautifulSoup

# Workaround for older Python SSL on macOS
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- Config ---
SCRIPT_DIR = Path(__file__).parent
DIST_DIR = SCRIPT_DIR.parent / "dist"
OUTPUT_PATH = DIST_DIR / "data" / "feed.json"

FOLLOW_BUILDERS_BASE = "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main"
FEED_X_URL = f"{FOLLOW_BUILDERS_BASE}/feed-x.json"
FEED_PODCASTS_URL = f"{FOLLOW_BUILDERS_BASE}/feed-podcasts.json"

PH_RSS_URL = "https://www.producthunt.com/feed"
GITHUB_TRENDING_URL = "https://github.com/trending"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Breakfeed/1.0"
}

REQUEST_TIMEOUT = 30


def fetch_json(url):
    """Fetch and parse JSON from a URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}", file=sys.stderr)
        return None


def fetch_twitter():
    """Fetch Twitter/X data from follow-builders."""
    print("Fetching Twitter data from follow-builders...", file=sys.stderr)
    data = fetch_json(FEED_X_URL)
    if not data or "x" not in data:
        print("  [WARN] No Twitter data available", file=sys.stderr)
        return []

    builders = data["x"]
    print(f"  Found {len(builders)} builders with tweets", file=sys.stderr)
    return builders


def fetch_podcasts():
    """Fetch podcast data from follow-builders."""
    print("Fetching podcast data from follow-builders...", file=sys.stderr)
    data = fetch_json(FEED_PODCASTS_URL)
    if not data or "podcasts" not in data:
        print("  [WARN] No podcast data available", file=sys.stderr)
        return []

    podcasts = data["podcasts"]
    print(f"  Found {len(podcasts)} episodes", file=sys.stderr)
    return podcasts


def fetch_producthunt():
    """Fetch top products from Product Hunt RSS."""
    print("Fetching Product Hunt RSS...", file=sys.stderr)
    try:
        feed = feedparser.parse(PH_RSS_URL)
        if not feed.entries:
            print("  [WARN] No PH entries found", file=sys.stderr)
            return []

        products = []
        for entry in feed.entries[:10]:
            # Strip HTML from summary and clean up
            raw_summary = entry.get("summary", "") or ""
            clean_summary = BeautifulSoup(raw_summary, "html.parser").get_text(separator=" ", strip=True)
            # Remove trailing "Discussion | Link" and similar noise
            clean_summary = re.sub(r'\s*(Discussion|Link|Comments?)(\s*\|\s*(Discussion|Link|Comments?))*\s*$', '', clean_summary)
            # Take first sentence only
            tagline = clean_summary.split(".")[0].strip() if clean_summary else ""
            if len(tagline) > 120:
                tagline = tagline[:120] + "..."

            products.append({
                "name": entry.get("title", "Unknown"),
                "tagline": tagline,
                "url": entry.get("link", ""),
                "votes": 0,  # RSS doesn't include vote counts
                "thumbnail": "",
            })

        print(f"  Found {len(products)} products", file=sys.stderr)
        return products
    except Exception as e:
        print(f"  [WARN] Failed to fetch Product Hunt: {e}", file=sys.stderr)
        return []


def fetch_github_trending():
    """Scrape GitHub Trending page."""
    print("Fetching GitHub Trending...", file=sys.stderr)
    try:
        resp = requests.get(
            GITHUB_TRENDING_URL,
            headers=HEADERS,
            params={"since": "daily"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        repos = []
        articles = soup.select("article.Box-row")

        for article in articles[:10]:
            # Repo name
            h2 = article.select_one("h2")
            if not h2:
                continue
            a_tag = h2.select_one("a")
            if not a_tag:
                continue
            repo_path = a_tag.get("href", "").strip("/")

            # Description
            p_tag = article.select_one("p")
            description = p_tag.get_text(strip=True) if p_tag else ""

            # Language
            lang_span = article.select_one("[itemprop='programmingLanguage']")
            language = lang_span.get_text(strip=True) if lang_span else ""

            # Stars
            star_links = article.select("a.Link--muted")
            stars = 0
            stars_today = 0

            for link in star_links:
                href = link.get("href", "")
                text = link.get_text(strip=True).replace(",", "")
                if "/stargazers" in href:
                    try:
                        stars = int(text)
                    except ValueError:
                        pass

            # Stars today
            spans = article.select("span.d-inline-block")
            for span in spans:
                text = span.get_text(strip=True)
                if "stars today" in text or "stars this week" in text:
                    num = text.split()[0].replace(",", "")
                    try:
                        stars_today = int(num)
                    except ValueError:
                        pass

            repos.append({
                "repo": repo_path,
                "description": description,
                "language": language,
                "stars": stars,
                "starsToday": stars_today,
                "url": f"https://github.com/{repo_path}",
            })

        print(f"  Found {len(repos)} trending repos", file=sys.stderr)
        return repos
    except Exception as e:
        print(f"  [WARN] Failed to fetch GitHub Trending: {e}", file=sys.stderr)
        return []


def main():
    print("=" * 50, file=sys.stderr)
    print("Breakfeed — Daily Data Fetch", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    # Fetch all sources
    twitter = fetch_twitter()
    podcasts = fetch_podcasts()
    producthunt = fetch_producthunt()
    github_trending = fetch_github_trending()

    # Assemble feed
    feed = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "twitter": twitter,
        "podcasts": podcasts,
        "producthunt": producthunt,
        "github_trending": github_trending,
    }

    # Ensure output directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Write feed
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)

    # Stats
    tweet_count = sum(len(b.get("tweets", [])) for b in twitter)
    print(f"\n{'=' * 50}", file=sys.stderr)
    print(f"Done! Output: {OUTPUT_PATH}", file=sys.stderr)
    print(f"  Twitter: {len(twitter)} builders, {tweet_count} tweets", file=sys.stderr)
    print(f"  Podcasts: {len(podcasts)} episodes", file=sys.stderr)
    print(f"  Product Hunt: {len(producthunt)} products", file=sys.stderr)
    print(f"  GitHub: {len(github_trending)} repos", file=sys.stderr)
    print(f"{'=' * 50}", file=sys.stderr)


if __name__ == "__main__":
    main()
