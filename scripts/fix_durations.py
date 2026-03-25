#!/usr/bin/env python3
"""
Fix missing podcast durations by fetching from YouTube.
Runs locally (YouTube doesn't block residential IPs).
"""
import json
import re
import sys
from pathlib import Path

import requests

FEED_PATH = Path(__file__).parent.parent / "dist" / "data" / "feed.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def main():
    with open(FEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    for ep in data.get("podcasts", []):
        vid = ep.get("videoId", "")
        if not vid or ep.get("duration"):
            continue
        try:
            url = f"https://www.youtube.com/watch?v={vid}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            match = re.search(r'"lengthSeconds"\s*:\s*"(\d+)"', resp.text)
            if match:
                seconds = int(match.group(1))
                if seconds < 60:
                    ep["duration"] = f"{seconds}s"
                elif seconds < 3600:
                    m = seconds // 60
                    s = seconds % 60
                    ep["duration"] = f"{m}m{s:02d}s" if s > 0 else f"{m}m"
                else:
                    h = seconds // 3600
                    m = (seconds % 3600) // 60
                    ep["duration"] = f"{h}h{m:02d}m"
                ep["durationSeconds"] = seconds
                ep["isShort"] = seconds <= 120
                updated += 1
                print(f"  {ep['duration']:>8} | {ep['title'][:60]}")
        except Exception as e:
            print(f"  FAIL | {vid}: {e}", file=sys.stderr)

    if updated:
        with open(FEED_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Updated {updated} durations")
    else:
        print("All durations present, nothing to do")


if __name__ == "__main__":
    main()
