#!/usr/bin/env python3
"""
Breakfeed — Chinese Summary Generator
Reads feed.json, uses Claude API to generate Chinese summaries for tweets.
Writes summaries back into feed.json (adds summary_zh to each tweet).

Usage:
  ANTHROPIC_API_KEY=sk-... python summarize.py

If no API key is set, skips summarization silently.
"""

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
FEED_PATH = SCRIPT_DIR.parent / "dist" / "data" / "feed.json"


def summarize_tweets(client, builders):
    """Generate Chinese summaries for all tweets using Claude API."""
    for builder in builders:
        name = builder.get("name", "Unknown")
        handle = builder.get("handle", "")
        bio = builder.get("bio", "")
        bio_zh = builder.get("bio_zh", "")

        for tweet in builder.get("tweets", []):
            # Skip if already summarized
            if tweet.get("summary_zh"):
                continue

            text = tweet.get("text", "")
            if not text.strip():
                continue

            prompt = f"""你是一个 AI 行业资讯翻译员。把下面这条推文翻译/解读成简单易懂的中文，让完全不懂 AI 的普通人也能看懂。

要求：
- 一两句话概括这条推文在说什么
- 如果有行业术语，用括号简单解释
- 语气轻松自然，像朋友聊天
- 不要加"这条推文说的是"之类的前缀，直接说内容
- 如果推文只是一个链接或无实质内容，就写"分享了一个链接"

发推人：{name} (@{handle})
背景：{bio_zh or bio}
推文原文：{text}"""

            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                )
                summary = response.content[0].text.strip()
                tweet["summary_zh"] = summary
                print(f"  [{handle}] {summary[:60]}...", file=sys.stderr)
            except Exception as e:
                print(f"  [WARN] Failed to summarize tweet by @{handle}: {e}", file=sys.stderr)
                tweet["summary_zh"] = ""


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("No ANTHROPIC_API_KEY set, skipping summarization.", file=sys.stderr)
        return

    try:
        import anthropic
    except ImportError:
        print("anthropic package not installed, skipping.", file=sys.stderr)
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Load feed
    with open(FEED_PATH, "r", encoding="utf-8") as f:
        feed = json.load(f)

    builders = feed.get("twitter", [])
    if not builders:
        print("No Twitter data to summarize.", file=sys.stderr)
        return

    total_tweets = sum(len(b.get("tweets", [])) for b in builders)
    unsummarized = sum(
        1 for b in builders for t in b.get("tweets", []) if not t.get("summary_zh")
    )
    print(f"Summarizing {unsummarized}/{total_tweets} tweets...", file=sys.stderr)

    summarize_tweets(client, builders)

    # Write back
    with open(FEED_PATH, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)

    print("Done! Summaries written to feed.json", file=sys.stderr)


if __name__ == "__main__":
    main()
