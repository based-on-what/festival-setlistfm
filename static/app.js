const selectedArtists = [];
let searchTimeout = null;
let dragSrcIndex  = null;
let swapSrcIndex  = null;

// ── Error messages (FIX: mapa completo de códigos → mensajes legibles) ─────────

const ERROR_MESSAGES = {
  // setlist.fm
  setlistfm_not_configured:    "The server is missing its setlist.fm API key. Contact the site admin.",
  setlistfm_api_key_invalid:   "The setlist.fm API key is invalid or expired. Contact the site admin.",
  setlistfm_rate_limited:      "Too many requests to setlist.fm. Wait a moment and try again.",
  setlistfm_timeout:           "setlist.fm took too long to respond. Check your connection and try again.",
  setlistfm_connection_error:  "Could not reach setlist.fm. Check your internet connection.",
  setlistfm_error:             "setlist.fm returned an unexpected error. Try again in a moment.",

  // Spotify auth
  spotify_not_configured:         "The server is missing Spotify credentials. Contact the site admin.",
  spotify_refresh_token_missing:  "Spotify refresh token not configured on the server. Contact the site admin.",
  spotify_refresh_token_invalid:  "Spotify session has expired. The site admin needs to re-authorize the app.",
  spotify_credentials_invalid:    "The Spotify client ID or secret is incorrect. Contact the site admin.",
  spotify_auth_timeout:           "Spotify authentication timed out. Try again in a moment.",
  spotify_auth_connection_error:  "Could not reach Spotify to authenticate. Check your internet connection.",
  spotify_token_expired:          "Spotify session expired mid-request. Reload the page and try again.",
  spotify_network_error:          "A network error occurred while talking to Spotify. Try again.",

  // Playlist creation
  spotify_could_not_get_user:        "Couldn't fetch your Spotify profile. Make sure the app has permission.",
  spotify_playlist_creation_failed:  "Spotify rejected the playlist creation. Check app permissions and try again.",

  // Generic
  no_artists:      "Add at least one artist first.",
  no_tracks_found: "No tracks were found on Spotify for any of the selected artists.",
};

function friendlyError(code, fallback) {
  if (!code) return fallback || "An unexpected error occurred. Please try again.";
  // FIX: si el código tiene prefijo http (ej. "setlistfm_http_500"), mensaje genérico con el código
  if (/_(http|auth_http)_\d{3}$/.test(code)) {
    const status = code.match(/\d{3}$/)[0];
    return `Remote API returned an error (HTTP ${status}). Try again in a moment.`;
  }
  return ERROR_MESSAGES[code] || fallback || `Unexpected error: ${code}`;
}

// ── Helpers ─────────────────────────────────────────────────────────────────────

function todayFormatted() {
  const d    = new Date();
  const dd   = String(d.getDate()).padStart(2, "0");
  const mm   = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

(function initTheme() {
  const saved = localStorage.getItem("festival-theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const next =
      document.documentElement.getAttribute("data-theme") === "dark"
        ? "light"
        : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("festival-theme", next);
  });
})();

document.getElementById("playlist-name-input").placeholder =
  `Festival Setlist – ${todayFormatted()}`;

function showError(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearError(id) {
  const el = document.getElementById(id);
  el.textContent = "";
  el.classList.add("hidden");
}

// ── Search (powered by setlist.fm) ────────────────────────────────────────────

document.getElementById("artist-input").addEventListener("input", (e) => {
  clearTimeout(searchTimeout);
  const q = e.target.value.trim();
  if (!q) {
    document.getElementById("search-results").classList.add("hidden");
    document.getElementById("search-spinner").classList.add("hidden");
    return;
  }
  document.getElementById("search-spinner").classList.remove("hidden");
  searchTimeout = setTimeout(() => searchArtists(q), 350);
});

document.getElementById("artist-input").addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.getElementById("search-results").classList.add("hidden");
  }
});

document.addEventListener("click", (e) => {
  if (
    !e.target.closest(".search-box") &&
    !e.target.closest(".dropdown")
  ) {
    document.getElementById("search-results").classList.add("hidden");
  }
});

async function searchArtists(q) {
  clearError("search-error");
  try {
    const res  = await fetch(`/api/search-artist?q=${encodeURIComponent(q)}`);
    document.getElementById("search-spinner").classList.add("hidden");
    const data = await res.json();

    if (!res.ok || data.error) {
      // FIX: antes mostraba el código crudo; ahora muestra mensaje legible
      showError("search-error", friendlyError(data.error, "Artist search failed. Try again."));
      return;
    }

    renderDropdown(data.artists || []);
  } catch {
    document.getElementById("search-spinner").classList.add("hidden");
    showError("search-error", "Network error. Check your connection and try again.");
  }
}

function renderDropdown(artists) {
  const container = document.getElementById("search-results");
  container.innerHTML = "";
  if (!artists.length) {
    container.classList.add("hidden");
    return;
  }
  artists.forEach((artist) => {
    const item = document.createElement("div");
    item.className = "dropdown-item";
    const thumb = `<div class="dropdown-thumb-placeholder">🎤</div>`;
    const sub   = artist.disambiguation
      ? `<span class="dropdown-meta">${escapeHtml(artist.disambiguation)}</span>`
      : "";
    item.innerHTML = `${thumb}<div class="dropdown-info"><span class="dropdown-name">${escapeHtml(
      artist.name
    )}</span>${sub}</div>`;
    item.addEventListener("click", () => addArtist(artist));
    container.appendChild(item);
  });
  container.classList.remove("hidden");
}

// ── Artist list management ─────────────────────────────────────────────────────

function addArtist(artist) {
  if (selectedArtists.find((a) => a.id === artist.id)) {
    document.getElementById("search-results").classList.add("hidden");
    document.getElementById("artist-input").value = "";
    return;
  }
  selectedArtists.push(artist);
  renderArtistList();
  document.getElementById("search-results").classList.add("hidden");
  document.getElementById("artist-input").value = "";
  clearError("search-error");
}

function removeArtist(id) {
  const idx = selectedArtists.findIndex((a) => a.id === id);
  if (idx !== -1) selectedArtists.splice(idx, 1);
  renderArtistList();
}

function handleSwapTap(index) {
  if (swapSrcIndex === null) {
    swapSrcIndex = index;
    renderArtistList();
  } else if (swapSrcIndex === index) {
    swapSrcIndex = null;
    renderArtistList();
  } else {
    const tmp                    = selectedArtists[swapSrcIndex];
    selectedArtists[swapSrcIndex] = selectedArtists[index];
    selectedArtists[index]        = tmp;
    swapSrcIndex                  = null;
    renderArtistList();
  }
}

function renderArtistList() {
  const list         = document.getElementById("artist-list");
  const empty        = document.getElementById("empty-list-msg");
  const createBtn    = document.getElementById("create-btn");
  const optionsGroup = document.getElementById("options-group");
  list.innerHTML = "";

  if (!selectedArtists.length) {
    empty.classList.remove("hidden");
    createBtn.classList.add("hidden");
    optionsGroup.classList.add("hidden");
    return;
  }

  empty.classList.add("hidden");
  createBtn.classList.remove("hidden");
  optionsGroup.classList.remove("hidden");

  selectedArtists.forEach((artist, index) => {
    const li              = document.createElement("li");
    li.className          = "artist-item";
    li.draggable          = true;
    const isSwapSelected  = swapSrcIndex === index;
    const thumb           = `<div class="artist-item-thumb-placeholder">🎤</div>`;

    li.innerHTML = `
      <span class="drag-handle${isSwapSelected ? " swap-selected" : ""}" title="Drag to reorder">⠿</span>
      ${thumb}
      <span class="artist-item-name">${escapeHtml(artist.name)}</span>
      <button class="remove-btn" title="Remove" onclick="removeArtist('${escapeHtml(
        artist.id
      )}')">✕</button>
    `;

    const handle = li.querySelector(".drag-handle");
    handle.addEventListener("click", (e) => {
      e.stopPropagation();
      handleSwapTap(index);
    });

    li.addEventListener("dragstart", (e) => {
      dragSrcIndex = index;
      e.dataTransfer.effectAllowed = "move";
      setTimeout(() => li.classList.add("dragging"), 0);
    });
    li.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      li.classList.add("drag-over");
    });
    li.addEventListener("dragleave", () => li.classList.remove("drag-over"));
    li.addEventListener("drop", (e) => {
      e.preventDefault();
      li.classList.remove("drag-over");
      if (dragSrcIndex === null || dragSrcIndex === index) return;
      const [moved] = selectedArtists.splice(dragSrcIndex, 1);
      selectedArtists.splice(index, 0, moved);
      dragSrcIndex = null;
      renderArtistList();
    });
    li.addEventListener("dragend", () => {
      dragSrcIndex = null;
      document.querySelectorAll(".artist-item").forEach((el) => {
        el.classList.remove("dragging", "drag-over");
      });
    });

    list.appendChild(li);
  });
}

// ── Create playlist ────────────────────────────────────────────────────────────

async function createPlaylist() {
  clearError("create-error");
  const btn          = document.getElementById("create-btn");
  const label        = document.getElementById("create-label");
  const spinner      = document.getElementById("create-spinner");
  const preferOriginal = document.getElementById("opt-prefer-original").checked;
  const includeTaped   = document.getElementById("opt-include-taped").checked;
  const playlistName   = document.getElementById("playlist-name-input").value.trim();

  btn.disabled       = true;
  label.textContent  = "Building playlist…";
  spinner.classList.remove("hidden");

  try {
    const res  = await fetch("/api/create-playlist", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        artists:         selectedArtists,
        prefer_original: preferOriginal,
        include_taped:   includeTaped,
        playlist_name:   playlistName,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      // FIX: antes usaba un switch manual incompleto; ahora usa el mapa centralizado
      showError("create-error", friendlyError(data.error));
      return;
    }

    showResult(data);
  } catch {
    showError("create-error", "Network error. Check your connection and try again.");
  } finally {
    btn.disabled      = false;
    label.textContent = "Create Festival Setlist";
    spinner.classList.add("hidden");
  }
}

// ── Result display ─────────────────────────────────────────────────────────────

function showResult(data) {
  document.getElementById("artists-card").classList.add("hidden");

  const resultCard = document.getElementById("result-card");
  resultCard.classList.remove("hidden");

  document.getElementById("playlist-link").href = data.playlist_url;

  const warningBox = document.getElementById("warning-box");
  warningBox.innerHTML = "";

  const warnings = [];

  // FIX: antes sólo se avisaba de missing tracks; ahora también de artistas sin setlist
  const noSetlist = (data.artists || []).filter((a) => a.status === "no_setlist");
  const noTracks  = (data.artists || []).filter((a) => a.status === "no_tracks");
  const missing   = (data.artists || []).filter((a) => a.missing && a.missing.length > 0);

  if (noSetlist.length) {
    warnings.push(`
      <div class="warning-row">
        <span class="warning-artist">📭 No recent setlist found for:</span>
        <span class="warning-songs">${noSetlist.map((a) => escapeHtml(a.name)).join(", ")}</span>
      </div>`);
  }

  if (noTracks.length) {
    warnings.push(`
      <div class="warning-row">
        <span class="warning-artist">🔇 Setlist found but no Spotify tracks for:</span>
        <span class="warning-songs">${noTracks.map((a) => escapeHtml(a.name)).join(", ")}</span>
      </div>`);
  }

  if (missing.length) {
    const rows = missing
      .map((a) => {
        const songList = a.missing.map((s) => `"${escapeHtml(s)}"`).join(", ");
        return `<div class="warning-row">
          <span class="warning-artist">🎤 ${escapeHtml(a.name)}</span>
          <span class="warning-songs">${songList}</span>
        </div>`;
      })
      .join("");
    warnings.push(`
      <div class="warning-row">
        <span class="warning-artist">⚠️ Some tracks couldn't be found on Spotify:</span>
      </div>
      ${rows}`);
  }

  // FIX: avisa si algún chunk de tracks falló al insertarse en la playlist
  if (data.failed_chunks > 0) {
    warnings.push(`
      <div class="warning-row">
        <span class="warning-artist">⚠️ Some tracks may be missing</span>
        <span class="warning-songs">Spotify rejected ${data.failed_chunks} batch(es) during upload. The playlist was created but may be incomplete.</span>
      </div>`);
  }

  if (warnings.length) {
    warningBox.innerHTML = `<div class="warning-title">Heads up:</div>${warnings.join("")}`;
    warningBox.classList.remove("hidden");
  } else {
    warningBox.classList.add("hidden");
  }

  // ── Artist summary ──
  const summary = document.getElementById("artist-summary");
  summary.innerHTML = "";
  (data.artists || []).forEach((a) => {
    const item        = document.createElement("div");
    item.className    = "summary-item";

    // FIX: antes "no_tracks" y "no_setlist" mostraban el mismo texto genérico
    let statusClass, statusText;
    if (a.status === "ok") {
      statusClass = "status-ok";
      statusText  = `${a.tracks} track${a.tracks !== 1 ? "s" : ""}`;
    } else if (a.status === "no_tracks") {
      statusClass = "status-warn";
      statusText  = "Setlist found, no tracks on Spotify";
    } else {
      statusClass = "status-warn";
      statusText  = "No recent setlist";
    }

    item.innerHTML = `
      <span>${escapeHtml(a.name)}</span>
      <span class="${statusClass}">${statusText}</span>
    `;
    summary.appendChild(item);
  });

  document.getElementById("player-wrap").innerHTML = `<iframe
    src="https://open.spotify.com/embed/playlist/${data.playlist_id}?utm_source=generator&theme=0"
    height="352"
    allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture; web-share"
    loading="lazy">
  </iframe>`;
}

function resetResult() {
  selectedArtists.length = 0;
  swapSrcIndex           = null;
  document.getElementById("playlist-name-input").value = "";
  renderArtistList();
  document.getElementById("result-card").classList.add("hidden");
  document.getElementById("artists-card").classList.remove("hidden");
  document.getElementById("player-wrap").innerHTML = "";
  document.getElementById("warning-box").classList.add("hidden");
}

// ── Utils ──────────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}