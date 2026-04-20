const selectedArtists = [];
let searchTimeout = null;
let dragSrcIndex = null;

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
  if (
    !e.target.closest(".search-box") &&
    !e.target.closest(".dropdown")
  ) {
    document.getElementById("search-results").classList.add("hidden");
  }
});

// ── Search (powered by setlist.fm) ────────────────────────────────────────────

async function searchArtists(q) {
  clearError("search-error");
  try {
    const res = await fetch(`/api/search-artist?q=${encodeURIComponent(q)}`);
    document.getElementById("search-spinner").classList.add("hidden");
    const data = await res.json();
    if (!res.ok || data.error) {
      showError("search-error", data.error || "Search failed. Try again.");
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

    const thumb = `<div class="dropdown-thumb-placeholder">🎤</div>`;
    const sub = artist.disambiguation
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

function renderArtistList() {
  const list = document.getElementById("artist-list");
  const empty = document.getElementById("empty-list-msg");
  const createBtn = document.getElementById("create-btn");
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
    const li = document.createElement("li");
    li.className = "artist-item";
    li.draggable = true;

    const thumb = `<div class="artist-item-thumb-placeholder">🎤</div>`;

    li.innerHTML = `
      <span class="drag-handle" title="Drag to reorder">⠿</span>
      ${thumb}
      <span class="artist-item-name">${escapeHtml(artist.name)}</span>
      <button class="remove-btn" title="Remove" onclick="removeArtist('${escapeHtml(
        artist.id
      )}')">✕</button>
    `;

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
  const btn = document.getElementById("create-btn");
  const label = document.getElementById("create-label");
  const spinner = document.getElementById("create-spinner");

  const preferOriginal = document.getElementById("opt-prefer-original").checked;
  const includeTaped = document.getElementById("opt-include-taped").checked;

  btn.disabled = true;
  label.textContent = "Building playlist…";
  spinner.classList.remove("hidden");

  try {
    const res = await fetch("/api/create-playlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        artists: selectedArtists,
        prefer_original: preferOriginal,
        include_taped: includeTaped,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      const msg =
        data.error === "no_tracks_found"
          ? "No matching tracks found on Spotify for any of these artists."
          : data.error === "no_artists"
          ? "Add at least one artist first."
          : data.error || "Failed to create playlist. Please try again.";
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

// ── Result display ─────────────────────────────────────────────────────────────

function showResult(data) {
  document.getElementById("artists-card").classList.add("hidden");

  const resultCard = document.getElementById("result-card");
  resultCard.classList.remove("hidden");

  document.getElementById("playlist-link").href = data.playlist_url;

  // ── Missing tracks warning box ──
  const warningBox = document.getElementById("warning-box");
  warningBox.innerHTML = "";

  const warnings = (data.artists || []).filter(
    (a) => a.missing && a.missing.length > 0
  );

  if (warnings.length) {
    const rows = warnings
      .map((a) => {
        // Show ALL missing tracks — no truncation
        const songList = a.missing
          .map((s) => `"${escapeHtml(s)}"`)
          .join(", ");
        return `<div class="warning-row">
          <span class="warning-artist">🎤 ${escapeHtml(a.name)}</span>
          <span class="warning-songs">${songList}</span>
        </div>`;
      })
      .join("");

    warningBox.innerHTML = `
      <div class="warning-title">⚠️ Some tracks couldn't be found on Spotify:</div>
      ${rows}
    `;
    warningBox.classList.remove("hidden");
  } else {
    warningBox.classList.add("hidden");
  }

  // ── Artist summary ──
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

  document.getElementById("player-wrap").innerHTML = `<iframe
    src="https://open.spotify.com/embed/playlist/${data.playlist_id}?utm_source=generator&theme=0"
    height="352"
    allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture; web-share"
    loading="lazy">
  </iframe>`;
}

function resetResult() {
  selectedArtists.length = 0;
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