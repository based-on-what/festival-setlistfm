const selectedArtists = [];
let searchTimeout = null;

async function checkAuth() {
  const res = await fetch("/api/auth-status");
  const data = await res.json();
  if (data.authenticated) {
    document.getElementById("login-btn").classList.add("hidden");
    document.getElementById("logout-area").classList.remove("hidden");
    document.getElementById("main-content").classList.remove("hidden");
    document.getElementById("auth-notice").classList.add("hidden");
  } else {
    document.getElementById("login-btn").classList.remove("hidden");
    document.getElementById("logout-area").classList.add("hidden");
    document.getElementById("main-content").classList.add("hidden");
    document.getElementById("auth-notice").classList.remove("hidden");
  }
}

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
  if (!e.target.closest(".search-box") && !e.target.closest(".dropdown")) {
    document.getElementById("search-results").classList.add("hidden");
  }
});

async function searchArtists(q) {
  clearError("search-error");
  try {
    const res = await fetch(`/api/search-artist?q=${encodeURIComponent(q)}`);
    document.getElementById("search-spinner").classList.add("hidden");
    if (res.status === 401) {
      showError("search-error", "Session expired. Please reconnect Spotify.");
      return;
    }
    const data = await res.json();
    if (data.error) {
      showError("search-error", "Search failed. Try again.");
      return;
    }
    renderDropdown(data.artists || []);
  } catch {
    document.getElementById("search-spinner").classList.add("hidden");
    showError("search-error", "Network error. Try again.");
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
    const thumb = artist.image
      ? `<img class="dropdown-thumb" src="${artist.image}" alt="" loading="lazy" />`
      : `<div class="dropdown-thumb-placeholder">🎤</div>`;
    item.innerHTML = `${thumb}<span class="dropdown-name">${escapeHtml(artist.name)}</span>`;
    item.addEventListener("click", () => addArtist(artist));
    container.appendChild(item);
  });
  container.classList.remove("hidden");
}

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

function renderArtistList() {
  const list = document.getElementById("artist-list");
  const empty = document.getElementById("empty-list-msg");
  const createBtn = document.getElementById("create-btn");
  list.innerHTML = "";

  if (!selectedArtists.length) {
    empty.classList.remove("hidden");
    createBtn.classList.add("hidden");
    return;
  }

  empty.classList.add("hidden");
  createBtn.classList.remove("hidden");

  selectedArtists.forEach((artist) => {
    const li = document.createElement("li");
    li.className = "artist-item";
    const thumb = artist.image
      ? `<img class="artist-item-thumb" src="${artist.image}" alt="" loading="lazy" />`
      : `<div class="artist-item-thumb-placeholder">🎤</div>`;
    li.innerHTML = `
      ${thumb}
      <span class="artist-item-name">${escapeHtml(artist.name)}</span>
      <button class="remove-btn" title="Remove" onclick="removeArtist('${artist.id}')">✕</button>
    `;
    list.appendChild(li);
  });
}

async function createPlaylist() {
  clearError("create-error");
  const btn = document.getElementById("create-btn");
  const label = document.getElementById("create-label");
  const spinner = document.getElementById("create-spinner");

  btn.disabled = true;
  label.textContent = "Building playlist…";
  spinner.classList.remove("hidden");

  try {
    const res = await fetch("/api/create-playlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ artists: selectedArtists }),
    });

    const data = await res.json();

    if (!res.ok) {
      const msg =
        data.error === "no_tracks_found"
          ? "No matching tracks found on Spotify for any artist."
          : data.error === "not_authenticated"
          ? "Session expired. Please reconnect Spotify."
          : "Failed to create playlist. Please try again.";
      showError("create-error", msg);
      return;
    }

    showResult(data);
  } catch {
    showError("create-error", "Network error. Please try again.");
  } finally {
    btn.disabled = false;
    label.textContent = "Create Festival Setlist";
    spinner.classList.add("hidden");
  }
}

function showResult(data) {
  document.getElementById("artists-card").classList.add("hidden");

  const resultCard = document.getElementById("result-card");
  resultCard.classList.remove("hidden");

  const link = document.getElementById("playlist-link");
  link.href = data.playlist_url;

  const summary = document.getElementById("artist-summary");
  summary.innerHTML = "";
  (data.artists || []).forEach((a) => {
    const item = document.createElement("div");
    item.className = "summary-item";
    const statusClass = a.status === "ok" ? "status-ok" : "status-warn";
    const statusText =
      a.status === "ok" ? `${a.tracks} tracks` : "No setlist found";
    item.innerHTML = `
      <span>${escapeHtml(a.name)}</span>
      <span class="${statusClass}">${statusText}</span>
    `;
    summary.appendChild(item);
  });

  const player = document.getElementById("player-wrap");
  player.innerHTML = `<iframe
    src="https://open.spotify.com/embed/playlist/${data.playlist_id}?utm_source=generator&theme=0"
    height="352"
    allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
    loading="lazy">
  </iframe>`;
}

function resetResult() {
  selectedArtists.length = 0;
  renderArtistList();
  document.getElementById("result-card").classList.add("hidden");
  document.getElementById("artists-card").classList.remove("hidden");
  document.getElementById("player-wrap").innerHTML = "";
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

checkAuth();
