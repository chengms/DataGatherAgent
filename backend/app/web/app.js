const state = {
  sources: [],
  jobs: [],
  lastPreview: null,
};

const elements = {
  healthBadge: document.getElementById("healthBadge"),
  form: document.getElementById("previewForm"),
  keywordsInput: document.getElementById("keywordsInput"),
  discoverySource: document.getElementById("discoverySource"),
  fetchSource: document.getElementById("fetchSource"),
  limitInput: document.getElementById("limitInput"),
  topKInput: document.getElementById("topKInput"),
  fallbackInput: document.getElementById("fallbackInput"),
  runButton: document.getElementById("runButton"),
  formStatus: document.getElementById("formStatus"),
  refreshSourcesButton: document.getElementById("refreshSourcesButton"),
  refreshJobsButton: document.getElementById("refreshJobsButton"),
  sourcesGrid: document.getElementById("sourcesGrid"),
  previewSummary: document.getElementById("previewSummary"),
  latestPreviewMeta: document.getElementById("latestPreviewMeta"),
  hotArticles: document.getElementById("hotArticles"),
  jobsList: document.getElementById("jobsList"),
  jobsMeta: document.getElementById("jobsMeta"),
  sourceCardTemplate: document.getElementById("sourceCardTemplate"),
};

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `请求失败，状态码 ${response.status}`);
  }
  return response.json();
}

function renderSources() {
  elements.sourcesGrid.innerHTML = "";
  const discovery = state.sources.filter((item) => item.kind === "search");
  const fetchers = state.sources.filter((item) => item.kind === "fetch");
  const ordered = [...discovery, ...fetchers];

  for (const source of ordered) {
    const fragment = elements.sourceCardTemplate.content.cloneNode(true);
    const pill = fragment.querySelector(".pill");
    const kind = fragment.querySelector(".kind");
    const title = fragment.querySelector("h3");
    const description = fragment.querySelector("p");

    pill.textContent = source.live ? "在线" : "模拟";
    pill.classList.toggle("offline", !source.live);
    kind.textContent = source.kind === "search" ? "发现" : "抓取";
    title.textContent = source.name;
    description.textContent = source.description;
    elements.sourcesGrid.appendChild(fragment);
  }

  syncSourceSelectors();
}

function syncSourceSelectors() {
  const discoverySources = state.sources.filter((item) => item.kind === "search");
  const fetchSources = state.sources.filter((item) => item.kind === "fetch");
  fillSelect(elements.discoverySource, discoverySources, "mock_wechat_search");
  fillSelect(elements.fetchSource, fetchSources, "mock_wechat_fetch");
}

function fillSelect(select, options, preferredValue) {
  const previous = select.value;
  select.innerHTML = "";
  for (const item of options) {
    const option = document.createElement("option");
    option.value = item.name;
    option.textContent = `${item.name}（${item.live ? "在线" : "模拟"}）`;
    select.appendChild(option);
  }
  const nextValue = options.some((item) => item.name === previous)
    ? previous
    : preferredValue;
  if (nextValue) {
    select.value = nextValue;
  }
}

function renderPreview() {
  const preview = state.lastPreview;
  if (!preview) {
    elements.previewSummary.innerHTML = "";
    elements.latestPreviewMeta.textContent = "还没有运行记录。";
    elements.hotArticles.className = "article-list empty-state";
    elements.hotArticles.textContent = "运行一次预览后，这里会显示排序结果。";
    return;
  }

  elements.latestPreviewMeta.textContent = `任务 #${preview.job_id}，共 ${preview.keywords.length} 个关键词`;
  const metrics = [
    ["已发现", preview.discovered_count],
    ["已抓取", preview.fetched_count],
    ["已排序", preview.ranked_count],
  ];

  elements.previewSummary.innerHTML = metrics.map(([label, value]) => `
    <article class="metric-card">
      <strong>${value}</strong>
      <span>${label}</span>
    </article>
  `).join("");

  if (!preview.hot_articles.length) {
    elements.hotArticles.className = "article-list empty-state";
    elements.hotArticles.textContent = "预览已完成，但没有可展示的排序结果。";
    return;
  }

  elements.hotArticles.className = "article-list";
  elements.hotArticles.innerHTML = preview.hot_articles.map((article) => `
    <article class="article-card">
      <div class="job-top">
        <span class="pill">${escapeHtml(article.keyword)}</span>
        <span>${Number(article.total_score).toFixed(4)}</span>
      </div>
      <h3>${escapeHtml(article.title)}</h3>
      <p>${escapeHtml(article.account_name)} · 阅读 ${article.read_count} · 评论 ${article.comment_count}</p>
      <p>${escapeHtml(article.score_reason)}</p>
      <p><a href="${escapeAttribute(article.source_url)}" target="_blank" rel="noreferrer">打开原文</a></p>
    </article>
  `).join("");
}

function renderJobs() {
  elements.jobsMeta.textContent = `已加载 ${state.jobs.length} 条任务`;
  if (!state.jobs.length) {
    elements.jobsList.className = "job-list empty-state";
    elements.jobsList.textContent = "还没有加载任务。";
    return;
  }

  elements.jobsList.className = "job-list";
  elements.jobsList.innerHTML = state.jobs.map((job) => `
    <article class="job-card">
      <div class="job-top">
        <span class="pill ${job.status === "success" ? "" : "offline"}">${escapeHtml(localizeJobStatus(job.status))}</span>
        <button type="button" data-job-id="${job.id}">打开 #${job.id}</button>
      </div>
      <h3>${escapeHtml(localizePlatform(job.platform))} 工作流</h3>
      <p>${escapeHtml(job.discovery_source)} → ${escapeHtml(job.fetch_source)}</p>
      <p>发现 ${job.discovered_count}，抓取 ${job.fetched_count}，排序 ${job.ranked_count}</p>
    </article>
  `).join("");

  for (const button of elements.jobsList.querySelectorAll("button[data-job-id]")) {
    button.addEventListener("click", async () => {
      const jobId = button.getAttribute("data-job-id");
      const detail = await requestJson(`/api/workflows/jobs/${jobId}`);
      state.lastPreview = {
        job_id: detail.job.id,
        keywords: safeParseKeywords(detail.job.keywords_json),
        discovered_count: detail.job.discovered_count,
        fetched_count: detail.job.fetched_count,
        ranked_count: detail.job.ranked_count,
        hot_articles: detail.hot_articles,
      };
      renderPreview();
    });
  }
}

function safeParseKeywords(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function setStatus(message, tone = "") {
  elements.formStatus.textContent = message;
  elements.formStatus.className = `status-line${tone ? ` ${tone}` : ""}`;
}

function localizePlatform(platform) {
  const mapping = {
    wechat: "公众号",
    xiaohongshu: "小红书",
  };
  return mapping[platform] || platform;
}

function localizeJobStatus(status) {
  const mapping = {
    success: "成功",
    failed: "失败",
    running: "运行中",
    pending: "等待中",
  };
  return mapping[status] || status;
}

async function loadHealth() {
  try {
    const payload = await requestJson("/health");
    elements.healthBadge.textContent = payload.status === "ok" ? "接口正常" : "接口状态未知";
  } catch {
    elements.healthBadge.textContent = "接口离线";
  }
}

async function loadSources() {
  const sources = await requestJson("/api/discovery/sources");
  state.sources = sources;
  renderSources();
}

async function loadJobs() {
  const jobs = await requestJson("/api/workflows/jobs");
  state.jobs = jobs;
  renderJobs();
}

async function runPreview(event) {
  event.preventDefault();
  const keywords = elements.keywordsInput.value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);

  if (!keywords.length) {
    setStatus("请至少输入一个关键词。", "error");
    return;
  }

  elements.runButton.disabled = true;
  setStatus("正在运行工作流预览...", "");

  try {
    const payload = {
      keywords,
      discovery_source: elements.discoverySource.value,
      fetch_source: elements.fetchSource.value,
      limit: Number(elements.limitInput.value),
      top_k: Number(elements.topKInput.value),
      fallback_to_mock: elements.fallbackInput.checked,
    };
    state.lastPreview = await requestJson("/api/workflows/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderPreview();
    await loadJobs();
    setStatus(`预览完成，任务编号 #${state.lastPreview.job_id}。`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    elements.runButton.disabled = false;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}

async function bootstrap() {
  elements.form.addEventListener("submit", runPreview);
  elements.refreshSourcesButton.addEventListener("click", loadSources);
  elements.refreshJobsButton.addEventListener("click", loadJobs);

  await Promise.allSettled([loadHealth(), loadSources(), loadJobs()]);
  renderPreview();
}

bootstrap();
