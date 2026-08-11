const state = {
  profile: null,
  readiness: null,
  activeJob: null,
  jobTimer: null,
};

const elements = {
  healthBadge: document.querySelector("#healthBadge"),
  envPath: document.querySelector("#envPath"),
  profileId: document.querySelector("#profileId"),
  displayName: document.querySelector("#displayName"),
  repoRoot: document.querySelector("#repoRoot"),
  importButton: document.querySelector("#importButton"),
  saveButton: document.querySelector("#saveButton"),
  validateButton: document.querySelector("#validateButton"),
  savedProfiles: document.querySelector("#savedProfiles"),
  profileSummary: document.querySelector("#profileSummary"),
  readinessStatus: document.querySelector("#readinessStatus"),
  readinessSummary: document.querySelector("#readinessSummary"),
  agentPrompt: document.querySelector("#agentPrompt"),
  commandMode: document.querySelector("#commandMode"),
  smokeButton: document.querySelector("#smokeButton"),
  agentAskButton: document.querySelector("#agentAskButton"),
  jobStatus: document.querySelector("#jobStatus"),
  jobMeta: document.querySelector("#jobMeta"),
  jobLog: document.querySelector("#jobLog"),
};

elements.importButton.addEventListener("click", () => importProfile());
elements.saveButton.addEventListener("click", () => saveProfile());
elements.validateButton.addEventListener("click", () => validateSources());
elements.smokeButton.addEventListener("click", () => startSmokeJob());
elements.agentAskButton.addEventListener("click", () => startAgentAsk());

checkHealth();
loadSavedProfiles();

async function checkHealth() {
  try {
    const payload = await requestJson("/api/health");
    setStatus(elements.healthBadge, payload.status === "ok" ? "pass" : "warn", payload.status === "ok" ? "已连接" : "异常");
  } catch (error) {
    setStatus(elements.healthBadge, "fail", "未连接");
  }
}

async function loadSavedProfiles() {
  try {
    const payload = await requestJson("/api/profiles");
    renderSavedProfiles(payload.profiles || []);
  } catch (error) {
    elements.savedProfiles.innerHTML = `<h3>已保存 Profile</h3><p>读取失败：${escapeHtml(error.message || error)}</p>`;
  }
}

async function importProfile() {
  withBusy(elements.importButton, "导入中", async () => {
    const payload = await requestJson("/api/profiles/import-env", {
      method: "POST",
      body: JSON.stringify(importPayload()),
    });
    state.profile = payload;
    renderProfile(payload);
    await validateSources();
  });
}

async function saveProfile() {
  withBusy(elements.saveButton, "保存中", async () => {
    if (!state.profile) {
      state.profile = await requestJson("/api/profiles/import-env", {
        method: "POST",
        body: JSON.stringify(importPayload()),
      });
      renderProfile(state.profile);
    }
    await requestJson("/api/profiles", {
      method: "POST",
      body: JSON.stringify(state.profile),
    });
    await loadSavedProfiles();
  });
}

async function validateSources() {
  withBusy(elements.validateButton, "检查中", async () => {
    const body = state.profile
      ? {
          profile: state.profile,
          repo_root: elements.repoRoot.value.trim() || ".",
        }
      : {
          ...importPayload(),
          repo_root: elements.repoRoot.value.trim() || ".",
        };
    const payload = await requestJson("/api/profiles/validate", {
      method: "POST",
      body: JSON.stringify(body),
    });
    state.readiness = payload;
    if (!state.profile) {
      state.profile = await requestJson("/api/profiles/import-env", {
        method: "POST",
        body: JSON.stringify(importPayload()),
      });
      renderProfile(state.profile);
    }
    renderReadiness(payload);
  });
}

async function loadProfile(profileId) {
  const payload = await requestJson(`/api/profiles/${encodeURIComponent(profileId)}`);
  state.profile = payload;
  elements.profileId.value = payload.profile_id || "";
  elements.displayName.value = payload.display_name || "";
  if (payload.env_file) {
    elements.envPath.value = payload.env_file;
  }
  renderProfile(payload);
  await validateSources();
}

async function startSmokeJob() {
  withBusy(elements.smokeButton, "启动中", async () => {
    const payload = await requestJson("/api/runs/smoke", {
      method: "POST",
      body: JSON.stringify({ profile_id: state.profile?.profile_id || null }),
    });
    state.activeJob = payload.job;
    elements.jobLog.textContent = "";
    renderJob(payload.job, []);
    await refreshJob(payload.job.job_id);
    startJobPolling(payload.job.job_id);
  });
}

async function startAgentAsk() {
  withBusy(elements.agentAskButton, "启动中", async () => {
    if (!state.profile) {
      throw new Error("请先导入或加载 Profile。");
    }
    const payload = await requestJson("/api/runs/ask", {
      method: "POST",
      body: JSON.stringify({
        profile: state.profile,
        prompt: elements.agentPrompt.value.trim(),
        command_mode: elements.commandMode.value,
      }),
    });
    state.activeJob = payload.job;
    elements.jobLog.textContent = "";
    renderJob(payload.job, []);
    await refreshJob(payload.job.job_id);
    startJobPolling(payload.job.job_id);
  });
}

async function refreshJob(jobId) {
  const [run, events] = await Promise.all([
    requestJson(`/api/runs/${encodeURIComponent(jobId)}`),
    requestJson(`/api/runs/${encodeURIComponent(jobId)}/events`),
  ]);
  state.activeJob = run.job;
  renderJob(run.job, events.events || []);
  if (isTerminal(run.job.status)) {
    stopJobPolling();
  }
}

function startJobPolling(jobId) {
  stopJobPolling();
  state.jobTimer = window.setInterval(() => refreshJob(jobId).catch(renderRequestError), 1200);
}

function stopJobPolling() {
  if (state.jobTimer) {
    window.clearInterval(state.jobTimer);
    state.jobTimer = null;
  }
}

function importPayload() {
  return {
    env_path: elements.envPath.value.trim(),
    profile_id: elements.profileId.value.trim() || null,
    display_name: elements.displayName.value.trim() || null,
  };
}

function renderJob(job, events) {
  const status = jobStatus(job);
  setStatus(elements.jobStatus, status, job?.status || "未启动");
  elements.jobMeta.textContent = job ? `${job.job_id} · ${job.job_type} · ${job.status}` : "尚未启动";
  elements.jobLog.textContent = events.length
    ? events.map((event) => `[${event.sequence}] ${event.stream}: ${event.message}`).join("\n")
    : "运行本地 smoke 或单轮 Agent 后，这里会显示 stdout/system 事件。";
}

function renderProfile(profile) {
  const sources = profile.sources || {};
  const route = profile.model_route || {};
  const runtime = profile.runtime || {};
  elements.profileSummary.className = "summary-grid";
  elements.profileSummary.innerHTML = [
    metricBox("Profile", profile.display_name || profile.profile_id, profile.profile_id),
    metricBox("模型路由", route.model_name || route.backend || "未配置", route.base_url || ""),
    metricBox("密钥环境变量", route.api_key_env || "未配置", "不保存真实 key"),
    metricBox("Source policy", sources.source_policy || "未配置", ""),
    metricBox("Market snapshot", sources.market_snapshot_id || "未配置", sources.market_as_of_date || ""),
    metricBox("运行设置", `${runtime.execution_shell || "auto"} · ${runtime.bge_device || "cpu"}`, runtime.wsl_repo_root || runtime.python || "python"),
  ].join("");
}

function renderSavedProfiles(profiles) {
  if (!profiles.length) {
    elements.savedProfiles.className = "saved-profiles empty-state";
    elements.savedProfiles.innerHTML = "<h3>已保存 Profile</h3><p>还没有保存过 profile。</p>";
    return;
  }
  elements.savedProfiles.className = "saved-profiles";
  elements.savedProfiles.innerHTML = `
    <h3>已保存 Profile</h3>
    <div class="saved-profile-list">
      ${profiles.map((profile) => savedProfileButton(profile)).join("")}
    </div>
  `;
  elements.savedProfiles.querySelectorAll("[data-profile-id]").forEach((button) => {
    button.addEventListener("click", () => loadProfile(button.dataset.profileId));
  });
}

function savedProfileButton(profile) {
  return `
    <button class="saved-profile-button" type="button" data-profile-id="${escapeHtml(profile.profile_id)}">
      ${escapeHtml(profile.display_name || profile.profile_id)}
      <span>${escapeHtml(profile.source_policy || "source policy 未配置")}</span>
    </button>
  `;
}

function renderReadiness(report) {
  setStatus(elements.readinessStatus, report.status, statusLabel(report.status));
  elements.readinessSummary.className = "readiness-layout";
  elements.readinessSummary.innerHTML = `
    <div class="summary-grid">
      ${metricBox("Manifest 行数", numberText(report.manifest?.row_count), `${numberText(report.manifest?.ticker_count)} tickers`)}
      ${metricBox("财年范围", listText(report.manifest?.years), "来自 manifest")}
      ${metricBox("市场快照行数", numberText(report.market_evidence?.row_count), `${numberText(report.market_evidence?.ticker_count)} tickers`)}
    </div>
    <div class="readiness-columns">
      <div>
        <h3>产物路径</h3>
        <div class="table-wrap">${pathTable(report.paths || [])}</div>
      </div>
      <div>
        <h3>覆盖摘要</h3>
        ${coverageBlocks(report)}
      </div>
    </div>
    <div class="readiness-columns">
      ${messageBlock("Warnings", report.warnings || [], "warn")}
      ${messageBlock("Errors", report.errors || [], "fail")}
    </div>
  `;
}

function pathTable(paths) {
  const rows = paths
    .map(
      (item) => `
        <tr>
          <td class="mono">${escapeHtml(item.name)}</td>
          <td>${statusBadge(item.status)}</td>
          <td>${escapeHtml(item.kind)}</td>
          <td class="mono">${escapeHtml(item.path || "未配置")}</td>
          <td>${escapeHtml(item.reason || "")}</td>
        </tr>
      `,
    )
    .join("");
  return `
    <table>
      <thead><tr><th>产物</th><th>状态</th><th>类型</th><th>路径</th><th>原因</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function coverageBlocks(report) {
  return `
    <div class="list-block">
      <h3>披露文件类型</h3>
      ${kvList(report.manifest?.form_counts)}
    </div>
    <div class="list-block">
      <h3>证据层级</h3>
      ${kvList(report.manifest?.source_tier_counts)}
    </div>
    <div class="list-block">
      <h3>市场快照字段</h3>
      ${kvList(report.market_evidence?.field_counts)}
    </div>
  `;
}

function messageBlock(title, rows, status) {
  const content = rows.length
    ? `<ul>${rows.map((row) => `<li>${escapeHtml(row)}</li>`).join("")}</ul>`
    : `<p>无</p>`;
  return `<div class="list-block"><h3>${escapeHtml(title)} ${statusBadge(rows.length ? status : "pass")}</h3>${content}</div>`;
}

function metricBox(label, value, detail) {
  return `
    <div class="metric-box">
      <div class="label">${escapeHtml(label)}</div>
      <div class="value">${escapeHtml(value || "未配置")}</div>
      ${detail ? `<div class="mono">${escapeHtml(detail)}</div>` : ""}
    </div>
  `;
}

function kvList(payload) {
  const entries = Object.entries(payload || {});
  if (!entries.length) {
    return "<p>无数据</p>";
  }
  return `<ul>${entries.map(([key, value]) => `<li><span class="mono">${escapeHtml(key)}</span>: ${escapeHtml(value)}</li>`).join("")}</ul>`;
}

function statusBadge(status) {
  return `<span class="status-pill ${escapeHtml(status || "neutral")}">${escapeHtml(statusLabel(status))}</span>`;
}

function setStatus(element, status, label) {
  element.className = `status-pill ${status || "neutral"}`;
  element.textContent = label;
}

function statusLabel(status) {
  if (status === "pass") return "通过";
  if (status === "warn") return "警告";
  if (status === "fail") return "失败";
  return "未检查";
}

function jobStatus(job) {
  if (!job) return "neutral";
  if (job.status === "completed") return "pass";
  if (job.status === "failed" || job.status === "cancelled") return "fail";
  if (job.status === "running" || job.status === "queued") return "warn";
  return "neutral";
}

function isTerminal(status) {
  return ["completed", "failed", "cancelled"].includes(status);
}

function listText(values) {
  if (!Array.isArray(values) || !values.length) return "无";
  return values.join(", ");
}

function numberText(value) {
  if (value === null || value === undefined) return "0";
  return Number(value).toLocaleString("en-US");
}

async function withBusy(button, label, action) {
  const original = button.textContent;
  button.textContent = label;
  button.disabled = true;
  try {
    await action();
  } catch (error) {
    renderRequestError(error);
  } finally {
    button.textContent = original;
    button.disabled = false;
  }
}

function renderRequestError(error) {
  setStatus(elements.readinessStatus, "fail", "请求失败");
  elements.readinessSummary.className = "readiness-layout";
  elements.readinessSummary.innerHTML = messageBlock("Request error", [String(error.message || error)], "fail");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const detail = payload.detail || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
