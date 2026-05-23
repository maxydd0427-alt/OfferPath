const state = {
  token: localStorage.getItem("offerpath_token") || "",
  resumeId: localStorage.getItem("offerpath_resume_id") || "",
  jobId: localStorage.getItem("offerpath_job_id") || "",
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

function apiBase() {
  return $("apiBase").value.replace(/\/$/, "");
}

function authHeaders(extra = {}) {
  return state.token ? { ...extra, Authorization: `Bearer ${state.token}` } : extra;
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" ? payload.detail || JSON.stringify(payload) : payload;
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return payload;
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  window.setTimeout(() => node.classList.remove("show"), 2800);
}

function setTab(name) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  ["resume", "job", "result"].forEach((tab) => {
    $(`${tab}Tab`).classList.toggle("hidden", tab !== name);
  });
}

function updateStateLabels() {
  $("tokenState").textContent = state.token ? `${state.token.slice(0, 18)}...` : "not logged in";
  $("resumeState").textContent = state.resumeId || "none";
  $("jobState").textContent = state.jobId || "none";
  $("resumeId").value = state.resumeId || $("resumeId").value;
}

async function checkHealth() {
  const badge = $("healthBadge");
  try {
    const payload = await request("/health/ready");
    badge.textContent = `${payload.status} / db ${payload.database} / redis ${payload.redis}`;
    badge.className = `badge ${payload.status === "ok" ? "ok" : "error"}`;
  } catch (error) {
    badge.textContent = "offline";
    badge.className = "badge error";
    toast(error.message);
  }
}

async function register() {
  await request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: $("email").value, password: $("password").value }),
  });
  toast("Registered");
}

async function login(event) {
  event.preventDefault();
  const form = new URLSearchParams();
  form.set("username", $("email").value);
  form.set("password", $("password").value);
  const payload = await request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  state.token = payload.access_token;
  localStorage.setItem("offerpath_token", state.token);
  updateStateLabels();
  toast("Logged in");
  await listResumes();
}

async function uploadResume(event) {
  event.preventDefault();
  const file = $("resumeFile").files[0];
  if (!file) return;
  const form = new FormData();
  form.set("file", file);
  const payload = await request("/resumes", {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  state.resumeId = String(payload.id);
  localStorage.setItem("offerpath_resume_id", state.resumeId);
  updateStateLabels();
  toast(`Uploaded resume ${payload.id}`);
  await listResumes();
  setTab("job");
}

async function listResumes() {
  if (!state.token) return;
  const resumes = await request("/resumes", { headers: authHeaders() });
  $("resumeList").innerHTML = resumes
    .map(
      (resume) => `
        <button class="list-item secondary" type="button" data-resume-id="${resume.id}">
          #${resume.id} ${escapeHtml(resume.original_filename)}
        </button>
      `,
    )
    .join("");
  document.querySelectorAll("[data-resume-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.resumeId = button.dataset.resumeId;
      localStorage.setItem("offerpath_resume_id", state.resumeId);
      updateStateLabels();
      setTab("job");
    });
  });
}

async function createJob(event) {
  event.preventDefault();
  const payload = await request("/jobs", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      resume_id: Number($("resumeId").value),
      target_title: $("targetTitle").value,
      job_description: $("jobDescription").value,
    }),
  });
  state.jobId = String(payload.id);
  localStorage.setItem("offerpath_job_id", state.jobId);
  updateStateLabels();
  toast(`Created job ${payload.id}`);
  setTab("result");
  await refreshJob();
}

async function refreshJob() {
  if (!state.jobId) {
    toast("Create a job first");
    return;
  }
  const payload = await request(`/jobs/${state.jobId}`, { headers: authHeaders() });
  renderJob(payload);
}

function renderJob(job) {
  $("jobSummary").innerHTML = [
    ["Status", job.status],
    ["Provider", job.ai_provider],
    ["Workflow", job.workflow_version],
    ["Prompt", job.prompt_version],
  ]
    .map(([label, value]) => `<div><b>${label}</b>${escapeHtml(String(value || "-"))}</div>`)
    .join("");
  $("resultJson").textContent = JSON.stringify(job, null, 2);
}

function togglePoll() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
    $("pollJob").textContent = "Poll";
    toast("Polling stopped");
    return;
  }
  refreshJob();
  state.pollTimer = window.setInterval(refreshJob, 2500);
  $("pollJob").textContent = "Stop";
  toast("Polling every 2.5s");
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return entities[char];
  });
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => setTab(button.dataset.tab));
});

$("checkHealth").addEventListener("click", checkHealth);
$("registerBtn").addEventListener("click", () => register().catch((error) => toast(error.message)));
$("authForm").addEventListener("submit", (event) => login(event).catch((error) => toast(error.message)));
$("resumeForm").addEventListener("submit", (event) => uploadResume(event).catch((error) => toast(error.message)));
$("jobForm").addEventListener("submit", (event) => createJob(event).catch((error) => toast(error.message)));
$("refreshJob").addEventListener("click", () => refreshJob().catch((error) => toast(error.message)));
$("pollJob").addEventListener("click", togglePoll);

updateStateLabels();
checkHealth();
if (state.token) {
  listResumes().catch(() => undefined);
}
