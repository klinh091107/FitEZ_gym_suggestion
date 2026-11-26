const GROUP_LABELS = {
  LegsFront: "Legs (front)",
  Posterior: "Glutes & hamstrings",
  hip_mobility: "Hip Mobility"
};

// Copy of the logged-in user's profile. The database holds the real one.
let savedProfile = null;
let metadata = null;
let latestResult = null;
let activeGroup = "All";
let catalogLoaded = false;
let catalogRequest = false;
let routinesLoaded = false;
let routinesRequest = false;

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function selectedValues(name) {
  return $$(`input[name="${name}"]:checked`).map((input) => input.value);
}

function collectProfile() {
  return {
    height_cm: Number($("#height").value),
    weight_kg: Number($("#weight").value),
    age: Number($("#age").value),
    bmi_standard: $("#bmi-standard").value,
    level: $("input[name='level']:checked").value,
    goals: selectedValues("goals"),
    equipment: selectedValues("equipment"),
    focus_muscles: selectedValues("focus_muscles"),
    has_pullup_bar: $("#pullup-bar").checked,
    session_min: Number($("#minutes").value),
    sessions_per_day: Number($("#sessions").value),
    days_per_week: Number($("#days").value),
    include_stretch: $("#include-stretch").checked,
    include_hip_mobility: $("#include-hip-mobility").checked
  };
}

// All API calls go through here: it adds the CSRF token and handles expired logins.
async function apiFetch(url, options = {}) {
  const headers = { ...options.headers, "X-CSRF-Token": $("meta[name='csrf-token']").content };
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401 || response.status === 403) {
    window.location.assign("/login");
    throw new Error("Please log in again.");
  }
  return response;
}

// Save the profile to the user's account. Returns true on success.
async function saveProfile(profile) {
  try {
    const response = await apiFetch("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not save your profile.");
    savedProfile = data.profile;
    return true;
  } catch (error) {
    showError(error.message || "Could not save your profile.");
    return false;
  }
}

function setCheckedValues(name, values) {
  $$("input[name=\"" + name + "\"]").forEach((input) => {
    input.checked = values.includes(input.value);
  });
  updateChoiceStyles();
}

function fillForm(profile) {
  $("#height").value = profile.height_cm ?? 165;
  $("#weight").value = profile.weight_kg ?? 65;
  $("#age").value = profile.age ?? 22;
  $("#bmi-standard").value = profile.bmi_standard ?? "asian";

  const level = profile.level ?? "beginner";
  const radio = $(`input[name="level"][value="${level}"]`);
  if (radio) radio.checked = true;

  setCheckedValues("goals", profile.goals ?? ["lose_weight"]);
  setCheckedValues("equipment", profile.equipment ?? ["dumbbell", "machine"]);
  setCheckedValues("focus_muscles", profile.focus_muscles ?? []);

  $("#pullup-bar").checked = Boolean(profile.has_pullup_bar);
  $("#days").value = profile.days_per_week ?? 3;
  $("#minutes").value = profile.session_min ?? 45;
  $("#sessions").value = profile.sessions_per_day ?? 1;
  $("#include-stretch").checked = profile.include_stretch !== false;
  $("#include-hip-mobility").checked = Boolean(profile.include_hip_mobility);

  updateRangeLabels();
  updateChoiceStyles();
  updateChooseAllState();
  updateHipMobilityOption();
  updateBmiPreview();
}

function updateChoiceStyles() {
  $$(".choice-card").forEach((card) => {
    card.classList.toggle("selected", $("input", card).checked);
  });
  $$(".select-pill").forEach((pill) => {
    pill.classList.toggle("selected", $("input", pill).checked);
  });
}

function updateRangeLabels() {
  $("#days-value").textContent = `${$("#days").value} day${$("#days").value === "1" ? "" : "s"} / week`;
  $("#minutes-value").textContent = `${$("#minutes").value} min`;
  $("#sessions-value").textContent = `${$("#sessions").value} session${$("#sessions").value === "1" ? "" : "s"}`;
  updateHipMobilityOption();
}

function calculateBmi(height, weight, standard = "asian") {
  if (!height || !weight || height <= 0) return null;

  const bmi = Math.round((weight / ((height / 100) ** 2)) * 10) / 10;
  let label = "Obese";
  if (bmi < 18.5) {
    label = "Underweight";
  } else if (standard === "asian" && bmi < 23) {
    label = "Normal";
  } else if (standard === "european" && bmi < 25) {
    label = "Normal";
  } else if (standard === "asian" && bmi < 25) {
    label = "Overweight";
  } else if (standard === "european" && bmi < 30) {
    label = "Overweight";
  }
  return { bmi, label };
}

function updateBmiPreview() {
  const standard = $("#bmi-standard").value;
  const bmi = calculateBmi(Number($("#height").value), Number($("#weight").value), standard);
  const standardLabel = standard === "asian" ? "Asian" : "European";
  $("#bmi-preview").textContent = bmi
    ? `Estimated BMI: ${bmi.bmi} · ${bmi.label} (${standardLabel} standard)`
    : "Enter your height and weight to calculate BMI.";
}

function updateHeaderSummary(profile) {
  if (!profile) {
    $("#summary-text").textContent = "Set up your profile";
    return;
  }
  const standard = profile.bmi_standard ?? "asian";
  const bmi = calculateBmi(Number(profile.height_cm), Number(profile.weight_kg), standard);
  const firstGoal = (profile.goals || [])[0]?.replaceAll("_", " ") || "Profile saved";
  $("#summary-text").textContent = bmi ? `BMI ${bmi.bmi} · ${firstGoal}` : "Profile saved";
}

function updateChooseAllState() {
  const equipmentInputs = $$("input[name='equipment']");
  let allSelected = equipmentInputs.length > 0;
  for (const input of equipmentInputs) {
    if (!input.checked) allSelected = false;
  }
  $("#choose-all-equipment").checked = allSelected && $("#pullup-bar").checked;
}

function chooseAllEquipment() {
  const checked = $("#choose-all-equipment").checked;
  $$("input[name='equipment']").forEach((input) => { input.checked = checked; });
  $("#pullup-bar").checked = checked;
  updateChoiceStyles();
}

function updateHipMobilityOption() {
  const sessionMinutes = Number($("#minutes").value);
  const option = $("#hip-mobility-option");
  const available = sessionMinutes > 10;
  option.classList.toggle("hidden", !available);
  if (!available) $("#include-hip-mobility").checked = false;
}

function setLoading(loading) {
  $("#loading-state").classList.toggle("hidden", !loading);
  $("#discover-button").disabled = loading;
  $("#discover-button").classList.toggle("is-loading", loading);
}

function showError(message) {
  const banner = $("#error-banner");
  banner.textContent = message;
  banner.classList.remove("hidden");
}

function hideError() {
  $("#error-banner").classList.add("hidden");
}

async function loadMetadata() {
  const response = await apiFetch("/api/metadata");
  if (!response.ok) throw new Error("Could not load exercise metadata. Refresh the page to try again.");

  metadata = await response.json();
  $("#dataset-count").textContent = metadata.stats.total;
  renderGroupFilters();
  renderProgressionOptions();
  renderCatalogGroupOptions();
}

function renderGroupFilters() {
  const container = $("#group-filters");
  const names = ["All", ...metadata.main_groups];
  container.innerHTML = names.map((group) => {
    const label = group === "All" ? "Today Plan" : (GROUP_LABELS[group] || group);
    return `<button class="filter-chip ${group === activeGroup ? "active" : ""}" data-group="${escapeHtml(group)}">${escapeHtml(label)}</button>`;
  }).join("");

  $$('button[data-group]', container).forEach((button) => {
    button.addEventListener("click", () => {
      activeGroup = button.dataset.group;
      renderGroupFilters();
      renderRecommendations();
    });
  });
}

function renderProgressionOptions() {
  const options = $("#progression-options");
  options.innerHTML = metadata.progression_nodes.map((node) =>
    `<option value="${escapeHtml(node.name)}">${escapeHtml(node.equipment)} · ${escapeHtml(node.level)}</option>`
  ).join("");
}

function renderCatalogGroupOptions() {
  const select = $("#catalog-group");
  let options = '<option value="all">All groups</option>';
  for (const group of metadata.groups) {
    const label = GROUP_LABELS[group] || group;
    options += `<option value="${escapeHtml(group)}">${escapeHtml(label)}</option>`;
  }
  select.innerHTML = options;
}

function clearResults() {
  latestResult = null;
  activeGroup = "All";
  $("#recommendation-count").textContent = "TOP PICKS";
  $("#recommendation-grid").innerHTML = `<div class="empty-state"><span class="empty-icon">✳</span><h3>Your exercises will appear here</h3><p>Press Discover to find exercises matched to your profile.</p></div>`;
  $("#schedule-days").textContent = "—";
  $("#schedule-exercises").textContent = "—";
  $("#schedule-minutes").textContent = "—";
  $("#schedule-list").innerHTML = `<div class="empty-state"><span class="empty-icon">▦</span><h3>Your training plan is waiting</h3><p>Press Discover to generate your training days.</p></div>`;
  renderGroupFilters();
}

async function saveProfileForm(event) {
  event.preventDefault();
  hideError();
  const form = $("#profile-form");
  if (!form.reportValidity()) return;

  const profile = collectProfile();
  if (!profile.goals.length) {
    showError("Please select at least one training goal.");
    return;
  }
  if (!(await saveProfile(profile))) return;

  clearResults();
  updateHeaderSummary(savedProfile);
  $("#profile-save-status").classList.remove("hidden");
  switchTab("today-exercise");
}

async function generatePlan() {
  hideError();
  if (!savedProfile) {
    switchTab("profile");
    showError("Please complete and save your profile before discovering exercises.");
    return;
  }

  setLoading(true);
  try {
    // The server builds the plan from the profile stored for this account.
    const response = await apiFetch("/api/recommend", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to generate your workout plan.");

    latestResult = data;
    activeGroup = "All";
    renderGroupFilters();
    renderRecommendations();
    renderSchedule();
    updateHeaderSummary(data.profile);
  } catch (error) {
    showError(error.message || "Something went wrong.");
  } finally {
    setLoading(false);
  }
}

// The picture of the exercise's primary muscle. Without one, the card keeps its group colour.
function exerciseVisual(exercise, index, groupLabel) {
  const number = `<span class="visual-index">${String(index + 1).padStart(2, "0")}</span>`;
  const muscle = String(exercise.primary_muscle || "").toLowerCase();
  const image = metadata?.muscle_images?.[muscle];
  if (image) {
    return `<div class="exercise-visual has-image">${number}<img src="${escapeHtml(image)}" alt="${escapeHtml(exercise.primary_muscle)} muscle"></div>`;
  }
  return `<div class="exercise-visual group-${escapeHtml(exercise.group)}">${number}<span class="visual-group">${escapeHtml(groupLabel)}</span></div>`;
}

function exerciseCard(exercise, index, featured = false) {
  const groupLabel = GROUP_LABELS[exercise.group] || exercise.group;
  const steps = (exercise.step_list || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("");
  const description = `${exercise.primary_muscle || groupLabel} · ${exercise.mechanic || "Exercise"} movement`;
  return `<article class="exercise-card ${featured ? "featured" : ""}">
    ${exerciseVisual(exercise, index, groupLabel)}
    <div class="exercise-content"><div class="exercise-topline"><span class="mini-tag">${escapeHtml(exercise.level)}</span><span class="mini-tag">${escapeHtml(exercise.category)}</span><span class="score-tag">${exercise.score ?? ""} PTS</span>${exercise.beginner_bonus ? '<span class="bonus-tag">BEGINNER +1</span>' : ""}</div>
    <h3>${escapeHtml(exercise.name)}</h3><p class="exercise-desc">${escapeHtml(description)}</p>
    <div class="exercise-meta"><span class="meta-chip">◷ ${exercise.duration_min} min</span><span class="meta-chip">▣ ${escapeHtml(exercise.equipment)}</span><span class="meta-chip">${escapeHtml(exercise.primary_muscle)}</span></div>
    ${steps ? `<details class="exercise-details"><summary>How to perform</summary><ol>${steps}</ol></details>` : ""}</div>
  </article>`;
}

function renderRecommendations() {
  const grid = $("#recommendation-grid");
  if (!latestResult) return;

  let exercises = latestResult.top_k;
  if (activeGroup !== "All") exercises = latestResult.by_group[activeGroup] || [];
  const totalMinutes = exercises.reduce((total, exercise) => total + exercise.duration_min, 0);
  // Plans saved before the time limit was added have no today_minutes.
  const timeLabel = latestResult.today_minutes ? ` · ${totalMinutes}/${latestResult.today_minutes} MIN` : "";
  $("#recommendation-count").textContent = `${exercises.length} ${activeGroup === "All" ? "TOP PICKS" : "IN GROUP"}${timeLabel}`;

  if (!exercises.length) {
    grid.innerHTML = `<div class="empty-state"><span class="empty-icon">✳</span><h3>No matches in this group</h3><p>Try another group, add more equipment or increase your minutes per session.</p></div>`;
    return;
  }
  grid.innerHTML = exercises.map((exercise, index) => exerciseCard(exercise, index, index === 0)).join("");
}

function renderProgression(progression) {
  $("#progression-note").textContent = progression.note;
  const container = $("#progression-track");
  if (!progression.path.length) {
    container.innerHTML = `<div class="empty-state slim"><span class="empty-icon">↗</span><h3>No progression path found</h3><p>Try another target exercise from the search list.</p></div>`;
    return;
  }

  let markup = "";
  progression.path.forEach((exercise, index) => {
    markup += `<article class="progression-step ${index === 0 ? "start" : ""}"><span class="step-number">STEP ${String(index + 1).padStart(2, "0")}</span><h3>${escapeHtml(exercise.name)}</h3><p>Equipment: <strong>${escapeHtml(exercise.equipment)}</strong></p><p>Muscle group: ${escapeHtml(GROUP_LABELS[exercise.group] || exercise.group)}</p><span class="step-level">${escapeHtml(exercise.level)}</span></article>`;
    if (index < progression.path.length - 1) markup += `<span class="step-arrow">→</span>`;
  });
  container.innerHTML = markup;
}

async function findProgression() {
  const target = $("#target-exercise").value.trim();
  const note = $("#progression-note");
  const container = $("#progression-track");
  if (!target) {
    note.textContent = "Please choose a target exercise first.";
    return;
  }

  const button = $("#find-progression-button");
  button.disabled = true;
  button.classList.add("is-loading");
  note.textContent = "Finding the shortest progression path…";

  try {
    const response = await apiFetch(`/api/progression?target=${encodeURIComponent(target)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not find a progression path.");
    renderProgression(data);
  } catch (error) {
    note.textContent = error.message || "Something went wrong. Please try again.";
    container.innerHTML = `<div class="empty-state slim"><span class="empty-icon">↗</span><h3>Could not find a path</h3><p>Choose an exercise from the suggestion list and try again.</p></div>`;
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
  }
}

function renderSchedule() {
  if (!latestResult) return;
  const days = latestResult.schedule;
  let totalExercises = 0;
  let totalMinutes = 0;

  days.forEach((day) => {
    totalExercises += day.exercises.length + day.warm_up.length + day.cool_down.length + day.hip_mobility.length;
    // Includes Hip Mobility; warm-up and cool-down are outside the time budget.
    totalMinutes += day.total_minutes;
  });

  $("#schedule-days").textContent = days.length;
  $("#schedule-exercises").textContent = totalExercises;
  $("#schedule-minutes").textContent = totalMinutes;

  const mobilityChoice = savedProfile && savedProfile.include_hip_mobility;
  $("#plan-mobility-note").textContent = mobilityChoice
    ? "Hip Mobility is included in each training day."
    : "Hip Mobility is not included. You can turn it on from your Profile settings.";

  const container = $("#schedule-list");
  if (!days.length) {
    container.innerHTML = `<div class="empty-state"><h3>No training days</h3><p>Update your schedule settings and try again.</p></div>`;
    return;
  }

  container.innerHTML = days.map((day) => {
    const warmUpMarkup = day.warm_up.length
      ? `<div class="warmup-block"><div class="warmup-title">✦ WARM-UP</div>${day.warm_up.map((exercise) => `<p>${escapeHtml(exercise.name)} · ${exercise.duration_min} min</p>`).join("")}</div>`
      : "";

    // Hip Mobility is listed and counted like any other exercise.
    const sessionExercises = [...day.exercises, ...day.hip_mobility];
    const exerciseMarkup = sessionExercises.map((exercise, index) =>
      `<div class="day-exercise"><span class="day-index">${index + 1}</span><div><strong>${escapeHtml(exercise.name)}</strong><small>${escapeHtml(GROUP_LABELS[exercise.group] || exercise.group)} · ${exercise.duration_min} min · ${escapeHtml(exercise.equipment)}</small></div></div>`
    ).join("");

    const coolDownMarkup = day.cool_down.length
      ? `<div class="cooldown-block"><div class="cooldown-title">✦ COOL-DOWN</div>${day.cool_down.map((exercise) => `<p>${escapeHtml(exercise.name)} · ${exercise.duration_min} min</p>`).join("")}</div>`
      : "";

    const warning = day.min_groups_met
      ? ""
      : `<div class="day-warning">Not enough time or eligible exercises to cover 3 groups. This day shows the best available selection.</div>`;

    return `<article class="day-card"><header class="day-header"><h3>${day.day}</h3><span>${day.total_minutes} MIN · ${sessionExercises.length} EXERCISES</span></header><div class="day-body">${warmUpMarkup}${exerciseMarkup || `<p class="muted-copy">No exercises fit the current filters.</p>`}${coolDownMarkup}${warning}</div></article>`;
  }).join("");
}

async function loadCatalog() {
  if (catalogRequest) return;
  catalogRequest = true;
  const group = $("#catalog-group").value;
  const level = $("#catalog-level").value;
  const container = $("#catalog-list");
  container.innerHTML = `<div class="empty-state"><span class="empty-icon">▤</span><h3>Loading exercises</h3><p>Reading the exercise dataset.</p></div>`;

  try {
    const response = await apiFetch(`/api/exercises?group=${encodeURIComponent(group)}&level=${encodeURIComponent(level)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load the exercise library.");
    renderCatalog(data.exercises, data.count);
    catalogLoaded = true;
  } catch (error) {
    container.innerHTML = `<div class="empty-state"><h3>Could not load exercises</h3><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    catalogRequest = false;
  }
}

function renderCatalog(exercises, count) {
  $("#all-exercise-count").textContent = `${count} EXERCISES`;
  const container = $("#catalog-list");
  if (count === 0) {
    container.innerHTML = `<div class="empty-state"><h3>No exercises found</h3><p>Try another group or experience level.</p></div>`;
    return;
  }

  const groupedExercises = {};
  for (const group of metadata.groups) groupedExercises[group] = [];
  for (const exercise of exercises) {
    if (!groupedExercises[exercise.group]) groupedExercises[exercise.group] = [];
    groupedExercises[exercise.group].push(exercise);
  }

  let markup = "";
  for (const group of metadata.groups) {
    const groupExercises = groupedExercises[group] || [];
    if (groupExercises.length === 0) continue;

    const groupLabel = GROUP_LABELS[group] || group;
    markup += `<section class="catalog-group"><header class="catalog-group-heading"><h3>${escapeHtml(groupLabel)}</h3><span>${groupExercises.length} exercises</span></header><div class="catalog-group-items">`;

    for (let index = 0; index < groupExercises.length; index += 1) {
      const exercise = groupExercises[index];
      markup += `<article class="catalog-item">
        <div class="catalog-item-number">${String(index + 1).padStart(3, "0")}</div>
        <div class="catalog-item-main"><h3>${escapeHtml(exercise.name)}</h3><p>${escapeHtml(exercise.primary_muscle)} · ${escapeHtml(groupLabel)}</p></div>
        <div class="catalog-item-tags"><span>${escapeHtml(exercise.level)}</span><span>${escapeHtml(exercise.equipment)}</span><span>${exercise.duration_min} min</span></div>
      </article>`;
    }
    markup += `</div></section>`;
  }
  container.innerHTML = markup;
}

async function loadWorkoutSets() {
  if (routinesLoaded || routinesRequest) return;
  routinesRequest = true;
  const container = $("#routine-grid");
  container.innerHTML = `<div class="empty-state"><span class="empty-icon">✳</span><h3>Loading quick routines</h3><p>Preparing your short workout sets.</p></div>`;

  try {
    const response = await apiFetch("/api/workout-sets");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load quick routines.");
    renderWorkoutSets(data.sets);
    routinesLoaded = true;
  } catch (error) {
    container.innerHTML = `<div class="empty-state"><h3>Could not load routines</h3><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    routinesRequest = false;
  }
}

function renderWorkoutSets(sets) {
  $("#routine-count").textContent = `${sets.length} ROUTINES`;
  const container = $("#routine-grid");
  let markup = "";

  sets.forEach((routine) => {
    let exerciseMarkup = "";
    routine.exercises.forEach((exercise, exerciseIndex) => {
      const steps = (exercise.step_list || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("");
      exerciseMarkup += `<article class="routine-exercise"><div class="routine-exercise-number">${String(exerciseIndex + 1).padStart(2, "0")}</div><div class="routine-exercise-content"><div class="routine-exercise-heading"><strong>${escapeHtml(exercise.name)}</strong><span>${exercise.duration_min} min</span></div><small>${escapeHtml(exercise.primary_muscle || GROUP_LABELS[exercise.group] || exercise.group)} · ${escapeHtml(exercise.level)} · ${escapeHtml(exercise.equipment)}</small>${steps ? `<details class="exercise-details"><summary>How to perform</summary><ol>${steps}</ol></details>` : ""}</div></article>`;
    });

    markup += `<article class="routine-card"><div class="routine-card-top"><span class="routine-tag">${escapeHtml(routine.tag)}</span><span class="routine-duration">${routine.duration_min} MIN</span></div><h3>${escapeHtml(routine.title)}</h3><p class="routine-description">${escapeHtml(routine.description)}</p><div class="routine-meta"><span>${escapeHtml(routine.level)}</span><span>${escapeHtml(routine.equipment)}</span></div><div class="routine-exercises">${exerciseMarkup}</div></article>`;
  });

  container.innerHTML = markup;
}

function switchTab(tabName) {
  $$(".nav-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  $$(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });
  hideError();
  if (tabName === "all-exercise" && !catalogLoaded) loadCatalog();
  if (tabName === "quick-routines" && !routinesLoaded) loadWorkoutSets();
}

function setupEvents() {
  $("#profile-form").addEventListener("submit", saveProfileForm);
  $("#discover-button").addEventListener("click", generatePlan);
  $("#find-progression-button").addEventListener("click", findProgression);
  $("#target-exercise").addEventListener("keydown", (event) => {
    if (event.key === "Enter") findProgression();
  });
  $$(".nav-tab").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });

  ["#days", "#minutes", "#sessions"].forEach((selector) => {
    $(selector).addEventListener("input", updateRangeLabels);
  });
  ["#height", "#weight"].forEach((selector) => {
    $(selector).addEventListener("input", updateBmiPreview);
  });
  $("#bmi-standard").addEventListener("change", updateBmiPreview);

  $("#profile-form").addEventListener("change", () => {
    updateChoiceStyles();
    updateChooseAllState();
  });
  $("#choose-all-equipment").addEventListener("change", chooseAllEquipment);

  $("#include-stretch").addEventListener("change", async () => {
    if (!savedProfile) return;
    const toggle = $("#include-stretch");
    const hadPlan = latestResult !== null;
    toggle.disabled = true;
    const profile = { ...savedProfile, include_stretch: toggle.checked };
    if (!(await saveProfile(profile))) {
      toggle.checked = !toggle.checked;
    } else if (hadPlan) {
      await generatePlan();
    }
    toggle.disabled = false;
  });
  $("#catalog-group").addEventListener("change", loadCatalog);
  $("#catalog-level").addEventListener("change", loadCatalog);
}

async function initialise() {
  setupEvents();
  updateRangeLabels();
  updateBmiPreview();

  try {
    // Remove the old browser-only profile so it is never shared between accounts.
    localStorage.removeItem("fitez_profile_v1");
    await loadMetadata();
    const response = await apiFetch("/api/profile");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load your profile.");
    savedProfile = data.profile;

    if (savedProfile) {
      fillForm(savedProfile);
      updateHeaderSummary(savedProfile);
      switchTab("today-exercise");
      if (data.plan) {
        latestResult = data.plan;
        renderRecommendations();
        renderSchedule();
      }
    } else {
      fillForm({});
      updateHeaderSummary(null);
      switchTab("profile");
    }
  } catch (error) {
    showError(error.message);
  }
}

document.addEventListener("DOMContentLoaded", initialise);
