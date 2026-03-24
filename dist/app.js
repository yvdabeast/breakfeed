// ============================================
// Breakfeed — App Logic
// ============================================

(function () {
  'use strict';

  const FEED_URL = 'data/feed.json';

  // --- Theme ---
  function initTheme() {
    const saved = localStorage.getItem('breakfeed-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeIcon(theme);

    document.getElementById('themeToggle').addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('breakfeed-theme', next);
      updateThemeIcon(next);
    });
  }

  function updateThemeIcon(theme) {
    const icon = document.querySelector('.theme-icon');
    icon.textContent = theme === 'dark' ? '\u2600' : '\u263E';
  }

  // --- Navigation ---
  function initNav() {
    const pills = document.querySelectorAll('.pill');
    pills.forEach(pill => {
      pill.addEventListener('click', () => {
        pills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');

        const section = pill.getAttribute('data-section');
        document.querySelectorAll('.section').forEach(s => s.classList.add('hidden'));
        const target = document.getElementById('section-' + section);
        if (target) {
          target.classList.remove('hidden');
          target.style.animation = 'none';
          target.offsetHeight; // trigger reflow
          target.style.animation = '';
        }
      });
    });
  }

  // --- Date Display ---
  function renderDate() {
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const dateStr = now.toLocaleDateString('en-US', options);
    const hour = now.getHours();
    let greeting = 'Good morning';
    if (hour >= 12 && hour < 17) greeting = 'Good afternoon';
    else if (hour >= 17) greeting = 'Good evening';

    document.getElementById('dateDisplay').textContent = greeting + ' \u2014 ' + dateStr;
  }

  // --- Render Stats ---
  function renderStats(data) {
    const tweets = data.twitter ? data.twitter.reduce((sum, b) => sum + b.tweets.length, 0) : 0;
    const podcasts = data.podcasts ? data.podcasts.length : 0;
    const products = data.producthunt ? data.producthunt.length : 0;
    const repos = data.github_trending ? data.github_trending.length : 0;

    const parts = [];
    if (tweets > 0) parts.push(tweets + ' tweets');
    if (podcasts > 0) parts.push(podcasts + ' episode' + (podcasts > 1 ? 's' : ''));
    if (products > 0) parts.push(products + ' products');
    if (repos > 0) parts.push(repos + ' repos');

    document.getElementById('statsDisplay').textContent =
      'Today: ' + parts.join(' \u00B7 ');
  }

  // --- Render Update Time ---
  function renderUpdateTime(data) {
    if (!data.generatedAt) return;
    const d = new Date(data.generatedAt);
    document.getElementById('updateTime').textContent =
      'Last updated: ' + d.toLocaleString();
  }

  // --- Twitter Cards ---
  function renderTwitter(builders) {
    const container = document.getElementById('twitterCards');
    if (!builders || builders.length === 0) {
      container.innerHTML = emptyState('\uD83D\uDCED', 'No tweets today');
      return;
    }

    let cardIndex = 0;
    container.innerHTML = builders.map(builder => {
      return builder.tweets.map(tweet => {
        const initial = builder.name.charAt(0).toUpperCase();
        const timeAgo = formatTimeAgo(tweet.createdAt);
        const bioZh = builder.bio_zh || '';
        const summaryZh = tweet.summary_zh || '';
        const hasOriginal = tweet.text && tweet.text.trim();
        const idx = cardIndex++;

        return `
          <div class="card tweet-card">
            <div class="tweet-header">
              <div class="tweet-avatar">${initial}</div>
              <div class="tweet-author">
                <div class="tweet-name">${esc(builder.name)}</div>
                <div class="tweet-handle">@${esc(builder.handle)} &middot; ${timeAgo}</div>
                ${bioZh ? `<div class="tweet-bio">${esc(bioZh)}</div>` : ''}
              </div>
            </div>
            ${summaryZh
              ? `<div class="tweet-summary">${esc(summaryZh)}</div>`
              : `<div class="tweet-text">${linkify(esc(tweet.text))}</div>`
            }
            ${hasOriginal && summaryZh ? `
            <details class="tweet-original">
              <summary class="tweet-original-toggle">\u539F\u6587</summary>
              <div class="tweet-original-text">${linkify(esc(tweet.text))}</div>
            </details>` : ''}
            <div class="tweet-footer">
              <div class="tweet-stats">
                <span class="tweet-stat">\u2764\uFE0F ${formatNum(tweet.likes)}</span>
                <span class="tweet-stat">\uD83D\uDD01 ${formatNum(tweet.retweets)}</span>
                <span class="tweet-stat">\uD83D\uDCAC ${formatNum(tweet.replies)}</span>
              </div>
              <a class="tweet-link" href="${esc(tweet.url)}" target="_blank" rel="noopener">\u539F\u6587 &rarr;</a>
            </div>
          </div>
        `;
      }).join('');
    }).join('');
  }

  // --- Podcast Cards ---
  function renderPodcasts(podcasts) {
    const container = document.getElementById('podcastCards');
    if (!podcasts || podcasts.length === 0) {
      container.innerHTML = emptyState('\uD83C\uDFA7', 'No new episodes today');
      return;
    }

    container.innerHTML = podcasts.map(ep => {
      const videoId = ep.videoId ? esc(ep.videoId) : '';
      const thumbUrl = videoId
        ? `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`
        : '';
      const dateStr = ep.publishedAt
        ? new Date(ep.publishedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        : '';

      const summaryZh = ep.summary_zh || '';

      return `
        <div class="card podcast-card-v">
          <div class="podcast-meta">
            <span class="podcast-channel">${esc(ep.name)}</span>
            <span class="podcast-date">${dateStr}</span>
          </div>
          <div class="podcast-title"><a href="${esc(ep.url)}" target="_blank" rel="noopener">${esc(ep.title)}</a></div>
          ${summaryZh ? `<div class="podcast-summary">${esc(summaryZh)}</div>` : ''}
          ${videoId ? `
          <div class="podcast-player" data-video-id="${videoId}">
            <img class="podcast-thumb-img" src="${thumbUrl}" alt="${esc(ep.title)}" loading="lazy">
            <div class="play-overlay">
              <div class="play-btn">&#9654;</div>
            </div>
          </div>` : ''}
        </div>
      `;
    }).join('');

    // Click to replace thumbnail with YouTube iframe
    container.querySelectorAll('.podcast-player').forEach(player => {
      player.addEventListener('click', () => {
        const videoId = player.getAttribute('data-video-id');
        player.innerHTML = `<iframe class="podcast-iframe" src="https://www.youtube.com/embed/${videoId}?autoplay=1" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
      });
    });
  }

  // --- Product Hunt Cards ---
  function renderProductHunt(products) {
    const container = document.getElementById('phCards');
    if (!products || products.length === 0) {
      container.innerHTML = emptyState('\uD83D\uDE80', 'No products today');
      return;
    }

    container.innerHTML = products.map((p, i) => {
      const emoji = getProductEmoji(p.name);
      const summaryZh = p.summary_zh || '';
      return `
        <div class="card ph-card-v">
          <div class="ph-card-header">
            <div class="ph-rank">${i + 1}</div>
            <div class="ph-logo">${emoji}</div>
            <div class="ph-name-wrap">
              <div class="ph-name"><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a></div>
              <div class="ph-tagline">${esc(p.tagline)}</div>
            </div>
            <a class="ph-view" href="${esc(p.url)}" target="_blank" rel="noopener">
              <span class="ph-votes-arrow">\u25B2</span>
              <span>View</span>
            </a>
          </div>
          ${summaryZh ? `<div class="ph-summary">${esc(summaryZh)}</div>` : ''}
        </div>
      `;
    }).join('');
  }

  // --- GitHub Trending Cards ---
  function renderGitHub(repos) {
    const container = document.getElementById('githubCards');
    if (!repos || repos.length === 0) {
      container.innerHTML = emptyState('\uD83D\uDCBB', 'No trending repos today');
      return;
    }

    container.innerHTML = repos.map((r, i) => {
      const langClass = (r.language || '').toLowerCase().replace(/[^a-z]/g, '') || 'default';
      const summaryZh = r.summary_zh || '';
      return `
        <div class="card gh-card">
          <div class="gh-rank">${i + 1}</div>
          <div class="gh-info">
            <div class="gh-repo"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.repo)}</a></div>
            ${summaryZh ? `<div class="gh-summary">${esc(summaryZh)}</div>` : `<div class="gh-desc">${esc(r.description || '')}</div>`}
            <div class="gh-meta">
              <span class="gh-lang">
                <span class="gh-lang-dot ${langClass}"></span>
                ${esc(r.language || 'Unknown')}
              </span>
              <span class="gh-stars">\u2B50 ${formatNum(r.stars)}</span>
              ${r.starsToday ? `<span class="gh-stars-today">+${formatNum(r.starsToday)} today</span>` : ''}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  // --- Helpers ---
  function esc(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  function linkify(text) {
    return text.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  }

  function formatNum(n) {
    if (n === undefined || n === null) return '0';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }

  function formatTimeAgo(dateStr) {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return mins + 'm ago';
    const hours = Math.floor(mins / 60);
    if (hours < 24) return hours + 'h ago';
    const days = Math.floor(hours / 24);
    return days + 'd ago';
  }

  function getProductEmoji(name) {
    const n = (name || '').toLowerCase();
    if (n.includes('cursor') || n.includes('code')) return '\uD83D\uDCBB';
    if (n.includes('music') || n.includes('audio') || n.includes('eleven')) return '\uD83C\uDFB5';
    if (n.includes('notion') || n.includes('note')) return '\uD83D\uDCDD';
    if (n.includes('replit') || n.includes('deploy')) return '\uD83D\uDE80';
    if (n.includes('design') || n.includes('figma')) return '\uD83C\uDFA8';
    if (n.includes('video') || n.includes('film')) return '\uD83C\uDFAC';
    return '\u2728';
  }

  function emptyState(icon, text) {
    return `
      <div class="empty-state">
        <div class="empty-state-icon">${icon}</div>
        <p>${text}</p>
      </div>
    `;
  }

  // --- Init ---
  async function init() {
    initTheme();
    initNav();
    renderDate();

    try {
      const res = await fetch(FEED_URL);
      const data = await res.json();

      renderStats(data);
      renderUpdateTime(data);
      renderTwitter(data.twitter);
      renderPodcasts(data.podcasts);
      renderProductHunt(data.producthunt);
      renderGitHub(data.github_trending);
    } catch (err) {
      console.error('Failed to load feed:', err);
      document.getElementById('twitterCards').innerHTML =
        emptyState('\u26A0\uFE0F', 'Failed to load data. Try refreshing.');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
