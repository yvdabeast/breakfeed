# Breakfeed

Your AI morning briefing. A daily auto-updating page that aggregates:

- **AI Builders on Twitter/X** — via [follow-builders](https://github.com/zarazhangrui/follow-builders)
- **AI Podcasts** — Latent Space, No Priors, etc.
- **Product Hunt** — daily hot products
- **GitHub Trending** — trending repos

## Setup

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Fetch data
python scripts/fetch_data.py

# Preview locally
npx http-server dist -p 8080
```

## Auto-update

GitHub Actions runs daily at 06:00 Beijing time, fetches fresh data, and deploys to GitHub Pages.

No API keys required — all data sources are public.
