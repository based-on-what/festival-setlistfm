import { ArtistStore }    from './store.js';
import { Toast }          from './components/toast.js';
import { SearchDropdown } from './components/dropdown.js';
import { createArtistItem } from './components/artist-item.js';
import { escapeHtml, todayFormatted } from './components/utils.js';

// ── Error catalog ─────────────────────────────────────────────────────────────

const ERROR_MESSAGES = {
  setlistfm_not_configured:         'The server is missing its setlist.fm API key. Contact the site admin.',
  setlistfm_api_key_invalid:        'The setlist.fm API key is invalid or expired. Contact the site admin.',
  setlistfm_rate_limited:           'Too many requests to setlist.fm. Wait a moment and try again.',
  setlistfm_quota_exceeded:         "The site's daily setlist.fm quota is used up. Try again tomorrow.",
  setlistfm_timeout:                'setlist.fm took too long to respond. Check your connection and try again.',
  setlistfm_connection_error:       'Could not reach setlist.fm. Check your internet connection.',
  setlistfm_error:                  'setlist.fm returned an unexpected error. Try again in a moment.',
  spotify_not_configured:           'The server is missing Spotify credentials. Contact the site admin.',
  spotify_refresh_token_missing:    'Spotify refresh token not configured on the server. Contact the site admin.',
  spotify_refresh_token_invalid:    'Spotify session has expired. The site admin needs to re-authorize the app.',
  spotify_credentials_invalid:      'The Spotify client ID or secret is incorrect. Contact the site admin.',
  spotify_auth_timeout:             'Spotify authentication timed out. Try again in a moment.',
  spotify_auth_connection_error:    'Could not reach Spotify to authenticate. Check your internet connection.',
  spotify_token_expired:            'Spotify session expired mid-request. Reload the page and try again.',
  spotify_network_error:            'A network error occurred while talking to Spotify. Try again.',
  spotify_could_not_get_user:       "Couldn't fetch your Spotify profile. Make sure the app has permission.",
  spotify_playlist_creation_failed: 'Spotify rejected the playlist creation. Check app permissions and try again.',
  no_artists:                       'Add at least one artist first.',
  too_many_artists:                 'Too many artists. Please remove some and try again.',
  no_tracks_found:                  'No tracks were found on Spotify for any of the selected artists.',
  job_not_found:                    'The playlist job expired or was lost (e.g. server restart). Try again.',
};

function friendlyError(code, fallback) {
  if (!code) return fallback || 'An unexpected error occurred. Please try again.';
  if (/_(http|auth_http)_\d{3}$/.test(code)) {
    const status = code.match(/\d{3}$/)[0];
    return `Remote API returned an error (HTTP ${status}). Try again in a moment.`;
  }
  return ERROR_MESSAGES[code] || fallback || `Unexpected error: ${code}`;
}

// ── State ─────────────────────────────────────────────────────────────────────

const store = new ArtistStore();
let searchTimeout      = null;
let searchController   = null;
let loadMoreController = null;
let currentSearchQuery = '';
let currentSearchPage  = 1;
let dragSrcIndex  = null;
let swapSrcIndex  = null;

// ── DOM refs (module is deferred, so DOM is ready) ────────────────────────────

const artistInput   = document.getElementById('artist-input');
const artistListEl  = document.getElementById('artist-list');
const emptyMsg      = document.getElementById('empty-list-msg');
const createBtn     = document.getElementById('create-btn');
const createLabel   = document.getElementById('create-label');
const createSpinner = document.getElementById('create-spinner');
const optionsGroup  = document.getElementById('options-group');
const announcer     = document.getElementById('announcer');
const builderEl     = document.getElementById('builder');
const lineupCount   = document.getElementById('lineup-count');
const maxArtists    = parseInt(lineupCount.dataset.max, 10);

// ── Helpers ───────────────────────────────────────────────────────────────────

function announce(msg) {
  announcer.textContent = '';
  requestAnimationFrame(() => { announcer.textContent = msg; });
}

// ── Theme ─────────────────────────────────────────────────────────────────────

(function initTheme() {
  const btn = document.getElementById('theme-toggle');
  // Label shows the theme the button switches TO, ticket-stub style.
  const apply = (theme) => {
    document.documentElement.setAttribute('data-theme', theme);
    btn.setAttribute('aria-pressed', String(theme === 'light'));
    btn.textContent = theme === 'dark' ? 'Day' : 'Night';
  };
  apply(localStorage.getItem('festival-theme') || 'dark');
  btn.addEventListener('click', () => {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    localStorage.setItem('festival-theme', next);
    apply(next);
  });
})();

document.getElementById('playlist-name-input').placeholder = `Festival Setlist – ${todayFormatted()}`;

// ── Search ────────────────────────────────────────────────────────────────────

const dropdown = new SearchDropdown('search-results', 'artist-input', (artist) => {
  artistInput.value = '';
  if (store.add(artist)) {
    announce(`${artist.name} added to lineup`);
  }
  artistInput.focus();
});

artistInput.addEventListener('input', (e) => {
  clearTimeout(searchTimeout);
  const q = e.target.value.trim();
  if (!q) {
    dropdown.close();
    return;
  }
  searchTimeout = setTimeout(() => searchArtists(q), 350);
});

artistInput.addEventListener('keydown', (e) => {
  dropdown.handleKeydown(e);
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('.search-box') && !e.target.closest('.dropdown')) {
    dropdown.close();
  }
});

async function searchArtists(q, page = 1) {
  if (page === 1) {
    searchController?.abort();
    loadMoreController?.abort();
    searchController   = new AbortController();
    currentSearchQuery = q;
    currentSearchPage  = 1;
    dropdown.showSkeleton();
  } else {
    loadMoreController?.abort();
    loadMoreController = new AbortController();
    dropdown.setLoadMoreLoading(true);
  }

  const controller = page === 1 ? searchController : loadMoreController;

  try {
    const res  = await fetch(`/api/search-artist?q=${encodeURIComponent(q)}&p=${page}`, {
      signal: controller.signal,
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      if (page === 1) dropdown.hideSkeleton();
      else dropdown.setLoadMoreLoading(false);
      Toast.error(friendlyError(data.error, 'Artist search failed. Try again.'));
      return;
    }
    currentSearchPage = page;
    dropdown.render(data.artists || [], {
      append:     page > 1,
      hasMore:    data.has_more,
      onLoadMore: () => searchArtists(currentSearchQuery, currentSearchPage + 1),
    });
  } catch (err) {
    if (err.name === 'AbortError') return;
    if (page === 1) dropdown.hideSkeleton();
    else dropdown.setLoadMoreLoading(false);
    Toast.error('Network error. Check your connection and try again.');
  }
}

// ── Artist list ───────────────────────────────────────────────────────────────

store.addEventListener('change', renderArtistList);

function renderArtistList() {
  const artists = store.artists;
  artistListEl.innerHTML = '';
  lineupCount.textContent = `${artists.length}/${maxArtists}`;

  if (!artists.length) {
    emptyMsg.classList.remove('hidden');
    createBtn.classList.add('hidden');
    optionsGroup.classList.add('hidden');
    return;
  }

  emptyMsg.classList.add('hidden');
  createBtn.classList.remove('hidden');
  optionsGroup.classList.remove('hidden');

  const frag = document.createDocumentFragment();

  artists.forEach((artist, index) => {
    const li = createArtistItem(artist, index, { isSwapSelected: swapSrcIndex === index });
    attachDragHandlers(li, index);
    frag.appendChild(li);
  });

  artistListEl.appendChild(frag);
}

function attachDragHandlers(li, index) {
  li.addEventListener('dragstart', (e) => {
    dragSrcIndex = index;
    e.dataTransfer.effectAllowed = 'move';
    setTimeout(() => li.classList.add('dragging'), 0);
  });
  li.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    li.classList.add('drag-over');
  });
  li.addEventListener('dragleave', () => li.classList.remove('drag-over'));
  li.addEventListener('drop', (e) => {
    e.preventDefault();
    li.classList.remove('drag-over');
    if (dragSrcIndex === null || dragSrcIndex === index) return;
    store.move(dragSrcIndex, index);
    dragSrcIndex = null;
  });
  li.addEventListener('dragend', () => {
    dragSrcIndex = null;
    document.querySelectorAll('.artist-item').forEach(el =>
      el.classList.remove('dragging', 'drag-over')
    );
  });
}

// Delegated: remove + swap click, swap keyboard
artistListEl.addEventListener('click', (e) => {
  const target = e.target.closest('[data-action]');
  if (!target) return;
  e.stopPropagation();
  if (target.dataset.action === 'remove') {
    const removed = store.remove(target.dataset.id);
    if (removed) announce(`${removed.name} removed from lineup`);
  } else if (target.dataset.action === 'swap') {
    handleSwapTap(parseInt(target.dataset.index, 10));
  }
});

artistListEl.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const target = e.target.closest('[data-action="swap"]');
  if (!target) return;
  e.preventDefault();
  target.click();
});

function handleSwapTap(index) {
  if (swapSrcIndex === null) {
    swapSrcIndex = index;
    renderArtistList();
  } else if (swapSrcIndex === index) {
    swapSrcIndex = null;
    renderArtistList();
  } else {
    store.move(swapSrcIndex, index);
    swapSrcIndex = null;
    // store 'change' → renderArtistList
  }
}

// ── Create playlist ───────────────────────────────────────────────────────────

createBtn.addEventListener('click', createPlaylist);

async function createPlaylist() {
  const preferOriginal = document.getElementById('opt-prefer-original').checked;
  const includeTaped   = document.getElementById('opt-include-taped').checked;
  const playlistName   = document.getElementById('playlist-name-input').value.trim();

  createBtn.disabled = true;
  createBtn.setAttribute('aria-busy', 'true');
  createLabel.textContent = 'Building playlist…';
  createSpinner.classList.remove('hidden');

  try {
    const res  = await fetch('/api/create-playlist', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        artists:         store.artists,
        prefer_original: preferOriginal,
        include_taped:   includeTaped,
        playlist_name:   playlistName,
      }),
    });

    const data = await res.json();
    if (!res.ok && res.status !== 202) {
      Toast.error(friendlyError(data.error));
      return;
    }
    // 202 + job_id: poll until done. Plain 200 kept as fallback shape.
    const result = data.job_id ? await pollJob(data.job_id) : data;
    showResult(result);
  } catch (err) {
    if (err?.errorCode !== undefined) {
      Toast.error(friendlyError(err.errorCode));
    } else {
      Toast.error('Network error. Check your connection and try again.');
    }
  } finally {
    createBtn.disabled = false;
    createBtn.removeAttribute('aria-busy');
    createLabel.textContent = 'Create the playlist';
    createSpinner.classList.add('hidden');
  }
}

const POLL_INTERVAL_MS = 2000;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Polls /api/playlist-status until the job finishes. Resolves with the build
// result; rejects with { errorCode } on job failure.
async function pollJob(jobId) {
  for (;;) {
    await sleep(POLL_INTERVAL_MS);
    const res  = await fetch(`/api/playlist-status/${jobId}`);
    const data = await res.json();
    if (!res.ok || data.state === 'error') {
      throw { errorCode: data.error };
    }
    if (data.state === 'done') return data.result;
    const p = data.progress;
    if (p?.total) {
      createLabel.textContent = `Building playlist… ${p.completed}/${p.total} artists`;
    }
  }
}

// ── Result display ────────────────────────────────────────────────────────────

function showResult(data) {
  builderEl.classList.add('hidden');
  document.getElementById('result-card').classList.remove('hidden');
  document.getElementById('playlist-link').href = data.playlist_url;
  announce('Playlist ready');

  const warningBox = document.getElementById('warning-box');
  warningBox.innerHTML = '';

  const noSetlist = (data.artists || []).filter(a => a.status === 'no_setlist');
  const noTracks  = (data.artists || []).filter(a => a.status === 'no_tracks');
  const timedOut  = (data.artists || []).filter(a => a.status === 'timeout');
  const missing   = (data.artists || []).filter(a => a.missing?.length > 0);
  const warnings  = [];

  if (timedOut.length) {
    warnings.push(`
      <div class="warning-row">
        <span class="warning-artist">⏱ Ran out of time processing:</span>
        <span class="warning-songs">${timedOut.map(a => escapeHtml(a.name)).join(', ')}</span>
      </div>`);
  }

  if (noSetlist.length) {
    warnings.push(`
      <div class="warning-row">
        <span class="warning-artist">📭 No recent setlist found for:</span>
        <span class="warning-songs">${noSetlist.map(a => escapeHtml(a.name)).join(', ')}</span>
      </div>`);
  }
  if (noTracks.length) {
    warnings.push(`
      <div class="warning-row">
        <span class="warning-artist">🔇 Setlist found but no Spotify tracks for:</span>
        <span class="warning-songs">${noTracks.map(a => escapeHtml(a.name)).join(', ')}</span>
      </div>`);
  }
  if (missing.length) {
    const rows = missing.map(a => `
      <div class="warning-row">
        <span class="warning-artist">🎤 ${escapeHtml(a.name)}</span>
        <span class="warning-songs">${a.missing.map(s => `"${escapeHtml(s)}"`).join(', ')}</span>
      </div>`).join('');
    warnings.push(`
      <div class="warning-row">
        <span class="warning-artist">⚠️ Some tracks couldn't be found on Spotify:</span>
      </div>${rows}`);
  }
  if (data.failed_chunks > 0) {
    warnings.push(`
      <div class="warning-row">
        <span class="warning-artist">⚠️ Some tracks may be missing</span>
        <span class="warning-songs">Spotify rejected ${data.failed_chunks} batch(es) during upload. The playlist was created but may be incomplete.</span>
      </div>`);
  }

  if (warnings.length) {
    warningBox.innerHTML = `<div class="warning-title">Heads up:</div>${warnings.join('')}`;
    warningBox.classList.remove('hidden');
  } else {
    warningBox.classList.add('hidden');
  }

  const summary     = document.getElementById('artist-summary');
  const summaryFrag = document.createDocumentFragment();
  (data.artists || []).forEach(a => {
    const item = document.createElement('div');
    item.className = 'summary-item';

    let statusClass, statusText;
    if (a.status === 'ok') {
      statusClass = 'status-ok';
      statusText  = `${a.tracks} track${a.tracks !== 1 ? 's' : ''}`;
    } else if (a.status === 'no_tracks') {
      statusClass = 'status-warn';
      statusText  = 'Setlist found, no tracks on Spotify';
    } else if (a.status === 'timeout') {
      statusClass = 'status-warn';
      statusText  = 'Timed out';
    } else {
      statusClass = 'status-warn';
      statusText  = 'No recent setlist';
    }

    const nameEl   = document.createElement('span');
    nameEl.textContent = a.name;
    const statusEl = document.createElement('span');
    statusEl.className   = statusClass;
    statusEl.textContent = statusText;
    item.appendChild(nameEl);
    item.appendChild(statusEl);
    summaryFrag.appendChild(item);
  });
  summary.innerHTML = '';
  summary.appendChild(summaryFrag);

  const safeId = String(data.playlist_id).replace(/[^a-zA-Z0-9]/g, '');
  const iframe  = document.createElement('iframe');
  iframe.src    = `https://open.spotify.com/embed/playlist/${safeId}?utm_source=generator&theme=0`;
  iframe.height = '352';
  iframe.title  = 'Spotify playlist player';
  iframe.setAttribute('allow', 'autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture; web-share');
  iframe.setAttribute('loading', 'lazy');
  document.getElementById('player-wrap').appendChild(iframe);
}

document.getElementById('reset-btn').addEventListener('click', resetResult);

function resetResult() {
  store.clear();
  swapSrcIndex = null;
  document.getElementById('playlist-name-input').value = '';
  document.getElementById('result-card').classList.add('hidden');
  builderEl.classList.remove('hidden');
  document.getElementById('player-wrap').innerHTML = '';
  document.getElementById('warning-box').classList.add('hidden');
}

// Initial render
renderArtistList();
