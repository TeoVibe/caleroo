const $ = (selector) => document.querySelector(selector);

const THEME_KEY = "caleroo-theme";
const THEMES = [
  { id: "lime", name: "Lime", bg: "#0c0d0b", accent: "#dff25c", scheme: "dark" },
  { id: "dusk", name: "Dusk", bg: "#14161b", accent: "#e4d2b0", scheme: "dark" },
  { id: "paper", name: "Paper", bg: "#efece4", accent: "#243024", scheme: "light" },
  { id: "ink", name: "Ink", bg: "#000000", accent: "#ffe600", scheme: "dark", contrast: true },
  { id: "chalk", name: "Chalk", bg: "#ffffff", accent: "#000000", scheme: "light", contrast: true },
];

const AVATAR_ART = {
  lemon: `<circle cx="32" cy="36" r="22" fill="#f5c518"/><ellipse cx="46" cy="16" rx="8" ry="4.5" transform="rotate(-40 46 16)" fill="#3e8f38"/><circle cx="25" cy="34" r="2.3" fill="#2a241c"/><circle cx="39" cy="34" r="2.3" fill="#2a241c"/><path d="M26 44c2.2 2.8 9.8 2.8 12 0" fill="none" stroke="#2a241c" stroke-width="1.8" stroke-linecap="round"/>`,
  sprout: `<circle cx="32" cy="40" r="18" fill="#9ed9b4"/><ellipse cx="24" cy="20" rx="8" ry="12" transform="rotate(-30 24 20)" fill="#5eae78"/><ellipse cx="40" cy="18" rx="8" ry="12" transform="rotate(28 40 18)" fill="#3f9a62"/><circle cx="25" cy="38" r="2.3" fill="#2a241c"/><circle cx="39" cy="38" r="2.3" fill="#2a241c"/><path d="M26 48c2.2 2.8 9.8 2.8 12 0" fill="none" stroke="#2a241c" stroke-width="1.8" stroke-linecap="round"/>`,
  cat: `<polygon points="14,28 20,12 28,26" fill="#f3b48a"/><polygon points="50,28 44,12 36,26" fill="#f3b48a"/><polygon points="17,24 20,15 25,24" fill="#f6c9c0"/><polygon points="47,24 44,15 39,24" fill="#f6c9c0"/><circle cx="32" cy="38" r="18" fill="#f3b48a"/><circle cx="25" cy="36" r="2.3" fill="#2a241c"/><circle cx="39" cy="36" r="2.3" fill="#2a241c"/><path d="M26 46c2.2 2.6 9.8 2.6 12 0" fill="none" stroke="#2a241c" stroke-width="1.8" stroke-linecap="round"/>`,
  bunny: `<ellipse cx="22" cy="18" rx="6" ry="14" fill="#f7c4d4"/><ellipse cx="42" cy="18" rx="6" ry="14" fill="#f7c4d4"/><ellipse cx="22" cy="18" rx="3" ry="9" fill="#f3a8c0"/><ellipse cx="42" cy="18" rx="3" ry="9" fill="#f3a8c0"/><circle cx="32" cy="40" r="18" fill="#f7c4d4"/><circle cx="25" cy="38" r="2.3" fill="#2a241c"/><circle cx="39" cy="38" r="2.3" fill="#2a241c"/><path d="M26 48c2.2 2.6 9.8 2.6 12 0" fill="none" stroke="#2a241c" stroke-width="1.8" stroke-linecap="round"/>`,
  bear: `<circle cx="16" cy="20" r="8" fill="#c9a27a"/><circle cx="48" cy="20" r="8" fill="#c9a27a"/><circle cx="16" cy="20" r="4" fill="#a67c52"/><circle cx="48" cy="20" r="4" fill="#a67c52"/><circle cx="32" cy="38" r="18" fill="#d7b899"/><ellipse cx="32" cy="44" rx="6" ry="4" fill="#f0d8c0"/><circle cx="25" cy="36" r="2.3" fill="#2a241c"/><circle cx="39" cy="36" r="2.3" fill="#2a241c"/>`,
  fox: `<polygon points="12,30 20,10 30,28" fill="#e07a3d"/><polygon points="52,30 44,10 34,28" fill="#e07a3d"/><circle cx="32" cy="38" r="18" fill="#e07a3d"/><ellipse cx="32" cy="46" rx="10" ry="7" fill="#fff4ea"/><circle cx="25" cy="34" r="2.3" fill="#2a241c"/><circle cx="39" cy="34" r="2.3" fill="#2a241c"/><circle cx="32" cy="44" r="2" fill="#2a241c"/>`,
  frog: `<circle cx="32" cy="38" r="20" fill="#7dce6a"/><circle cx="22" cy="28" r="8" fill="#f7fff4"/><circle cx="42" cy="28" r="8" fill="#f7fff4"/><circle cx="22" cy="28" r="4" fill="#2a241c"/><circle cx="42" cy="28" r="4" fill="#2a241c"/><circle cx="23.2" cy="26.8" r="1.4" fill="#fff"/><circle cx="43.2" cy="26.8" r="1.4" fill="#fff"/><path d="M22 44c3.4 4 16.6 4 20 0" fill="none" stroke="#2a241c" stroke-width="1.8" stroke-linecap="round"/>`,
  panda: `<circle cx="14" cy="18" r="8" fill="#2a241c"/><circle cx="50" cy="18" r="8" fill="#2a241c"/><circle cx="32" cy="38" r="18" fill="#f7f4ee"/><ellipse cx="23" cy="36" rx="7" ry="8" fill="#2a241c"/><ellipse cx="41" cy="36" rx="7" ry="8" fill="#2a241c"/><circle cx="23" cy="36" r="2.4" fill="#f7f4ee"/><circle cx="41" cy="36" r="2.4" fill="#f7f4ee"/><ellipse cx="32" cy="46" rx="3.5" ry="2.4" fill="#2a241c"/>`,
  owl: `<polygon points="32,8 24,22 40,22" fill="#c9a36a"/><circle cx="32" cy="38" r="18" fill="#e6d2a4"/><circle cx="24" cy="36" r="8" fill="#fffaf2"/><circle cx="40" cy="36" r="8" fill="#fffaf2"/><circle cx="24" cy="36" r="4" fill="#2a241c"/><circle cx="40" cy="36" r="4" fill="#2a241c"/><polygon points="32,40 28,46 36,46" fill="#e09a3e"/>`,
  chick: `<polygon points="32,12 28,20 36,20" fill="#f0c24a"/><circle cx="32" cy="38" r="18" fill="#ffe56a"/><polygon points="30,40 42,38 30,44" fill="#f4a24a"/><circle cx="24" cy="34" r="2.3" fill="#2a241c"/><circle cx="34" cy="34" r="2.3" fill="#2a241c"/>`,
  mushroom: `<rect x="24" y="34" width="16" height="18" rx="6" fill="#fff1e0"/><ellipse cx="32" cy="30" rx="22" ry="14" fill="#e15d5d"/><circle cx="22" cy="26" r="3.5" fill="#fff6f2"/><circle cx="34" cy="20" r="2.6" fill="#fff6f2"/><circle cx="42" cy="28" r="2.2" fill="#fff6f2"/><circle cx="28" cy="42" r="1.8" fill="#2a241c"/><circle cx="36" cy="42" r="1.8" fill="#2a241c"/><path d="M28 47c1.4 1.6 6.6 1.6 8 0" fill="none" stroke="#2a241c" stroke-width="1.6" stroke-linecap="round"/>`,
  blob: `<path d="M32 10c12 0 22 8 22 20 0 8-4 12-4 16 0 8-8 14-18 14S14 54 14 46c0-4-4-8-4-16C10 18 20 10 32 10z" fill="#8ec5f5"/><circle cx="25" cy="32" r="2.3" fill="#2a241c"/><circle cx="39" cy="32" r="2.3" fill="#2a241c"/><path d="M26 42c2.2 2.8 9.8 2.8 12 0" fill="none" stroke="#2a241c" stroke-width="1.8" stroke-linecap="round"/>`,
};

const AVATAR_NAMES = {
  lemon: "Lemon",
  sprout: "Sprout",
  cat: "Cat",
  bunny: "Bunny",
  bear: "Bear",
  fox: "Fox",
  frog: "Frog",
  panda: "Panda",
  owl: "Owl",
  chick: "Chick",
  mushroom: "Mushroom",
  blob: "Blob",
};

const state = {
  date: "",
  day: null,
  week: null,
  history: null,
  settings: null,
  auth: null,
  user: null,
  avatar: "lemon",
  mode: "idle",
  blob: null,
  previewUrl: null,
  stream: null,
  facing: "environment",
  estimate: null,
  adviceLoading: false,
};

const video = $("#video");
const preview = $("#preview");
const fileInput = $("#file-input");

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (value == null || value === false) return;
    if (key === "class") node.className = value;
    else if (key === "hidden") node.hidden = Boolean(value);
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2).toLowerCase(), value);
    else node.setAttribute(key, String(value));
  });
  const list = Array.isArray(children) ? children : [children];
  list.forEach((child) => {
    if (child == null || child === false) return;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  });
  return node;
}

function todayISO() {
  const now = new Date();
  return isoFromDate(now);
}

function isoFromDate(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function addDays(iso, amount) {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() + amount);
  return isoFromDate(date);
}

function labelFor(iso) {
  if (iso === todayISO()) return "Today";
  if (iso === addDays(todayISO(), -1)) return "Yesterday";
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function fmt(value) {
  return Math.round(Number(value) || 0).toLocaleString();
}

function grams(value) {
  const number = Number(value) || 0;
  if (Math.abs(number) >= 10) return Math.round(number).toLocaleString();
  return (Math.round(number * 10) / 10).toLocaleString();
}

function clock(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function toast(message, kind = "") {
  const host = $("#toasts");
  host.replaceChildren();
  const node = el("p", { class: kind ? `toast ${kind}` : "toast" }, message);
  host.append(node);
  setTimeout(() => {
    if (node.isConnected) node.remove();
  }, 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!response.ok) {
    const detail = data && data.detail;
    const error = new Error(typeof detail === "string" ? detail : "Request failed.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function avatarMarkup(id) {
  const art = AVATAR_ART[id] || AVATAR_ART.lemon;
  return `<svg viewBox="0 0 64 64" aria-hidden="true">${art}</svg>`;
}

function renderAvatars(selected) {
  const host = $("#avatar-picker");
  if (!host) return;
  const ids = (state.auth && state.auth.avatars) || Object.keys(AVATAR_ART);
  state.avatar = ids.includes(selected) ? selected : ids[0] || "lemon";
  host.replaceChildren();
  ids.forEach((id) => {
    const pressed = id === state.avatar;
    const button = el("button", {
      type: "button",
      class: pressed ? "avatar-choice selected" : "avatar-choice",
      "aria-pressed": pressed ? "true" : "false",
      "aria-label": AVATAR_NAMES[id] || id,
    });
    button.innerHTML = avatarMarkup(id);
    button.addEventListener("click", () => renderAvatars(id));
    host.append(button);
  });
}

function showAccount(user) {
  const button = $("#account-btn");
  const pad = $("#nav-pad");
  const logout = $("#logout-btn");
  const label = $("#account-label");
  state.user = user || null;
  if (!user) {
    button.hidden = true;
    button.replaceChildren();
    pad.hidden = false;
    logout.hidden = true;
    label.hidden = true;
    return;
  }
  button.hidden = false;
  pad.hidden = true;
  button.innerHTML = avatarMarkup(user.avatar);
  button.setAttribute("aria-label", `${user.username}, account`);
  logout.hidden = false;
  label.hidden = false;
  label.textContent = user.username;
}

function showAuthMode(mode) {
  const login = mode !== "register";
  $("#login-form").hidden = !login;
  $("#register-form").hidden = login;
  if (!login) renderAvatars(state.avatar);
  const field = login ? $("#login-name") : $("#register-name");
  if (field) field.focus();
}

function showGate(auth) {
  state.auth = auth || state.auth;
  document.body.classList.add("gated");
  const shell = $("#shell");
  shell.inert = true;
  shell.setAttribute("aria-hidden", "true");
  $("#gate").hidden = false;
  showAccount(null);
  const hasUsers = Boolean(state.auth && state.auth.has_users);
  $("#show-login").hidden = !hasUsers;
  showAuthMode(hasUsers ? "login" : "register");
}

function hideGate() {
  document.body.classList.remove("gated");
  const shell = $("#shell");
  shell.inert = false;
  shell.removeAttribute("aria-hidden");
  $("#gate").hidden = true;
}

async function enterApp(auth) {
  state.auth = auth;
  $("#meals").replaceChildren();
  showAccount(auth.user);
  hideGate();
  await loadApp();
}

function loadApp() {
  state.date = readHash();
  if (location.hash !== `#${state.date}`) history.replaceState(null, "", `#${state.date}`);
  return api("/api/settings")
    .then((settings) => {
      state.settings = settings;
      fillSettingsForm();
      if (settings.user) showAccount(settings.user);
    })
    .catch((error) => {
      if (error.status === 401) {
        showGate(state.auth || { authentication: true, has_users: true, avatars: Object.keys(AVATAR_ART) });
        return;
      }
      toast(error.message, "error");
    })
    .finally(() => {
      if (!document.body.classList.contains("gated")) refresh();
    });
}

function readHash() {
  const match = location.hash.match(/^#(\d{4}-\d{2}-\d{2})$/);
  if (!match || match[1] > todayISO()) return todayISO();
  return match[1];
}

function setDate(iso) {
  if (iso > todayISO()) iso = todayISO();
  if (location.hash === `#${iso}`) {
    state.date = iso;
    refresh();
    return;
  }
  location.hash = iso;
}

async function refresh() {
  try {
    const calendarOpen = $("#calendar-dialog").open;
    const calls = [api(`/api/days/${state.date}`), api(`/api/weeks/${state.date}`)];
    if (calendarOpen) calls.push(api("/api/history"));
    const [day, week, history] = await Promise.all(calls);
    state.day = day;
    state.week = week;
    if (history) {
      state.history = history;
      renderCalendar();
    }
    renderSummary();
    renderMeals();
    renderWeek();
    renderDate();
  } catch (error) {
    if (error.status === 401) {
      showGate(state.auth || { authentication: true, has_users: true, avatars: Object.keys(AVATAR_ART) });
      return;
    }
    toast(error.message, "error");
  }
}

function renderDate() {
  const label = labelFor(state.date);
  const dateLabel = $("#date-label");
  dateLabel.textContent = label;
  dateLabel.setAttribute("aria-label", `Open calendar, ${label}`);
  $("#next-day").disabled = state.date >= todayISO();
  renderAdviceButton();
}

function paintRing(ring, value, goal, over) {
  const length = 2 * Math.PI * 46;
  const pct = goal > 0 ? Math.min(Math.max(value, 0) / goal, 1) : 0;
  ring.style.strokeDasharray = String(length);
  ring.style.strokeDashoffset = String(length * (1 - pct));
  ring.classList.toggle("over", Boolean(over));
}

const MACRO_GOALS = { protein_g: 150, carbs_g: 200, fat_g: 65 };

const MACRO_STATS = [
  { key: "protein_g", label: "Protein", figure: "protein-figure", remain: "protein-remain", ring: "ring-protein", link: "open-protein-goal" },
  { key: "carbs_g", label: "Carbs", figure: "carbs-figure", remain: "carbs-remain", ring: "ring-carbs", link: "open-carbs-goal" },
  { key: "fat_g", label: "Fat", figure: "fat-figure", remain: "fat-remain", ring: "ring-fat", link: "open-fat-goal" },
];

function renderMacro(stat, value, goal) {
  const over = goal > 0 && value > goal;
  const met = goal > 0 && value >= goal && !over;
  const figure = $(`#${stat.figure}`);
  figure.textContent = grams(value);
  figure.classList.toggle("over", over);
  figure.classList.toggle("met", met);
  const left = goal - value;
  let remain = `${grams(Math.max(left, 0))} left`;
  if (over) remain = `${grams(Math.abs(left))} over`;
  else if (met) remain = "Met";
  $(`#${stat.remain}`).textContent = remain;
  $(`#${stat.link}`).textContent = `${stat.label} ${fmt(goal)}`;
  paintRing($(`#${stat.ring}`), value, goal, over);
}

function renderSummary() {
  const totals = state.day.totals;
  const goal = state.day.goal;
  const over = goal > 0 && totals.calories > goal;
  const figure = $("#kcal-figure");
  figure.textContent = fmt(totals.calories);
  figure.classList.toggle("over", over);
  const left = goal - totals.calories;
  $("#remain").textContent = left >= 0 ? `${fmt(left)} left` : `${fmt(Math.abs(left))} over`;
  $("#open-goal").textContent = `Diet ${fmt(goal)}`;
  const macros = state.day.macro_goals || MACRO_GOALS;
  MACRO_STATS.forEach((stat) => {
    renderMacro(stat, Number(totals[stat.key]) || 0, Number(macros[stat.key]) || 0);
  });
  paintRing($("#ring-value"), totals.calories, goal, over);
}

function renderMeals() {
  const meals = state.day.meals || [];
  const host = $("#meals");
  host.replaceChildren();
  $("#meal-count").textContent = meals.length === 1 ? "1 meal" : meals.length ? `${meals.length} meals` : "";
  meals.forEach((meal) => host.append(mealCard(meal)));
}

function mealCard(meal) {
  const thumb = meal.has_image
    ? el("img", { class: "thumb", alt: "", src: `/api/meals/${meal.id}/image` })
    : el("span", { class: "mono", "aria-hidden": "true" }, (meal.title || "M").trim().charAt(0).toUpperCase());
  if (meal.has_image) thumb.addEventListener("error", () => thumb.replaceWith(el("span", { class: "mono" }, "M")));
  const itemNames = (meal.items || []).map((item) => item.name).filter(Boolean);
  const names = itemNames.length === 1 && itemNames[0] === meal.title ? "" : itemNames.join(" · ");
  const body = el("div", { class: "meal-body", tabindex: "0", role: "button", "aria-expanded": "false" }, [
    el("p", { class: "meal-title" }, meal.title),
    el("p", { class: "meal-meta" }, clock(meal.created_at)),
    names ? el("p", { class: "meal-items" }, names) : null,
  ]);
  const remove = el("button", { class: "linkish", type: "button" }, "Delete");
  remove.addEventListener("click", (event) => confirmDelete(event, meal, remove));
  const side = el("div", { class: "meal-side" }, [
    el("p", { class: "meal-kcal num" }, fmt(meal.calories)),
    remove,
  ]);
  const detail = mealDetail(meal);
  const toggle = () => {
    detail.hidden = !detail.hidden;
    body.setAttribute("aria-expanded", String(!detail.hidden));
  };
  body.addEventListener("click", toggle);
  body.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    toggle();
  });
  thumb.addEventListener("click", toggle);
  return el("article", { class: "meal" }, [thumb, body, side, detail]);
}

function mealDetail(meal) {
  const lines = (meal.items || []).map((item) => {
    const portion = item.portion ? ` · ${item.portion}` : "";
    return el("li", {}, `${item.name}${portion} — ${fmt(item.calories)} kcal`);
  });
  const bits = [el("ul", {}, lines)];
  if (meal.notes) bits.push(el("p", { class: "detail-notes" }, meal.notes));
  return el("div", { class: "detail", hidden: true }, bits);
}

async function confirmDelete(event, meal, button) {
  event.stopPropagation();
  if (button.dataset.armed !== "1") {
    button.dataset.armed = "1";
    button.classList.add("armed");
    button.textContent = "Remove?";
    setTimeout(() => {
      if (!button.isConnected) return;
      button.dataset.armed = "0";
      button.classList.remove("armed");
      button.textContent = "Delete";
    }, 2400);
    return;
  }
  try {
    await api(`/api/meals/${meal.id}`, { method: "DELETE" });
    await refresh();
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderWeek() {
  const host = $("#week");
  host.replaceChildren();
  const days = state.week.days || [];
  const goal = state.week.goal || 0;
  const today = todayISO();
  days.forEach((day) => {
    const [year, month, date] = day.date.split("-").map(Number);
    const weekday = new Date(year, month - 1, date).toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2);
    const over = goal > 0 && day.calories > goal;
    const selected = day.date === state.date;
    const future = day.date > today;
    const track = el("span", { class: "bar-track" });
    if (day.calories > 0) {
      const bar = el("span", { class: over ? "bar over" : "bar diet" });
      const pct = goal > 0 ? Math.min(day.calories / goal, 1) : 1;
      bar.style.height = `${Math.max(12, Math.round(pct * 100))}%`;
      track.append(bar);
    }
    const button = el("button", {
      class: selected ? "bar-btn selected" : "bar-btn",
      type: "button",
      disabled: future || undefined,
      "aria-current": selected ? "date" : undefined,
      "aria-label": `${labelFor(day.date)}, ${fmt(day.calories)} kcal, protein ${grams(day.protein_g)} g, carbs ${grams(day.carbs_g)} g, fat ${grams(day.fat_g)} g`,
      onclick: () => setDate(day.date),
    }, [
      track,
      el("span", { class: "dow" }, weekday),
      el("span", { class: "day-num" }, String(date)),
    ]);
    host.append(button);
  });
}

function weekdayLetters() {
  const monday = new Date(2026, 9, 19);
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(monday);
    date.setDate(monday.getDate() + index);
    return date.toLocaleDateString(undefined, { weekday: "narrow" });
  });
}

function monthKey(iso) {
  return iso.slice(0, 7);
}

function shiftMonthKey(key, amount) {
  const [year, month] = key.split("-").map(Number);
  const date = new Date(year, month - 1 + amount, 1);
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}`;
}

function monthsInRange(startKey, endKey) {
  const months = [];
  let key = startKey;
  while (key <= endKey && months.length < 240) {
    const [year, month] = key.split("-").map(Number);
    months.push({ year, monthIndex: month - 1 });
    const next = shiftMonthKey(key, 1);
    if (next <= key) break;
    key = next;
  }
  months.reverse();
  return months;
}

function calendarRange() {
  const today = todayISO();
  const keys = [monthKey(today), monthKey(state.date)];
  if (state.history && state.history.first) keys.push(monthKey(state.history.first));
  keys.sort();
  return { start: keys[0], end: monthKey(today) };
}

function sinceLabel(first) {
  if (!first) return "No meals yet";
  const [year, month, day] = first.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const options = { month: "short", day: "numeric" };
  if (year !== new Date().getFullYear()) options.year = "numeric";
  return `Since ${date.toLocaleDateString(undefined, options)}`;
}

function renderDow() {
  const host = $("#cal-dows");
  if (host.childElementCount) return;
  weekdayLetters().forEach((letter) => host.append(el("span", {}, letter)));
}

function historyByDate() {
  const days = (state.history && state.history.days) || [];
  return Object.fromEntries(days.map((day) => [day.date, day]));
}

function monthStats(year, monthIndex, byDate, goal) {
  const total = new Date(year, monthIndex + 1, 0).getDate();
  let logged = 0;
  let calories = 0;
  let over = 0;
  let active = false;
  for (let day = 1; day <= total; day += 1) {
    const record = byDate[isoFromDate(new Date(year, monthIndex, day))];
    if (!record) continue;
    if (record.meals) active = true;
    if (!record.meals) continue;
    logged += 1;
    calories += record.calories;
    if (goal > 0 && record.calories > goal) over += 1;
  }
  return { logged, avg: logged ? Math.round(calories / logged) : 0, over, active };
}

function monthStatLabel(stats) {
  if (!stats.logged) return "No meals";
  if (!stats.over) return `${fmt(stats.avg)} avg`;
  return `${fmt(stats.avg)} avg · ${stats.over} over`;
}

function monthTitle(year, monthIndex, showYear) {
  return new Date(year, monthIndex, 1).toLocaleDateString(
    undefined,
    showYear ? { month: "long", year: "numeric" } : { month: "long" },
  );
}

function monthKeyOf(year, monthIndex) {
  return `${year}-${String(monthIndex + 1).padStart(2, "0")}`;
}

function calendarBlocks(months, byDate) {
  const blocks = [];
  let gap = [];
  const flush = () => {
    if (!gap.length) return;
    blocks.push({ type: "gap", months: gap });
    gap = [];
  };
  months.forEach((month) => {
    const key = monthKeyOf(month.year, month.monthIndex);
    const visible = key === monthKey(todayISO())
      || key === monthKey(state.date)
      || monthStats(month.year, month.monthIndex, byDate, 0).active;
    if (visible) {
      flush();
      blocks.push({ type: "month", year: month.year, monthIndex: month.monthIndex });
    } else {
      gap.push(month);
    }
  });
  flush();
  return blocks;
}

function renderCalendar() {
  renderDow();
  const history = state.history || { first: null, goal: 2000, days: [] };
  const goal = history.goal || 0;
  const byDate = historyByDate();
  const range = calendarRange();
  const crossesYears = range.start.slice(0, 4) !== range.end.slice(0, 4);
  $("#cal-since").textContent = sinceLabel(history.first);
  const host = $("#cal-months");
  host.replaceChildren();
  calendarBlocks(monthsInRange(range.start, range.end), byDate).forEach((block) => {
    if (block.type === "gap") return;
    const { year, monthIndex } = block;
    const showYear = crossesYears || year !== new Date().getFullYear();
    const stats = monthStats(year, monthIndex, byDate, goal);
    host.append(el("section", { class: "cal-month" }, [
      el("div", { class: "cal-month-head" }, [
        el("h3", {}, monthTitle(year, monthIndex, showYear)),
        el("p", { class: "cal-month-stat num" }, monthStatLabel(stats)),
      ]),
      monthGrid(year, monthIndex, byDate, goal),
    ]));
  });
}

function monthGrid(year, monthIndex, byDate, goal) {
  const grid = el("div", { class: "cal-grid" });
  const offset = (new Date(year, monthIndex, 1).getDay() + 6) % 7;
  for (let pad = 0; pad < offset; pad += 1) grid.append(el("span", { class: "cal-pad" }));
  const total = new Date(year, monthIndex + 1, 0).getDate();
  const today = todayISO();
  for (let day = 1; day <= total; day += 1) {
    const iso = isoFromDate(new Date(year, monthIndex, day));
    const record = byDate[iso];
    const calories = record ? record.calories : 0;
    const future = iso > today && !record;
    const over = goal > 0 && calories > goal;
    const selected = iso === state.date;
    const classes = ["cal-day"];
    if (record) classes.push("has");
    if (selected) classes.push("selected");
    if (iso === today) classes.push("today");
    if (over) classes.push("over");
    const parts = [el("span", { class: "cal-num" }, String(day))];
    if (calories > 0) {
      const pct = goal > 0 ? Math.min(calories / goal, 1) : 1;
      const fill = el("span", { class: over ? "cal-fill over" : "cal-fill" });
      fill.style.height = `${Math.max(22, Math.round(pct * 100))}%`;
      const meter = el("span", { class: "cal-meter", "aria-hidden": "true" }, fill);
      parts.push(meter);
    }
    const detail = record
      ? `${labelFor(iso)}, ${fmt(calories)} kcal, protein ${grams(record.protein_g)} g, carbs ${grams(record.carbs_g)} g, fat ${grams(record.fat_g)} g`
      : `${labelFor(iso)}, no meals`;
    const button = el("button", {
      type: "button",
      class: classes.join(" "),
      disabled: future || undefined,
      "aria-pressed": selected ? "true" : "false",
      "aria-label": detail,
    }, parts);
    if (!future) button.addEventListener("click", () => chooseDay(iso));
    grid.append(button);
  }
  return grid;
}

function chooseDay(iso) {
  closeDialog($("#calendar-dialog"));
  if (iso !== state.date) setDate(iso);
}

function scrollCalendarToSelection() {
  const selected = document.querySelector("#cal-months .cal-day.selected");
  const scroller = $("#calendar-dialog .calendar-sheet");
  if (!selected || !scroller) return;
  const header = scroller.querySelector(".cal-sticky");
  const headerHeight = header ? header.offsetHeight : 0;
  const delta = selected.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
  const view = scroller.clientHeight - headerHeight;
  scroller.scrollTop += delta - headerHeight - view / 2 + selected.offsetHeight / 2;
}

async function openCalendar() {
  openDialog("#calendar-dialog");
  $("#calendar-dialog").focus();
  if (!state.history) $("#cal-since").textContent = "";
  try {
    state.history = await api("/api/history");
    renderCalendar();
    requestAnimationFrame(scrollCalendarToSelection);
  } catch (error) {
    if (!state.history) $("#cal-since").textContent = "";
    toast(error.message, "error");
  }
}

function showMode(mode) {
  state.mode = mode;
  $("#stage").hidden = mode === "idle";
  video.hidden = mode !== "camera";
  preview.hidden = mode === "idle" || mode === "camera";
  $("#analyzing").hidden = mode !== "loading";
  $("#camera-controls").hidden = mode !== "camera";
  $("#preview-controls").hidden = mode !== "preview";
  $("#cap-review").hidden = mode !== "review";
  $("#estimate").disabled = mode === "loading";
  $("#capture").classList.toggle("reviewing", mode === "review");
}

function stopCamera() {
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
  }
  video.srcObject = null;
}

function resetCapture() {
  stopCamera();
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = null;
  state.blob = null;
  state.estimate = null;
  preview.removeAttribute("src");
  $("#cap-review").replaceChildren();
  showMode("idle");
}

function setBlob(blob) {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.blob = blob;
  state.previewUrl = URL.createObjectURL(blob);
  preview.src = state.previewUrl;
  showMode("preview");
}

async function downscale(file) {
  const bitmap = await createImageBitmap(file);
  try {
    const maxEdge = 1600;
    const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.86));
    if (!blob) throw new Error("Could not read that photo.");
    return blob;
  } finally {
    bitmap.close?.();
  }
}

async function useFile(file) {
  if (!file) return;
  try {
    const blob = await downscale(file);
    stopCamera();
    setBlob(blob);
  } catch {
    toast("Could not read that photo.", "error");
  }
}

function cameraMessage(error) {
  if (!window.isSecureContext || !navigator.mediaDevices) return "No camera.";
  if (error && error.name === "NotAllowedError") return "Camera blocked.";
  if (error && error.name === "NotFoundError") return "No camera.";
  return "No camera.";
}

async function openCamera(facing = state.facing) {
  if (!window.isSecureContext || !navigator.mediaDevices) {
    toast(cameraMessage(), "error");
    return;
  }
  stopCamera();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: facing }, width: { ideal: 1600 }, height: { ideal: 1200 } },
      audio: false,
    });
    state.facing = facing;
    state.stream = stream;
    video.srcObject = stream;
    await video.play();
    showMode("camera");
  } catch (error) {
    toast(cameraMessage(error), "error");
    showMode("idle");
  }
}

async function takePhoto() {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) {
    toast("Camera isn't ready.");
    return;
  }
  const scale = Math.min(1, 1600 / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.86));
  if (!blob) {
    toast("No photo.", "error");
    return;
  }
  stopCamera();
  setBlob(blob);
}

async function estimate() {
  if (!state.blob || state.mode === "loading") return;
  showMode("loading");
  const form = new FormData();
  form.append("image", state.blob, "meal.jpg");
  try {
    state.estimate = await api("/api/analyze", { method: "POST", body: form });
    renderReview(state.estimate);
    showMode("review");
  } catch (error) {
    showMode("preview");
    toast(error.message, "error");
  }
}

function renderReview(estimate) {
  const root = $("#cap-review");
  const title = el("input", { id: "review-title", type: "text", maxlength: "80", "aria-label": "Meal name" });
  title.value = estimate.title === "No food detected" ? "" : estimate.title || "";
  const notes = el("textarea", { id: "review-notes", rows: "2", "aria-label": "Notes" });
  notes.value = estimate.notes || "";
  const list = el("div", { id: "review-items" });
  const items = estimate.items && estimate.items.length ? estimate.items : [blankItem()];
  items.forEach((item) => list.append(itemRow(item)));
  root.replaceChildren(
    el("label", { class: "field" }, [el("span", {}, "Meal"), title]),
    list,
    el("button", { class: "btn btn-ghost btn-small", type: "button", onclick: () => list.append(itemRow(blankItem())) }, "Add food"),
    el("label", { class: "field" }, [el("span", {}, "Notes"), notes]),
    el("div", { class: "action-row" }, [
      el("button", { class: "btn btn-ghost", type: "button", onclick: resetCapture }, "Discard"),
      el("button", { id: "save-meal", class: "btn btn-primary", type: "button", onclick: saveMeal }, "Log"),
    ]),
  );
  list.addEventListener("input", updateReviewTotal);
  title.addEventListener("input", updateReviewTotal);
  updateReviewTotal();
}

function blankItem() {
  return { name: "", portion: "", calories: "", protein_g: "", carbs_g: "", fat_g: "" };
}

function itemRow(item) {
  const name = el("input", { class: "name", type: "text", maxlength: "80", placeholder: "Food", "aria-label": "Food" });
  const portion = el("input", { class: "portion", type: "text", maxlength: "48", placeholder: "Portion", "aria-label": "Portion" });
  const kcal = el("input", { class: "kcal", type: "number", min: "0", max: "20000", step: "1", inputmode: "numeric", placeholder: "kcal", "aria-label": "Calories" });
  name.value = item.name || "";
  portion.value = item.portion || "";
  kcal.value = item.calories === "" || item.calories == null ? "" : item.calories;
  const remove = el("button", { class: "remove", type: "button", "aria-label": "Remove food" }, "×");
  const row = el("div", { class: "item" }, [
    name,
    portion,
    kcal,
    remove,
    macroInputs(item),
  ]);
  remove.addEventListener("click", () => {
    row.remove();
    updateReviewTotal();
  });
  return row;
}

function macroInputs(item) {
  const protein = miniField("P", "p", "Protein grams", item.protein_g);
  const carbs = miniField("C", "c", "Carb grams", item.carbs_g);
  const fat = miniField("F", "f", "Fat grams", item.fat_g);
  return el("div", { class: "macros-mini" }, [protein, carbs, fat]);
}

function miniField(label, className, aria, value) {
  const input = el("input", { class: className, type: "number", min: "0", max: "2000", step: "0.1", inputmode: "decimal", "aria-label": aria });
  input.value = value === "" || value == null ? "" : value;
  return el("label", { class: "mini" }, [label, input]);
}

function numberValue(input) {
  const value = Number(input.value);
  if (!Number.isFinite(value) || value < 0) return 0;
  return value;
}

function collectItems() {
  return [...document.querySelectorAll("#review-items .item")].map((row) => ({
    name: row.querySelector(".name").value.trim(),
    portion: row.querySelector(".portion").value.trim(),
    calories: Math.round(numberValue(row.querySelector(".kcal"))),
    protein_g: Math.round(numberValue(row.querySelector(".p")) * 10) / 10,
    carbs_g: Math.round(numberValue(row.querySelector(".c")) * 10) / 10,
    fat_g: Math.round(numberValue(row.querySelector(".f")) * 10) / 10,
  }));
}

function updateReviewTotal() {
  const items = collectItems();
  const calories = items.reduce((sum, item) => sum + item.calories, 0);
  const button = $("#save-meal");
  if (button) button.textContent = `Log ${fmt(calories)} kcal`;
}

async function saveMeal() {
  const button = $("#save-meal");
  if (!button || button.disabled) return;
  button.disabled = true;
  const items = collectItems().filter((item) => item.name);
  if (!items.length) {
    button.disabled = false;
    toast("Name a food.");
    return;
  }
  const payload = {
    eaten_on: state.date,
    title: $("#review-title").value.trim(),
    notes: $("#review-notes").value.trim(),
    confidence: state.estimate ? state.estimate.confidence : "",
    model: state.estimate ? state.estimate.model : "",
    items,
  };
  const form = new FormData();
  form.append("payload", JSON.stringify(payload));
  if (state.blob) form.append("image", state.blob, "meal.jpg");
  try {
    await api("/api/meals", { method: "POST", body: form });
    resetCapture();
    await refresh();
  } catch (error) {
    toast(error.message, "error");
    button.disabled = false;
  }
}

function openDialog(id) {
  const dialog = $(id);
  if (!dialog.open) dialog.showModal();
}

function closeDialog(dialog) {
  dialog.close();
}

function fillSettingsForm() {
  const settings = state.settings || {
    daily_goal: 2000,
    protein_goal: 150,
    carbs_goal: 200,
    fat_goal: 65,
    model: "",
    model_is_custom: false,
    default_model: "google/gemini-2.5-flash",
    openrouter: true,
    estimates_ready: false,
    setup_detail: "Set API_KEY before using the model.",
    theme: "lime",
  };
  const fallback = settings.default_model || "";
  $("#goal-input").value = settings.daily_goal;
  $("#protein-goal-input").value = settings.protein_goal || 150;
  $("#carbs-goal-input").value = settings.carbs_goal || 200;
  $("#fat-goal-input").value = settings.fat_goal || 65;
  $("#model-input").value = settings.model_is_custom ? settings.model : "";
  $("#model-input").placeholder = fallback;
  applyTheme(settings.theme || "lime");
  renderAdviceButton();
}

function currentTheme() {
  const value = document.documentElement.dataset.theme;
  if (THEMES.some((theme) => theme.id === value)) return value;
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (THEMES.some((theme) => theme.id === stored)) return stored;
  } catch {
    /* storage can be blocked */
  }
  return "lime";
}

function applyTheme(id) {
  const theme = THEMES.find((item) => item.id === id) || THEMES[0];
  document.documentElement.dataset.theme = theme.id;
  const color = document.querySelector('meta[name="theme-color"]');
  if (color) color.setAttribute("content", theme.bg);
  const scheme = document.querySelector('meta[name="color-scheme"]');
  if (scheme) scheme.setAttribute("content", theme.scheme);
  try {
    localStorage.setItem(THEME_KEY, theme.id);
  } catch {
    /* storage can be blocked */
  }
  renderThemes();
}

function renderThemes() {
  const host = $("#theme-picker");
  if (!host) return;
  const active = currentTheme();
  host.replaceChildren();
  THEMES.forEach((theme) => {
    const selected = theme.id === active;
    const button = el("button", {
      type: "button",
      class: selected ? "theme-swatch selected" : "theme-swatch",
      "aria-pressed": selected ? "true" : "false",
      "aria-label": theme.contrast ? `${theme.name}, high contrast` : theme.name,
    }, [
      el("span", {
        class: "swatch",
        style: `background:${theme.bg};border-color:${theme.accent}`,
      }, el("span", { class: "swatch-dot", style: `background:${theme.accent}` })),
      el("span", { class: "swatch-name" }, theme.name),
    ]);
    button.addEventListener("click", () => chooseTheme(theme.id));
    host.append(button);
  });
}

async function chooseTheme(id) {
  if (id === currentTheme()) return;
  const previous = (state.settings && state.settings.theme) || currentTheme();
  applyTheme(id);
  try {
    state.settings = await api("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: id }),
    });
  } catch (error) {
    applyTheme(previous);
    toast(error.message, "error");
  }
}

function renderAdviceButton() {
  const button = $("#advice-btn");
  if (!button) return;
  const ready = Boolean(state.settings && state.settings.estimates_ready);
  button.hidden = state.date !== todayISO() || !ready;
  button.disabled = state.adviceLoading;
}

function renderAdviceLoading() {
  $("#advice-body").replaceChildren(
    el("div", { class: "advice-loading" }, [
      el("span", { class: "spinner", "aria-hidden": "true" }),
    ]),
  );
}

function renderAdvice(advice) {
  const bits = [];
  if (advice.summary) bits.push(el("p", { class: "advice-summary" }, advice.summary));
  (advice.ideas || []).forEach((idea) => {
    bits.push(el("div", { class: "advice-idea" }, [
      el("div", { class: "advice-idea-top" }, [
        el("h3", {}, idea.title),
        el("p", { class: "advice-kcal num" }, [fmt(idea.calories), el("span", { class: "advice-unit" }, "kcal")]),
      ]),
      idea.detail ? el("p", { class: "advice-detail" }, idea.detail) : null,
    ]));
  });
  $("#advice-body").replaceChildren(...bits);
}

async function askAdvice() {
  if (state.adviceLoading || state.date !== todayISO()) return;
  if (!state.settings || !state.settings.estimates_ready) {
    toast("Model off.", "error");
    return;
  }
  state.adviceLoading = true;
  renderAdviceButton();
  openDialog("#advice-dialog");
  renderAdviceLoading();
  const again = $("#advice-again");
  again.disabled = true;
  try {
    const advice = await api("/api/advice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        date: state.date,
        local_time: new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }),
        timezone_offset_minutes: new Date().getTimezoneOffset(),
      }),
    });
    renderAdvice(advice);
  } catch (error) {
    $("#advice-body").replaceChildren(el("p", { class: "advice-summary" }, error.message));
  } finally {
    state.adviceLoading = false;
    renderAdviceButton();
    again.disabled = false;
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const goal = Number($("#goal-input").value);
  const proteinGoal = Number($("#protein-goal-input").value);
  const carbsGoal = Number($("#carbs-goal-input").value);
  const fatGoal = Number($("#fat-goal-input").value);
  const model = $("#model-input").value.trim();
  try {
    state.settings = await api("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        daily_goal: goal,
        protein_goal: proteinGoal,
        carbs_goal: carbsGoal,
        fat_goal: fatGoal,
        model,
      }),
    });
    fillSettingsForm();
    closeDialog($("#settings-dialog"));
    await refresh();
  } catch (error) {
    toast(error.message, "error");
  }
}

function openSettings(focusId) {
  openDialog("#settings-dialog");
  if (!focusId) return;
  const field = $(focusId);
  if (field) field.focus();
}

async function saveManual(event) {
  event.preventDefault();
  const payload = {
    eaten_on: state.date,
    title: $("#manual-title").value.trim(),
    calories: Number($("#manual-kcal").value),
    protein_g: Number($("#manual-p").value) || 0,
    carbs_g: Number($("#manual-c").value) || 0,
    fat_g: Number($("#manual-f").value) || 0,
  };
  try {
    await api("/api/meals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("#manual-form").reset();
    closeDialog($("#manual-dialog"));
    await refresh();
  } catch (error) {
    toast(error.message, "error");
  }
}

function bindDialog(dialog) {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.querySelectorAll("[data-close]").forEach((button) => {
    button.addEventListener("click", () => dialog.close());
  });
}

$("#prev-day").addEventListener("click", () => setDate(addDays(state.date, -1)));
$("#next-day").addEventListener("click", () => setDate(addDays(state.date, 1)));
$("#date-label").addEventListener("click", openCalendar);
$("#cal-today").addEventListener("click", () => {
  closeDialog($("#calendar-dialog"));
  if (state.date !== todayISO()) setDate(todayISO());
});
$("#open-settings").addEventListener("click", () => openSettings());
$("#open-goal").addEventListener("click", () => openSettings("#goal-input"));
$("#open-protein-goal").addEventListener("click", () => openSettings("#protein-goal-input"));
$("#open-carbs-goal").addEventListener("click", () => openSettings("#carbs-goal-input"));
$("#open-fat-goal").addEventListener("click", () => openSettings("#fat-goal-input"));
$("#open-camera").addEventListener("click", () => fileInput.click());
$("#flip-camera").addEventListener("click", () => openCamera(state.facing === "environment" ? "user" : "environment"));
$("#camera-cancel").addEventListener("click", resetCapture);
$("#shutter").addEventListener("click", takePhoto);
$("#retake").addEventListener("click", resetCapture);
$("#estimate").addEventListener("click", estimate);
$("#open-manual").addEventListener("click", () => openDialog("#manual-dialog"));
$("#advice-btn").addEventListener("click", askAdvice);
$("#advice-again").addEventListener("click", askAdvice);
$("#settings-form").addEventListener("submit", saveSettings);
$("#manual-form").addEventListener("submit", saveManual);
fileInput.addEventListener("change", async () => {
  const file = fileInput.files && fileInput.files[0];
  fileInput.value = "";
  await useFile(file);
});

const capture = $("#capture");
capture.addEventListener("dragover", (event) => {
  event.preventDefault();
  capture.classList.add("drag");
});
capture.addEventListener("dragleave", (event) => {
  if (!capture.contains(event.relatedTarget)) capture.classList.remove("drag");
});
capture.addEventListener("drop", async (event) => {
  event.preventDefault();
  capture.classList.remove("drag");
  const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
  await useFile(file);
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden && state.mode === "camera") resetCapture();
});

window.addEventListener("hashchange", () => {
  if (document.body.classList.contains("gated")) return;
  state.date = readHash();
  refresh();
});

bindDialog($("#settings-dialog"));
bindDialog($("#manual-dialog"));
bindDialog($("#advice-dialog"));
bindDialog($("#calendar-dialog"));

async function submitLogin(event) {
  event.preventDefault();
  const button = event.submitter;
  if (button) button.disabled = true;
  try {
    const auth = await api("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: $("#login-name").value,
        password: $("#login-password").value,
      }),
    });
    $("#login-form").reset();
    await enterApp(auth);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
}

async function submitRegister(event) {
  event.preventDefault();
  const button = event.submitter;
  if (button) button.disabled = true;
  try {
    const auth = await api("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: $("#register-name").value,
        password: $("#register-password").value,
        avatar: state.avatar,
        daily_goal: Number($("#register-goal").value),
        protein_goal: Number($("#register-protein").value),
        carbs_goal: Number($("#register-carbs").value),
        fat_goal: Number($("#register-fat").value),
      }),
    });
    $("#register-form").reset();
    state.avatar = "lemon";
    await enterApp(auth);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
}

async function logout() {
  try {
    await api("/api/logout", { method: "POST" });
  } catch (error) {
    if (error.status !== 401) {
      toast(error.message, "error");
      return;
    }
  }
  closeDialog($("#settings-dialog"));
  state.day = null;
  state.settings = null;
  try {
    showGate(await api("/api/auth"));
  } catch (error) {
    showGate({ authentication: true, has_users: true, avatars: Object.keys(AVATAR_ART) });
  }
}

$("#login-form").addEventListener("submit", submitLogin);
$("#register-form").addEventListener("submit", submitRegister);
$("#show-register").addEventListener("click", () => showAuthMode("register"));
$("#show-login").addEventListener("click", () => showAuthMode("login"));
$("#account-btn").addEventListener("click", () => openSettings());
$("#logout-btn").addEventListener("click", logout);

applyTheme(currentTheme());
api("/api/auth")
  .then((auth) => {
    state.auth = auth;
    if (auth.authentication && !auth.user) {
      showGate(auth);
      return;
    }
    if (auth.user) showAccount(auth.user);
    return loadApp();
  })
  .catch((error) => toast(error.message, "error"));
