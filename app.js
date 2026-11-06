const RELEASE = new Date("2026-11-06T20:59:00+01:00");
const AREAS = [
  ["k", "Indre By"],
  ["v", "Vesterbro"],
  ["n", "Nørrebro"],
  ["s", "Amager"],
  ["o", "Østerbro"],
  ["frb", "Frederiksberg"],
  ["val", "Valby"],
];

const state = {
  pubs: [],
  area: "all",
  query: "",
  selected: null,
  picks: new Set(),
  here: null,
  sheet: true,
};

const $ = (id) => document.getElementById(id);
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let map;
let cluster;
let hereMarker;
const markers = new Map();

function loadPicks() {
  try {
    const saved = JSON.parse(localStorage.getItem("jday-2026-picks") || "[]");
    if (Array.isArray(saved)) saved.forEach((id) => state.picks.add(id));
  } catch (_) { /* ignore broken storage */ }
  const params = new URLSearchParams(location.search);
  const fromUrl = (params.get("pick") || "").split(",").map((s) => s.trim()).filter(Boolean);
  fromUrl.forEach((id) => state.picks.add(id));
  if (params.get("area")) state.area = params.get("area");
  if (params.get("q")) state.query = params.get("q");
  if (params.get("bar")) state.selected = params.get("bar");
  if (fromUrl.length) persistPicks();
}

function persistPicks() {
  localStorage.setItem("jday-2026-picks", JSON.stringify([...state.picks]));
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2200);
}

function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const p = Math.PI / 180;
  const dLat = (lat2 - lat1) * p;
  const dLng = (lng2 - lng1) * p;
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1 * p) * Math.cos(lat2 * p) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

function formatDistance(meters) {
  if (meters < 950) return `${Math.max(10, Math.round(meters / 10) * 10)} m`;
  const km = meters / 1000;
  return `${km.toFixed(km < 10 ? 1 : 0)} km`;
}

function isWeak(pub) {
  if (pub.lat == null) return true;
  if (pub.source === "unmatched") return true;
  return pub.confidence != null && pub.confidence < 0.8;
}

function googleUrl(pub) {
  const query = encodeURIComponent(pub.googleQuery || `${pub.name} Copenhagen`);
  return `https://www.google.com/maps/search/?api=1&query=${query}`;
}

function directionsUrl(pub) {
  if (pub.lat == null) return googleUrl(pub);
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  if (ios) return `https://maps.apple.com/?daddr=${pub.lat},${pub.lng}&dirflg=w`;
  return `https://www.google.com/maps/dir/?api=1&destination=${pub.lat},${pub.lng}&travelmode=walking`;
}

function distanceOf(pub) {
  if (!state.here || pub.lat == null) return null;
  return haversine(state.here.lat, state.here.lng, pub.lat, pub.lng);
}

function filtered() {
  const q = state.query.trim().toLowerCase();
  let rows = state.pubs.filter((pub) => {
    if (state.area === "saved" && !state.picks.has(pub.id)) return false;
    if (state.area !== "all" && state.area !== "saved" && pub.area !== state.area) return false;
    if (!q) return true;
    const hay = `${pub.name} ${pub.areaLabel} ${pub.areaShort} ${pub.address || ""}`.toLowerCase();
    return hay.includes(q);
  });
  rows.sort((a, b) => {
    const da = distanceOf(a);
    const db = distanceOf(b);
    if (da != null && db != null && da !== db) return da - db;
    if (da != null && db == null) return -1;
    if (db != null && da == null) return 1;
    return a.name.localeCompare(b.name, "da");
  });
  return rows;
}

function iconFor(pub) {
  const active = pub.id === state.selected ? " is-active" : "";
  const saved = state.picks.has(pub.id) ? " is-saved" : "";
  return L.divIcon({
    className: "pin-wrap",
    html: `<span class="pin area-${pub.area}${active}${saved}"></span>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

function syncMarkers(rows) {
  cluster.clearLayers();
  const visible = new Set(rows.map((pub) => pub.id));
  for (const pub of state.pubs) {
    if (pub.lat == null) continue;
    let marker = markers.get(pub.id);
    if (!marker) {
      marker = L.marker([pub.lat, pub.lng], { icon: iconFor(pub), keyboard: true, title: pub.name });
      marker.on("click", () => select(pub.id, { pan: false }));
      markers.set(pub.id, marker);
    } else {
      marker.setIcon(iconFor(pub));
    }
    if (visible.has(pub.id)) cluster.addLayer(marker);
  }
}

function renderChips() {
  const chips = $("chips");
  chips.replaceChildren();
  const counts = new Map(AREAS.map(([id]) => [id, state.pubs.filter((p) => p.area === id).length]));
  const items = [["all", "All", state.pubs.length], ...AREAS.map(([id, label]) => [id, label, counts.get(id)]), ["saved", "Saved", state.picks.size]];
  for (const [id, label, count] of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(state.area === id));
    if (AREAS.some(([area]) => area === id)) {
      const dot = document.createElement("span");
      dot.className = `dot area-${id}`;
      button.append(dot);
    }
    button.append(`${label} ${count}`);
    button.addEventListener("click", () => {
      state.area = id;
      render();
      fitTo(filtered());
    });
    chips.append(button);
  }
}

function renderSummary(rows) {
  const summary = $("summary");
  const located = rows.filter((pub) => pub.lat != null);
  if (state.here && located.length) {
    const nearest = located[0];
    const meters = distanceOf(nearest);
    summary.textContent = `${rows.length} bar${rows.length === 1 ? "" : "s"} · nearest ${nearest.name}, ${formatDistance(meters)}`;
    return;
  }
  if (state.area === "saved") {
    summary.textContent = rows.length ? `${rows.length} saved for tonight` : "No saves yet. Star the bars you actually want.";
    return;
  }
  const label = AREAS.find(([id]) => id === state.area)?.[1];
  if (!label) {
    const noun = rows.length === 1 ? "bar" : "bars";
    summary.textContent = `${rows.length} ${noun} pouring on J-dag. Indre By is the dense crawl and gets packed after 21.`;
    return;
  }
  summary.textContent = `${rows.length} in ${label}`;
}

function renderList(rows) {
  const list = $("list");
  list.replaceChildren();
  for (const pub of rows) {
    const item = document.createElement("li");
    item.className = "row" + (pub.id === state.selected ? " is-selected" : "");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "row-main";
    const swatch = document.createElement("span");
    swatch.className = `swatch area-${pub.area}`;
    const text = document.createElement("span");
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = pub.name;
    const meta = document.createElement("span");
    meta.className = "meta";
    const bits = [pub.areaShort];
    if (pub.lat == null) bits.push("no pin");
    else if (isWeak(pub)) bits.push("check the pin");
    meta.textContent = bits.join(" · ");
    text.append(name, document.createElement("br"), meta);
    const dist = document.createElement("span");
    dist.className = "dist";
    const meters = distanceOf(pub);
    dist.textContent = meters == null ? "" : formatDistance(meters);
    const star = document.createElement("button");
    star.type = "button";
    star.className = "star" + (state.picks.has(pub.id) ? " is-on" : "");
    star.setAttribute("aria-label", state.picks.has(pub.id) ? `Unsave ${pub.name}` : `Save ${pub.name}`);
    star.textContent = state.picks.has(pub.id) ? "★" : "☆";
    star.addEventListener("click", (event) => {
      event.stopPropagation();
      togglePick(pub.id);
    });
    button.append(swatch, text, dist);
    button.addEventListener("click", () => select(pub.id));
    item.append(button, star);
    list.append(item);
  }
}

function renderCard() {
  const card = $("card");
  const pub = state.pubs.find((item) => item.id === state.selected);
  if (!pub) {
    card.hidden = true;
    card.replaceChildren();
    return;
  }
  card.hidden = false;
  card.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = pub.name;
  const where = document.createElement("p");
  where.className = "where";
  where.textContent = `${pub.areaShort} · ${pub.areaLabel}`;
  card.append(title, where);
  if (pub.address) {
    const addr = document.createElement("p");
    addr.className = "addr";
    addr.textContent = pub.address;
    card.append(addr);
  }
  const meters = distanceOf(pub);
  if (meters != null) {
    const walk = document.createElement("p");
    walk.className = "walk";
    const minutes = Math.max(1, Math.round(meters / 80));
    walk.textContent = `${formatDistance(meters)} · about ${minutes} min walk`;
    card.append(walk);
  }
  const actions = document.createElement("div");
  actions.className = "card-actions";
  const directions = document.createElement("a");
  directions.className = "primary";
  directions.href = directionsUrl(pub);
  directions.target = "_blank";
  directions.rel = "noopener";
  directions.textContent = "Directions";
  const rating = document.createElement("a");
  rating.href = googleUrl(pub);
  rating.target = "_blank";
  rating.rel = "noopener";
  rating.textContent = "Rating & hours";
  const save = document.createElement("button");
  save.type = "button";
  save.textContent = state.picks.has(pub.id) ? "Saved" : "Save";
  save.addEventListener("click", () => togglePick(pub.id));
  actions.append(directions, rating, save);
  card.append(actions);
  if (pub.note || isWeak(pub)) {
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = pub.note || (pub.lat == null
      ? "No reliable pin. Use Rating & hours and search the name."
      : "Pin is a best match and might be a door off. Confirm with Rating & hours.");
    card.append(note);
  }
}

function renderShare() {
  const button = $("share");
  button.textContent = state.picks.size ? `Share ${state.picks.size}` : "Share";
  button.classList.toggle("has-picks", state.picks.size > 0);
}

function render() {
  const rows = filtered();
  renderChips();
  renderSummary(rows);
  renderList(rows);
  renderCard();
  renderShare();
  if (cluster) syncMarkers(rows);
  const selected = $("list").querySelector(".is-selected");
  if (selected) selected.scrollIntoView({ block: "nearest" });
}

function select(id, options = {}) {
  state.selected = id;
  const pub = state.pubs.find((item) => item.id === id);
  render();
  if (!pub || pub.lat == null || !map) return;
  const marker = markers.get(pub.id);
  const latlng = marker ? marker.getLatLng() : L.latLng(pub.lat, pub.lng);
  const zoom = Math.max(map.getZoom(), 16);
  if (options.pan === false) {
    if (!map.getBounds().pad(-0.15).contains(latlng)) map.panTo(latlng, { animate: !reduceMotion });
    return;
  }
  if (reduceMotion) map.setView(latlng, zoom, { animate: false });
  else map.flyTo(latlng, zoom, { duration: 0.55 });
}

function togglePick(id) {
  if (state.picks.has(id)) state.picks.delete(id);
  else state.picks.add(id);
  persistPicks();
  render();
}

function fitTo(rows) {
  const points = rows.filter((pub) => pub.lat != null).map((pub) => [pub.lat, pub.lng]);
  if (!points.length || !map) return;
  if (points.length === 1) {
    map.setView(points[0], 16, { animate: !reduceMotion });
    return;
  }
  map.fitBounds(points, { padding: [36, 36], maxZoom: 15, animate: !reduceMotion });
}

function shareUrl() {
  const url = new URL(location.href);
  url.search = "";
  url.hash = "";
  if (state.picks.size) url.searchParams.set("pick", [...state.picks].join(","));
  else if (state.selected) url.searchParams.set("bar", state.selected);
  return url.toString();
}

async function sharePlan() {
  const url = shareUrl();
  const count = state.picks.size;
  const text = count ? `J-dag plan · ${count} bar${count === 1 ? "" : "s"}` : "J-dag map, Copenhagen";
  if (navigator.share) {
    try {
      await navigator.share({ title: "J-dag i København", text, url });
      return;
    } catch (error) {
      if (error && error.name === "AbortError") return;
    }
  }
  try {
    await navigator.clipboard.writeText(url);
    toast("Link copied");
  } catch (_) {
    toast(url);
  }
}

function locate() {
  if (!navigator.geolocation) {
    toast("This browser has no location");
    return;
  }
  $("locate").setAttribute("aria-pressed", "true");
  navigator.geolocation.getCurrentPosition((pos) => {
    state.here = { lat: pos.coords.latitude, lng: pos.coords.longitude };
    const icon = L.divIcon({ className: "pin-wrap", html: `<span class="me-dot"></span>`, iconSize: [18, 18], iconAnchor: [9, 9] });
    if (hereMarker) hereMarker.remove();
    hereMarker = L.marker([state.here.lat, state.here.lng], { icon, interactive: false, zIndexOffset: 800 }).addTo(map);
    render();
    const nearest = filtered().find((pub) => pub.lat != null);
    if (nearest) map.setView([state.here.lat, state.here.lng], 15, { animate: !reduceMotion });
  }, () => {
    $("locate").setAttribute("aria-pressed", "false");
    toast("Location is off — you can still browse the map");
  }, { enableHighAccuracy: true, timeout: 8000, maximumAge: 15000 });
}

function tick() {
  const now = new Date();
  const diff = RELEASE - now;
  const value = $("clock-value");
  const label = $("clock-label");
  const clock = value.closest(".clock");
  if (diff > 0) {
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    value.textContent = hours > 0
      ? `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
      : `${minutes}:${String(seconds).padStart(2, "0")}`;
    label.textContent = "until julebryg";
    clock.classList.remove("is-out");
    return;
  }
  clock.classList.add("is-out");
  value.textContent = "It’s out";
  label.textContent = "julebryg since 20:59";
}

function setupMap() {
  map = L.map("map", { zoomControl: true, attributionControl: true }).setView([55.678, 12.569], 13);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ | Places &copy; OpenStreetMap',
    maxZoom: 19,
    maxNativeZoom: 16,
  }).addTo(map);
  cluster = L.markerClusterGroup({
    showCoverageOnHover: false,
    maxClusterRadius: 42,
    spiderfyOnMaxZoom: true,
    disableClusteringAtZoom: 17,
  });
  map.addLayer(cluster);
}

async function main() {
  loadPicks();
  $("q").value = state.query;
  setupMap();
  const response = await fetch("./data/pubs.json");
  const data = await response.json();
  state.pubs = data.pubs;
  if (state.selected && !state.pubs.some((pub) => pub.id === state.selected)) state.selected = null;
  render();
  const params = new URLSearchParams(location.search);
  if (params.get("pick") && state.picks.size) fitTo(state.pubs.filter((pub) => state.picks.has(pub.id)));
  else if (state.selected) select(state.selected);
  else fitTo(filtered());

  $("q").addEventListener("input", (event) => {
    state.query = event.target.value;
    render();
  });
  $("locate").addEventListener("click", locate);
  $("share").addEventListener("click", sharePlan);
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement !== $("q")) {
      event.preventDefault();
      $("q").focus();
    }
    if (event.key === "Escape") {
      state.selected = null;
      render();
    }
  });
  tick();
  setInterval(tick, 1000);
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
}

main().catch((error) => {
  $("summary").textContent = "The bar list didn’t load. Refresh once you’re back online.";
  console.error(error);
});
