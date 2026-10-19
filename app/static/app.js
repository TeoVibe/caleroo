const $ = (selector) => document.querySelector(selector);

const state = {
  date: "",
  day: null,
  week: null,
  settings: null,
  mode: "idle",
  blob: null,
  previewUrl: null,
  stream: null,
  facing: "environment",
  estimate: null,
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
    throw new Error(typeof detail === "string" ? detail : "Request failed.");
  }
  return data;
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
    const [day, week] = await Promise.all([
      api(`/api/days/${state.date}`),
      api(`/api/weeks/${state.date}`),
    ]);
    state.day = day;
    state.week = week;
    renderSummary();
    renderMeals();
    renderWeek();
    renderDate();
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderDate() {
  const label = labelFor(state.date);
  $("#date-label").textContent = label;
  $("#summary-kicker").textContent = label;
  $("#log-for").textContent = label;
  $("#next-day").disabled = state.date >= todayISO();
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
  $("#open-goal").textContent = `Goal ${fmt(goal)}`;
  const macros = $("#macros");
  macros.replaceChildren();
  [
    ["Protein", totals.protein_g],
    ["Carbs", totals.carbs_g],
    ["Fat", totals.fat_g],
  ].forEach(([name, value]) => {
    macros.append(el("div", {}, [el("dt", {}, name), el("dd", { class: "num" }, `${grams(value)}g`)]));
  });
  const ring = $("#ring-value");
  const length = 2 * Math.PI * 46;
  const pct = goal > 0 ? Math.min(totals.calories / goal, 1) : 0;
  ring.style.strokeDasharray = String(length);
  ring.style.strokeDashoffset = String(length * (1 - pct));
  ring.classList.toggle("over", over);
}

function renderMeals() {
  const meals = state.day.meals;
  const host = $("#meals");
  host.replaceChildren();
  $("#meal-count").textContent = meals.length === 1 ? "1 meal" : meals.length ? `${meals.length} meals` : "";
  if (!meals.length) {
    host.append(el("div", { class: "empty" }, [
      el("p", { class: "empty-title" }, "Nothing logged"),
      el("p", {}, "A photo of the plate is enough to start."),
    ]));
    return;
  }
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
  if (meal.model) bits.push(el("p", { class: "detail-notes" }, meal.model));
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
    toast("Meal removed");
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
  const max = Math.max(goal, ...days.map((day) => day.calories), 1);
  days.forEach((day) => {
    const [year, month, date] = day.date.split("-").map(Number);
    const weekday = new Date(year, month - 1, date).toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2);
    const over = goal > 0 && day.calories > goal;
    const selected = day.date === state.date;
    const track = el("span", { class: selected ? "bar-track selected" : "bar-track" });
    if (day.calories > 0) {
      const bar = el("span", { class: `bar${over ? " over" : ""}${selected && !over ? " on" : ""}` });
      bar.style.height = `${Math.max(8, Math.round((day.calories / max) * 100))}%`;
      track.append(bar);
    }
    const button = el("button", {
      class: selected ? "bar-btn selected" : "bar-btn",
      type: "button",
      "aria-label": `${labelFor(day.date)}, ${fmt(day.calories)} kcal`,
      onclick: () => setDate(day.date),
    }, [track, el("span", { class: "dow" }, weekday)]);
    host.append(button);
  });
}

function showMode(mode) {
  state.mode = mode;
  $("#cap-idle").hidden = mode !== "idle";
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
    toast("Could not read that photo. Try a JPEG or PNG.", "error");
  }
}

function cameraMessage(error) {
  if (!window.isSecureContext || !navigator.mediaDevices) {
    return "The camera needs localhost or HTTPS. Uploading a photo still works.";
  }
  if (error && error.name === "NotAllowedError") return "Camera permission was blocked. You can upload a photo instead.";
  if (error && error.name === "NotFoundError") return "No camera was found. You can upload a photo instead.";
  return "Could not open the camera. You can upload a photo instead.";
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
    toast("The camera is not ready yet.");
    return;
  }
  const scale = Math.min(1, 1600 / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.86));
  if (!blob) {
    toast("Could not capture that frame.", "error");
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
  const confidence = estimate.confidence || "low";
  root.replaceChildren(
    el("div", { class: "review-head" }, [
      el("p", { class: "kicker" }, "Check the estimate"),
      el("p", { class: `pill ${confidence}` }, confidence),
    ]),
    estimate.items && estimate.items.length
      ? el("p", { class: "hint" }, "Change anything that looks wrong. The log uses these numbers.")
      : el("p", { class: "hint" }, "No food stood out in that photo. Add it yourself, or choose another."),
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
    toast("Name at least one food.");
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
    const saved = await api("/api/meals", { method: "POST", body: form });
    toast(`Logged ${fmt(saved.calories)} kcal`);
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
    model: "",
    model_is_custom: false,
    inference: "openrouter",
    estimates_ready: false,
  };
  const local = settings.inference === "local";
  $("#goal-input").value = settings.daily_goal;
  $("#model-input").value = settings.model_is_custom ? settings.model : "";
  $("#model-input").placeholder = settings.model || (local ? "vision model name" : "google/gemini-2.5-flash");
  $("#model-label").textContent = local ? "Model" : "OpenRouter model";
  $("#model-hint").textContent = local
    ? "Leave the model blank to use LOCAL_MODEL. It has to accept images."
    : "Leave the model blank to use OPENROUTER_MODEL from the server. It has to accept images.";
  if (settings.inference !== "openrouter" && settings.inference !== "local") {
    $("#banner-detail").textContent = "Set INFERENCE to openrouter or local, then restart.";
    $("#key-status").textContent = "INFERENCE must be openrouter or local.";
  } else if (local) {
    $("#banner-detail").textContent = "Set LOCAL_BASE_URL and LOCAL_MODEL, then restart. You can still log meals by hand.";
    $("#key-status").textContent = settings.estimates_ready
      ? "Using a local OpenAI-compatible server."
      : "No local endpoint configured yet.";
  } else {
    $("#banner-detail").textContent = "Add OPENROUTER_API_KEY and restart. You can still log meals by hand.";
    $("#key-status").textContent = settings.estimates_ready
      ? "OpenRouter key is set on the server."
      : "No OpenRouter key on the server yet.";
  }
  const via = local ? "local" : "OpenRouter";
  $("#model-note").textContent = settings.model ? `Estimating with ${settings.model} via ${via}` : "";
  $("#key-banner").hidden = Boolean(settings.estimates_ready);
}

async function saveSettings(event) {
  event.preventDefault();
  const goal = Number($("#goal-input").value);
  const model = $("#model-input").value.trim();
  try {
    state.settings = await api("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ daily_goal: goal, model }),
    });
    fillSettingsForm();
    closeDialog($("#settings-dialog"));
    toast("Settings saved");
    await refresh();
  } catch (error) {
    toast(error.message, "error");
  }
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
    const saved = await api("/api/meals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("#manual-form").reset();
    closeDialog($("#manual-dialog"));
    toast(`Logged ${fmt(saved.calories)} kcal`);
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
$("#date-label").addEventListener("click", () => setDate(todayISO()));
$("#open-settings").addEventListener("click", () => openDialog("#settings-dialog"));
$("#open-goal").addEventListener("click", () => openDialog("#settings-dialog"));
$("#open-camera").addEventListener("click", () => fileInput.click());
$("#flip-camera").addEventListener("click", () => openCamera(state.facing === "environment" ? "user" : "environment"));
$("#camera-cancel").addEventListener("click", resetCapture);
$("#shutter").addEventListener("click", takePhoto);
$("#retake").addEventListener("click", resetCapture);
$("#estimate").addEventListener("click", estimate);
$("#open-manual").addEventListener("click", () => openDialog("#manual-dialog"));
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
  state.date = readHash();
  refresh();
});

bindDialog($("#settings-dialog"));
bindDialog($("#manual-dialog"));

state.date = readHash();
if (location.hash !== `#${state.date}`) history.replaceState(null, "", `#${state.date}`);
api("/api/settings")
  .then((settings) => {
    state.settings = settings;
    fillSettingsForm();
  })
  .catch((error) => toast(error.message, "error"))
  .finally(refresh);
