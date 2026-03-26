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


def load_bios():
    """Load Chinese bios from bios_zh.json."""
    bios_path = SCRIPT_DIR / "bios_zh.json"
    try:
        with open(bios_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def fetch_twitter():
    """Fetch Twitter/X data from follow-builders, with RSSHub fallback."""
    print("Fetching Twitter data from follow-builders...", file=sys.stderr)
    data = fetch_json(FEED_X_URL)
    bios = load_bios()

    # Check if follow-builders data is fresh (< 12 hours old)
    is_stale = True
    if data and "generatedAt" in data:
        try:
            gen_time = datetime.fromisoformat(data["generatedAt"].replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - gen_time).total_seconds() / 3600
            is_stale = age_hours > 12
            if is_stale:
                print(f"  [WARN] follow-builders data is {age_hours:.1f}h old, trying RSSHub fallback...", file=sys.stderr)
        except Exception:
            pass

    builders = []

    if data and "x" in data and not is_stale:
        # Use follow-builders data
        builders = data["x"]
        print(f"  Found {len(builders)} builders from follow-builders", file=sys.stderr)
    else:
        # Fallback: try RSSHub for each account
        print("  Using RSSHub fallback for Twitter data...", file=sys.stderr)
        builders = fetch_twitter_rsshub(bios)
        # If RSSHub also fails, use stale follow-builders data as last resort
        if not builders and data and "x" in data:
            builders = data["x"]
            print(f"  RSSHub failed, using stale follow-builders data ({len(builders)} builders)", file=sys.stderr)

    # Inject Chinese bio for each builder (case-insensitive lookup)
    bios_lower = {k.lower(): v for k, v in bios.items()}
    for builder in builders:
        handle = builder.get("handle", "").lower()
        if handle in bios_lower:
            builder["bio_zh"] = bios_lower[handle]

    print(f"  Final: {len(builders)} builders with tweets", file=sys.stderr)
    return builders


def fetch_twitter_rsshub(bios):
    """Fallback: fetch tweets from RSSHub instances."""
    # List of public RSSHub instances to try
    rsshub_instances = [
        "https://rsshub.app",
        "https://rsshub.rssforever.com",
        "https://rsshub-instance.zeabur.app",
    ]

    # Get handles from bios or use default list
    handles = list(bios.keys()) if bios else [
        "karpathy", "swyx", "sama", "kevinweil", "petergyang",
        "rauchg", "levie", "garrytan", "danshipper", "trq212",
        "alexalbert__", "amasad", "steipete", "mattturck", "claudeai",
    ]

    builders = []
    working_instance = None

    # Find a working instance
    for instance in rsshub_instances:
        try:
            test_url = f"{instance}/twitter/user/sama"
            resp = requests.get(test_url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                working_instance = instance
                print(f"  Using RSSHub instance: {instance}", file=sys.stderr)
                break
        except Exception:
            continue

    if not working_instance:
        print("  [WARN] No working RSSHub instance found", file=sys.stderr)
        return []

    for handle in handles:
        try:
            url = f"{working_instance}/twitter/user/{handle}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue

            feed = feedparser.parse(resp.text)
            if not feed.entries:
                continue

            tweets = []
            for entry in feed.entries[:3]:
                # Parse entry
                title = entry.get("title", "")
                link = entry.get("link", "")
                pub_date = entry.get("published", "")

                # Try to extract tweet ID from link
                tweet_id = ""
                if "/status/" in link:
                    tweet_id = link.split("/status/")[-1].split("?")[0].split("#")[0]

                if not tweet_id:
                    continue

                tweets.append({
                    "id": tweet_id,
                    "text": title,
                    "createdAt": pub_date,
                    "url": link,
                    "likes": 0,
                    "retweets": 0,
                    "replies": 0,
                    "isQuote": False,
                    "quotedTweetId": None,
                })

            if tweets:
                # Find display name from bios or use handle
                display_name = handle
                for key, val in bios.items():
                    if key.lower() == handle.lower():
                        display_name = handle
                        break

                builders.append({
                    "source": "x",
                    "name": display_name.replace("_", " ").title(),
                    "handle": handle,
                    "bio": "",
                    "tweets": tweets,
                })

            # Be nice to the instance
            import time
            time.sleep(0.5)

        except Exception as e:
            print(f"  [WARN] RSSHub failed for @{handle}: {e}", file=sys.stderr)
            continue

    print(f"  RSSHub fetched {len(builders)} builders", file=sys.stderr)
    return builders


def fetch_podcasts():
    """Fetch latest episodes from YouTube RSS for each podcast channel."""
    print("Fetching podcast data from YouTube RSS...", file=sys.stderr)

    # Channel ID → Name mapping (from Zara's list + our additions)
    channels = {
        # Core AI podcasts
        "UCxBcwypKK-W3GHd_RZ9FZrQ": "Latent Space",
        "UCSI7h9hydQ40K5MJHnCrQvw": "No Priors",
        "UCUl-s_Vp-Kkk_XVyDylNwLA": "Unsupervised Learning",
        "UCQID78IY6EOojr5RUdD47MQ": "Data Driven NYC",
        "UC-DRzaGnL_vtBUpCFH5M0tg": "TBPN",
        # Tech / AI commentary
        "UCZHmQk67mSJgfCCTn7xBfew": "Lex Fridman",
        "UCsBjURrPoezykLs9EqgamOA": "Fireship",
        "UCJIfeSCssxSC_Dhc5s7woww": "Matt Wolfe",
        "UCXUPKJO5MZQN11PqgIvyuvQ": "AI Explained",
        # Product / startup
        "UC6t1O76G0jYXOAoYCm153dA": "Lenny's Podcast",
        "UCPjNBjflYl0-HQtUvOx0Ibw": "Greg Isenberg",
        "UCcefcZRL2oaA_uBNeo5UOWg": "Y Combinator",
        # AI companies
        "UCOIji0UklfggVrY7Ym-IfDQ": "Anthropic",
        "UCP7jMXSY2xbc3KCAE0MHQ-A": "Google DeepMind",
        # Builders
        "UCXUPKJO5MZQN11PqgIvyuvQ": "Andrej Karpathy",
        "UCt6l0E-bBC1Z4d7C3qgh3cA": "Rowan Cheung",
        # Communities
        "UCMR-rPSUI34DRQXUkvFuIUQ": "South Park Commons",
        "UCGwuxdEeCf0TIA2RbPOj-8g": "Stanford GSB",
        "UCmvYCRYPDlzSHVNCI_ViJDQ": "Tiago Forte",
    }

    # Playlists
    playlists = {
        "PLOhHNjZItNnMm5tdW61JpnyxeYH5NDDx8": "Training Data",
        "PLWEAb1SXhjlfkEF_PxzYHonU_v5LPMI8L": "Latent Space (full)",
        "PLuMcoKK9mKgHtW_o9h5sGO2vXrffKHwJL": "AI & I",
        "PLqYmG7hTraZBiUr6_Qf8YTS2Oqy3OGZEj": "Google DeepMind Podcast",
        "PLRYSuzHGhXPmKnOpd-f588cNNmTe2S9FP": "The AI Daily Brief",
        "PLIWHjbvRtljj4RewVNv_znkUe-3E-NKd2": "Behind the Craft",
        "PLmYVYFmFwGm3txxUduawn7i53C5rDjjd7": "Minus One",
        "PLQ-uHSnFig5Ob4XXhgSK26Smb4oRhzFmK": "Lightcone Podcast",
    }

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }

    episodes = []

    # Fetch from channels
    for channel_id, name in channels.items():
        try:
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                print(f"  [WARN] Failed to fetch {name}: HTTP {resp.status_code}", file=sys.stderr)
                continue

            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            for entry in list(root.findall("atom:entry", ns))[:3]:
                vid = entry.find("yt:videoId", ns)
                title = entry.find("atom:title", ns)
                pub = entry.find("atom:published", ns)
                if vid is not None and title is not None:
                    title_text = title.text or ""
                    # Detect Shorts by title patterns
                    is_short = any(tag in title_text.lower() for tag in
                                   ["#shorts", "#short", "#podcastclips", "#clips"])
                    # Also check if title is very short (common for shorts)
                    if not is_short and len(title_text) < 30 and "#" in title_text:
                        is_short = True
                    episodes.append({
                        "name": name,
                        "title": title_text,
                        "videoId": vid.text,
                        "url": f"https://youtube.com/watch?v={vid.text}",
                        "publishedAt": pub.text if pub is not None else "",
                        "isShort": is_short,
                    })
        except Exception as e:
            print(f"  [WARN] Error fetching {name}: {e}", file=sys.stderr)

    # Fetch from playlists
    for playlist_id, name in playlists.items():
        try:
            url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                continue

            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            for entry in list(root.findall("atom:entry", ns))[:3]:
                vid = entry.find("yt:videoId", ns)
                title = entry.find("atom:title", ns)
                pub = entry.find("atom:published", ns)
                if vid is not None and title is not None:
                    episodes.append({
                        "name": name,
                        "title": title.text or "",
                        "videoId": vid.text,
                        "url": f"https://youtube.com/watch?v={vid.text}",
                        "publishedAt": pub.text if pub is not None else "",
                        "isShort": False,
                    })
        except Exception as e:
            print(f"  [WARN] Error fetching {name}: {e}", file=sys.stderr)

    # Deduplicate by videoId
    seen = set()
    unique = []
    for e in episodes:
        vid = e.get("videoId", "")
        if vid and vid not in seen:
            seen.add(vid)
            unique.append(e)
    episodes = unique

    # Fetch duration for each episode (with retry)
    print("  Fetching video durations...", file=sys.stderr)
    for ep in episodes:
        vid = ep.get("videoId", "")
        if not vid:
            continue
        for attempt in range(2):  # retry once on failure
            try:
                url = f"https://www.youtube.com/watch?v={vid}"
                page_resp = requests.get(url, headers=HEADERS, timeout=20)
                if page_resp.status_code == 200:
                    match = re.search(r'"lengthSeconds"\s*:\s*"(\d+)"', page_resp.text)
                    if match:
                        seconds = int(match.group(1))
                        hours = seconds // 3600
                        minutes = (seconds % 3600) // 60
                        if seconds < 60:
                            ep["duration"] = f"{seconds}s"
                        elif hours > 0:
                            ep["duration"] = f"{hours}h{minutes:02d}m"
                        else:
                            ep["duration"] = f"{minutes}m"
                        ep["durationSeconds"] = seconds
                        ep["isShort"] = seconds <= 120
                        break  # success, no retry needed
            except Exception:
                if attempt == 0:
                    import time
                    time.sleep(1)  # brief pause before retry

    # Sort by date descending, take today's batch (max 5 long + 3 shorts = 8)
    episodes.sort(key=lambda e: e.get("publishedAt", ""), reverse=True)
    longs = [e for e in episodes if not e.get("isShort")][:5]
    shorts = [e for e in episodes if e.get("isShort")][:3]
    episodes = sorted(longs + shorts, key=lambda e: e.get("publishedAt", ""), reverse=True)
    episodes = episodes[:8]

    # Tag with fetch date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for e in episodes:
        e["fetchDate"] = today

    print(f"  Found {len(episodes)} episodes", file=sys.stderr)
    return episodes


def fetch_producthunt():
    """Fetch top 15 products from Product Hunt API (ranked by votes)."""
    print("Fetching Product Hunt API...", file=sys.stderr)

    ph_key = os.environ.get("PH_API_KEY", "")
    ph_secret = os.environ.get("PH_API_SECRET", "")

    if not ph_key or not ph_secret:
        print("  [WARN] PH_API_KEY/PH_API_SECRET not set, falling back to RSS", file=sys.stderr)
        return fetch_producthunt_rss()

    try:
        # Get access token
        token_resp = requests.post("https://api.producthunt.com/v2/oauth/token", json={
            "client_id": ph_key,
            "client_secret": ph_secret,
            "grant_type": "client_credentials",
        }, timeout=15)

        if token_resp.status_code != 200:
            print(f"  [WARN] PH token failed: {token_resp.status_code}", file=sys.stderr)
            return fetch_producthunt_rss()

        token = token_resp.json().get("access_token", "")
        if not token:
            return fetch_producthunt_rss()

        # Fetch top 15 posts ranked by votes
        gql_resp = requests.post(
            "https://api.producthunt.com/v2/api/graphql",
            json={"query": """{ posts(order: VOTES, first: 15) { edges { node {
                name tagline votesCount commentsCount url slug
                thumbnail { url }
                media { type url videoUrl }
                topics { edges { node { name } } }
            } } } }"""},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15,
        )

        if gql_resp.status_code != 200:
            print(f"  [WARN] PH GraphQL failed: {gql_resp.status_code}", file=sys.stderr)
            return fetch_producthunt_rss()

        edges = gql_resp.json().get("data", {}).get("posts", {}).get("edges", [])
        products = []
        for i, edge in enumerate(edges):
            node = edge["node"]
            topics = [t["node"]["name"] for t in node.get("topics", {}).get("edges", [])]
            thumb = node.get("thumbnail", {})
            thumb_url = thumb.get("url", "") if thumb else ""

            # Get first product screenshot (not the logo thumbnail)
            media_items = node.get("media", []) or []
            screenshot = ""
            for m in media_items[:1]:
                if m.get("url"):
                    screenshot = m["url"]
                    break

            products.append({
                "rank": i + 1,
                "name": node.get("name", "Unknown"),
                "tagline": node.get("tagline", ""),
                "url": node.get("url", ""),
                "votes": node.get("votesCount", 0),
                "comments": node.get("commentsCount", 0),
                "topics": topics,
                "thumbnail": thumb_url,
                "screenshot": screenshot,
            })

        print(f"  Found {len(products)} products (API)", file=sys.stderr)
        return products

    except Exception as e:
        print(f"  [WARN] PH API failed: {e}, falling back to RSS", file=sys.stderr)
        return fetch_producthunt_rss()


def fetch_producthunt_rss():
    """Fallback: Fetch products from Product Hunt RSS (no votes/tags)."""
    print("  Using PH RSS fallback...", file=sys.stderr)
    try:
        feed = feedparser.parse(PH_RSS_URL)
        if not feed.entries:
            return []

        products = []
        for i, entry in enumerate(feed.entries[:15]):
            raw_summary = entry.get("summary", "") or ""
            clean_summary = BeautifulSoup(raw_summary, "html.parser").get_text(separator=" ", strip=True)
            clean_summary = re.sub(r'\s*(Discussion|Link|Comments?)(\s*\|\s*(Discussion|Link|Comments?))*\s*$', '', clean_summary)
            tagline = clean_summary.split(".")[0].strip() if clean_summary else ""
            if len(tagline) > 120:
                tagline = tagline[:120] + "..."

            products.append({
                "rank": i + 1,
                "name": entry.get("title", "Unknown"),
                "tagline": tagline,
                "url": entry.get("link", ""),
                "votes": 0,
                "comments": 0,
                "topics": [],
                "thumbnail": "",
            })

        print(f"  Found {len(products)} products (RSS fallback)", file=sys.stderr)
        return products
    except Exception as e:
        print(f"  [WARN] PH RSS failed: {e}", file=sys.stderr)
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


def load_existing_feed():
    """Load existing feed.json for history accumulation."""
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def merge_history(old_feed, new_twitter, new_podcasts):
    """Merge new data into existing feed, preserving history with dedup."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # --- Podcasts: accumulate, dedup by videoId, keep 7 days ---
    old_podcasts = old_feed.get("podcasts", []) if old_feed else []
    existing_vids = {ep.get("videoId") for ep in old_podcasts}
    for ep in new_podcasts:
        if ep.get("videoId") not in existing_vids:
            old_podcasts.append(ep)
    # Sort by date desc, keep max 7 days of content
    old_podcasts.sort(key=lambda e: e.get("publishedAt", ""), reverse=True)
    cutoff = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=7)).isoformat()
    podcasts = [ep for ep in old_podcasts if ep.get("publishedAt", "") >= cutoff or not ep.get("publishedAt")]
    # Safety cap at 60 episodes
    podcasts = podcasts[:60]

    # --- Twitter: accumulate by fetchDate, dedup by tweet id, keep 7 days ---
    old_twitter = old_feed.get("twitter_history", []) if old_feed else []
    # Add today's builders
    for builder in new_twitter:
        builder["fetchDate"] = today
    # Merge: combine old history + new
    all_tweet_ids = set()
    for day_builders in old_twitter:
        for b in day_builders.get("builders", []):
            for t in b.get("tweets", []):
                all_tweet_ids.add(t.get("id"))
    # Filter new tweets to only truly new ones
    filtered_new = []
    for b in new_twitter:
        new_tweets = [t for t in b.get("tweets", []) if t.get("id") not in all_tweet_ids]
        if new_tweets:
            filtered_new.append({**b, "tweets": new_tweets})
    # Add today's batch to history
    if filtered_new:
        old_twitter.insert(0, {"date": today, "builders": filtered_new})
    # Keep 7 days
    cutoff_date = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=7)).strftime("%Y-%m-%d")
    twitter_history = [day for day in old_twitter if day.get("date", "") >= cutoff_date]

    return podcasts, twitter_history


def main():
    print("=" * 50, file=sys.stderr)
    print("Breakfeed — Daily Data Fetch", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    # Load existing feed for history
    old_feed = load_existing_feed()

    # Fetch all sources
    twitter = fetch_twitter()
    podcasts = fetch_podcasts()
    producthunt = fetch_producthunt()
    github_trending = fetch_github_trending()

    # Merge with history
    merged_podcasts, twitter_history = merge_history(old_feed, twitter, podcasts)

    # Assemble feed
    feed = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "twitter": twitter,           # Today's builders (for backwards compat)
        "twitter_history": twitter_history,  # All days, grouped by date
        "podcasts": merged_podcasts,   # Accumulated episodes
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
    print(f"  Twitter: {len(twitter)} builders, {tweet_count} tweets (today)", file=sys.stderr)
    print(f"  Twitter history: {len(twitter_history)} days", file=sys.stderr)
    print(f"  Podcasts: {len(merged_podcasts)} episodes (accumulated)", file=sys.stderr)
    print(f"  Product Hunt: {len(producthunt)} products", file=sys.stderr)
    print(f"  GitHub: {len(github_trending)} repos", file=sys.stderr)
    print(f"{'=' * 50}", file=sys.stderr)


if __name__ == "__main__":
    main()
