#!/usr/bin/env python3
"""
Breakfeed — Chinese Summary Generator
Uses Claude API to generate Chinese summaries for ALL content:
  - Tweets (summary_zh)
  - Podcasts (summary_zh with watch recommendation)
  - Product Hunt (summary_zh with relevance)
  - GitHub Trending (summary_zh with relevance)

Usage:
  ANTHROPIC_API_KEY=sk-... python summarize.py

If no API key is set, skips summarization silently.
"""

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
FEED_PATH = SCRIPT_DIR.parent / "dist" / "data" / "feed.json"

# Context about Yves for personalized recommendations
YVES_CONTEXT = """受众背景：
- Yves（衣服）：Logic Labs（AI 公司）和 TexTale（男士科技服装电商）联合创始人
- 前 OnePlus 全球创意设计总监
- 零代码能力，但创意极强，用 AI 作为主要工具
- 关注：AI 行业趋势、创意设计工具、电商运营、品牌营销"""


def summarize_tweets(client, feed):
    """Generate Chinese summaries for tweets in twitter and twitter_history."""
    all_builders = list(feed.get("twitter", []))
    for day in feed.get("twitter_history", []):
        all_builders.extend(day.get("builders", []))

    count = 0
    for builder in all_builders:
        name = builder.get("name", "Unknown")
        handle = builder.get("handle", "")
        bio = builder.get("bio", "")
        bio_zh = builder.get("bio_zh", "")

        for tweet in builder.get("tweets", []):
            if tweet.get("summary_zh"):
                continue

            text = tweet.get("text", "")
            if not text.strip():
                continue

            stripped = re.sub(r'https?://\S+', '', text).strip()
            if not stripped:
                tweet["summary_zh"] = ""
                continue

            prompt = f"""你是一个 AI 行业资讯翻译员。把下面这条推文翻译/解读成简单易懂的中文，让完全不懂 AI 的普通人也能看懂。

要求：
- 一两句话概括这条推文在说什么
- 如果有行业术语，用括号简单解释
- 语气轻松自然，像朋友聊天
- 不要加"这条推文说的是"之类的前缀，直接说内容
- 如果推文只是转发或分享链接配了一句简短评语，概括他想说的意思

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
                count += 1
                print(f"  [tweet] @{handle}: {summary[:50]}...", file=sys.stderr)
            except Exception as e:
                print(f"  [WARN] Tweet @{handle}: {e}", file=sys.stderr)

    return count


def summarize_podcasts(client, feed):
    """Generate Chinese summaries with watch recommendations for podcasts."""
    count = 0
    for ep in feed.get("podcasts", []):
        if ep.get("summary_zh"):
            continue

        title = ep.get("title", "")
        name = ep.get("name", "")
        duration = ep.get("duration", "")

        prompt = f"""你是 AI 行业资讯分析师，为一位特定用户推荐播客视频。

{YVES_CONTEXT}

请为以下视频写中文摘要和观看建议：

频道：{name}
标题：{title}
时长：{duration}

要求：
1. 第一段：2-3 句话概括这个视频讲什么，用普通人能懂的语言
2. 第二段另起一行，用以下格式之一给出观看建议：
   - "🎯 推荐 Yves 观看 — [具体原因，提到 Logic Labs/TexTale/创意设计中的哪个相关]"
   - "💡 值得一看 — [原因]"
   - "⏭️ 建议跳过 — [原因]"

判断标准：
- 与 AI 工具/产品开发/创业直接相关 → 🎯 推荐
- 与科技趋势/行业洞察/设计创意间接相关 → 💡 值得一看
- 与 AI/设计/创业无关（纯娱乐/医疗/政治等） → ⏭️ 建议跳过

只输出摘要和建议，不要加任何前缀标题。"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = response.content[0].text.strip()
            ep["summary_zh"] = summary
            count += 1
            print(f"  [podcast] {name}: {summary[:50]}...", file=sys.stderr)
        except Exception as e:
            print(f"  [WARN] Podcast {name}: {e}", file=sys.stderr)

    return count


def summarize_producthunt(client, feed):
    """Generate Chinese summaries for Product Hunt items."""
    count = 0
    for product in feed.get("producthunt", []):
        if product.get("summary_zh"):
            continue

        name = product.get("name", "")
        tagline = product.get("tagline", "")

        prompt = f"""你是 AI 行业产品分析师，为一位特定用户分析新产品。

{YVES_CONTEXT}

产品名：{name}
一句话介绍：{tagline}

请用中文写 2-3 句话：
1. 这个产品是做什么的（用普通人能懂的话）
2. 对 Yves 的哪个业务有帮助：Logic Labs（AI 公司）还是 TexTale（科技服装电商），或者对他作为创意/设计 IC 有什么价值

只输出分析内容，不要加前缀。"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = response.content[0].text.strip()
            product["summary_zh"] = summary
            count += 1
            print(f"  [ph] {name}: {summary[:50]}...", file=sys.stderr)
        except Exception as e:
            print(f"  [WARN] PH {name}: {e}", file=sys.stderr)

    return count


def summarize_github(client, feed):
    """Generate Chinese summaries for GitHub trending repos."""
    count = 0
    for repo in feed.get("github_trending", []):
        if repo.get("summary_zh"):
            continue

        repo_name = repo.get("repo", "")
        description = repo.get("description", "")
        language = repo.get("language", "")
        stars = repo.get("stars", 0)

        prompt = f"""你是开源项目分析师，为一位特定用户分析 GitHub 热门项目。

{YVES_CONTEXT}

项目：{repo_name}
描述：{description}
语言：{language}
Stars：{stars}

请用中文写 2-3 句话：
1. 这个项目是做什么的（用普通人能懂的话）
2. 对 Yves 的哪个业务有帮助：Logic Labs（AI 公司）还是 TexTale（科技服装电商），或者对他作为创意设计从业者有什么价值

只输出分析内容，不要加前缀。"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = response.content[0].text.strip()
            repo["summary_zh"] = summary
            count += 1
            print(f"  [gh] {repo_name}: {summary[:50]}...", file=sys.stderr)
        except Exception as e:
            print(f"  [WARN] GH {repo_name}: {e}", file=sys.stderr)

    return count


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

    print("=" * 50, file=sys.stderr)
    print("Breakfeed — Generating Chinese Summaries", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    tweet_count = summarize_tweets(client, feed)
    podcast_count = summarize_podcasts(client, feed)
    ph_count = summarize_producthunt(client, feed)
    gh_count = summarize_github(client, feed)

    # Write back
    with open(FEED_PATH, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)

    total = tweet_count + podcast_count + ph_count + gh_count
    print(f"\nDone! Generated {total} summaries:", file=sys.stderr)
    print(f"  Tweets: {tweet_count}", file=sys.stderr)
    print(f"  Podcasts: {podcast_count}", file=sys.stderr)
    print(f"  Product Hunt: {ph_count}", file=sys.stderr)
    print(f"  GitHub: {gh_count}", file=sys.stderr)


if __name__ == "__main__":
    main()
