const PLATFORM_OPTIONS = [
  { key: "wechat", label: "公众号", description: "微信公众号文章发现与抓取", supported: true },
  { key: "xiaohongshu", label: "小红书", description: "小红书笔记发现与详情抓取", supported: true },
  { key: "weibo", label: "微博", description: "微博热点与内容抓取", supported: true },
  { key: "douyin", label: "抖音", description: "抖音热点视频与内容抓取", supported: true },
  { key: "bilibili", label: "B站", description: "B站热门视频与动态抓取", supported: true },
  { key: "zhihu", label: "知乎", description: "知乎热门回答与专栏，后续接入", supported: false },
];

const CONTENT_KIND_LABELS = {
  article: "图文文章",
  note: "笔记",
  video: "视频",
  mixed: "混合",
};

const DEFAULT_SELECTED_PLATFORMS = new Set(["wechat", "xiaohongshu"]);

const state = {
  sources: [],
  jobs: [],
  lastPreview: null,
  hotPlatformFilter: "",
  articleSearch: {
    query: "",
    platform: "",
    contentKind: "",
    jobId: "",
    page: 1,
    pageSize: 8,
    total: 0,
    items: [],
  },
};

const elements = {
  healthBadge: document.getElementById("healthBadge"),
  previewForm: document.getElementById("previewForm"),
  keywordsInput: document.getElementById("keywordsInput"),
  platformGrid: document.getElementById("platformGrid"),
  selectAllPlatformsButton: document.getElementById("selectAllPlatformsButton"),
  clearPlatformsButton: document.getElementById("clearPlatformsButton"),
  limitInput: document.getElementById("limitInput"),
  topKInput: document.getElementById("topKInput"),
  fallbackInput: document.getElementById("fallbackInput"),
  runButton: document.getElementById("runButton"),
  formStatus: document.getElementById("formStatus"),
  refreshSourcesButton: document.getElementById("refreshSourcesButton"),
  refreshJobsButton: document.getElementById("refreshJobsButton"),
  sourcesGrid: document.getElementById("sourcesGrid"),
  latestPreviewMeta: document.getElementById("latestPreviewMeta"),
  previewSummary: document.getElementById("previewSummary"),
  hotPlatformFilter: document.getElementById("hotPlatformFilter"),
  hotArticles: document.getElementById("hotArticles"),
  jobsMeta: document.getElementById("jobsMeta"),
  jobsList: document.getElementById("jobsList"),
  localSearchForm: document.getElementById("localSearchForm"),
  localQueryInput: document.getElementById("localQueryInput"),
  localPlatformFilter: document.getElementById("localPlatformFilter"),
  localKindFilter: document.getElementById("localKindFilter"),
  localJobIdInput: document.getElementById("localJobIdInput"),
  localSearchButton: document.getElementById("localSearchButton"),
  localPageMeta: document.getElementById("localPageMeta"),
  localPrevButton: document.getElementById("localPrevButton"),
  localNextButton: document.getElementById("localNextButton"),
  localArticles: document.getElementById("localArticles"),
  articleModal: document.getElementById("articleModal"),
  closeModalButton: document.getElementById("closeModalButton"),
  modalTitle: document.getElementById("modalTitle"),
  modalMeta: document.getElementById("modalMeta"),
  modalSourceLinkWrap: document.getElementById("modalSourceLinkWrap"),
  modalContentText: document.getElementById("modalContentText"),
  modalComments: document.getElementById("modalComments"),
};

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

function localizePlatform(platform) {
  const mapping = {
    wechat: "公众号",
    xiaohongshu: "小红书",
    weibo: "微博",
    douyin: "抖音",
    bilibili: "B站",
    zhihu: "知乎",
  };
  return String(platform || "")
    .split(",")
    .filter(Boolean)
    .map((item) => mapping[item] || item)
    .join(" / ");
}

function localizeContentKind(kind) {
  return CONTENT_KIND_LABELS[kind] || (kind || "未知");
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

function setStatus(message, tone = "") {
  elements.formStatus.textContent = message;
  elements.formStatus.className = `status-line${tone ? ` ${tone}` : ""}`;
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `请求失败，状态码 ${response.status}`);
  }
  return response.json();
}

function safeParseKeywords(raw) {
  try {
    const payload = JSON.parse(raw);
    return Array.isArray(payload) ? payload : [];
  } catch {
    return [];
  }
}

function renderPlatformSelector() {
  const previous = new Set(
    Array.from(document.querySelectorAll('input[name="platform-option"]:checked')).map((input) => input.value),
  );
  elements.platformGrid.innerHTML = PLATFORM_OPTIONS.map((platform) => {
    const checked = previous.size ? previous.has(platform.key) : DEFAULT_SELECTED_PLATFORMS.has(platform.key);
    return `
      <label class="platform-option${platform.supported ? "" : " disabled"}">
        <input
          type="checkbox"
          name="platform-option"
          value="${platform.key}"
          ${checked ? "checked" : ""}
          ${platform.supported ? "" : "disabled"}
        >
        <span class="platform-option-title">${platform.label}</span>
        <span class="platform-option-desc">${platform.description}</span>
        <span class="platform-option-tag">${platform.supported ? "已接入" : "即将支持"}</span>
      </label>
    `;
  }).join("");
}

function buildCapabilityMap() {
  const capabilityMap = new Map();
  for (const source of state.sources) {
    if (!capabilityMap.has(source.platform)) {
      capabilityMap.set(source.platform, { search: false, fetch: false, live: false });
    }
    const current = capabilityMap.get(source.platform);
    current[source.kind] = true;
    current.live = current.live || Boolean(source.live);
  }
  return capabilityMap;
}

function renderSourceCards() {
  const capabilityMap = buildCapabilityMap();
  elements.sourcesGrid.innerHTML = PLATFORM_OPTIONS.map((platform) => {
    const capability = capabilityMap.get(platform.key);
    const ready = Boolean(capability?.search && capability?.fetch && platform.supported);
    const live = Boolean(capability?.live);
    return `
      <article class="source-card${platform.supported ? "" : " disabled"}">
        <div class="source-top">
          <span class="pill ${ready ? "" : "offline"}">${ready ? "可用" : (platform.supported ? "未就绪" : "即将支持")}</span>
          <span class="kind">${platform.label}</span>
        </div>
        <h3>${platform.label}</h3>
        <p>${platform.description}</p>
        <p>${ready ? (live ? "在线爬取链路已可用" : "当前仅模拟或离线能力") : "当前不会加入预览请求"}</p>
      </article>
    `;
  }).join("");
}

function renderHotFilterOptions() {
  const selected = state.hotPlatformFilter;
  const options = [{ value: "", label: "全部平台" }];
  const candidates = new Set();
  for (const item of state.lastPreview?.platforms || []) {
    candidates.add(item);
  }
  for (const article of state.lastPreview?.hot_articles || []) {
    if (article.platform) {
      candidates.add(article.platform);
    }
  }
  for (const platform of candidates) {
    options.push({ value: platform, label: localizePlatform(platform) });
  }
  elements.hotPlatformFilter.innerHTML = options
    .map((item) => `<option value="${escapeAttribute(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
  if (options.some((item) => item.value === selected)) {
    elements.hotPlatformFilter.value = selected;
  } else {
    state.hotPlatformFilter = "";
    elements.hotPlatformFilter.value = "";
  }
}

function renderPreview() {
  renderHotFilterOptions();
  const preview = state.lastPreview;
  if (!preview) {
    elements.latestPreviewMeta.textContent = "还没有运行记录。";
    elements.previewSummary.innerHTML = "";
    elements.hotArticles.className = "article-list empty-state";
    elements.hotArticles.textContent = "运行一次预览后，这里会显示排序结果。";
    return;
  }

  const platforms = preview.platforms?.length ? preview.platforms.map(localizePlatform).join(" / ") : "";
  elements.latestPreviewMeta.textContent = `任务 #${preview.job_id}，关键词 ${preview.keywords.length} 个${platforms ? `，平台：${platforms}` : ""}`;
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

  const visible = (preview.hot_articles || []).filter((item) => {
    if (!state.hotPlatformFilter) {
      return true;
    }
    return item.platform === state.hotPlatformFilter;
  });
  if (!visible.length) {
    elements.hotArticles.className = "article-list empty-state";
    elements.hotArticles.textContent = state.hotPlatformFilter
      ? "当前平台筛选下没有热门结果。"
      : "预览已完成，但没有可展示的排序结果。";
    return;
  }

  elements.hotArticles.className = "article-list";
  elements.hotArticles.innerHTML = visible.map((article, index) => `
    <article class="article-card">
      <div class="job-top">
        <span class="pill">${escapeHtml(article.keyword)}</span>
        <span>${Number(article.total_score || 0).toFixed(4)}</span>
      </div>
      <h3>${escapeHtml(article.title)}</h3>
      <p>${escapeHtml(localizePlatform(article.platform || ""))} · ${escapeHtml(localizeContentKind(article.content_kind || "article"))}</p>
      <p>来源 ${escapeHtml(article.source_engine || "-")} · 账号 ${escapeHtml(article.account_name || "-")}</p>
      <p>阅读 ${Number(article.read_count || 0)} · 评论 ${Number(article.comment_count || 0)}</p>
      <p>${escapeHtml(article.score_reason || "")}</p>
      <div class="card-actions">
        <a href="${escapeAttribute(article.source_url)}" target="_blank" rel="noreferrer">打开原文</a>
        <button type="button" class="link-button" data-open-hot-local="${index}">本地预览（含评论）</button>
      </div>
    </article>
  `).join("");

  elements.hotArticles.querySelectorAll("button[data-open-hot-local]").forEach((button) => {
    button.addEventListener("click", async () => {
      const index = Number(button.getAttribute("data-open-hot-local") || "0");
      const article = visible[index];
      if (article) {
        await openLocalPreviewBySource(article);
      }
    });
  });
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
  elements.jobsList.querySelectorAll("button[data-job-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const jobId = button.getAttribute("data-job-id");
      if (!jobId) {
        return;
      }
      const detail = await requestJson(`/api/workflows/jobs/${jobId}`);
      state.lastPreview = {
        job_id: detail.job.id,
        keywords: safeParseKeywords(detail.job.keywords_json),
        platforms: String(detail.job.platform || "").split(",").filter(Boolean),
        discovered_count: detail.job.discovered_count,
        fetched_count: detail.job.fetched_count,
        ranked_count: detail.job.ranked_count,
        hot_articles: detail.hot_articles || [],
      };
      state.hotPlatformFilter = "";
      renderPreview();
    });
  });
}

function renderLocalPlatformOptions() {
  const selected = elements.localPlatformFilter.value;
  const options = [
    { value: "", label: "全部平台" },
    ...PLATFORM_OPTIONS.filter((item) => item.supported).map((item) => ({ value: item.key, label: item.label })),
  ];
  elements.localPlatformFilter.innerHTML = options
    .map((item) => `<option value="${escapeAttribute(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
  elements.localPlatformFilter.value = options.some((item) => item.value === selected) ? selected : "";
}

function renderLocalSearch() {
  const total = state.articleSearch.total;
  const page = state.articleSearch.page;
  const pageSize = state.articleSearch.pageSize;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  elements.localPrevButton.disabled = page <= 1;
  elements.localNextButton.disabled = page >= totalPages || total === 0;
  elements.localPageMeta.textContent = total
    ? `第 ${page} / ${totalPages} 页，共 ${total} 条`
    : "未命中结果";

  if (!state.articleSearch.items.length) {
    elements.localArticles.className = "article-list empty-state";
    elements.localArticles.textContent = "暂无本地搜索结果。";
    return;
  }

  elements.localArticles.className = "article-list";
  elements.localArticles.innerHTML = state.articleSearch.items.map((article) => `
    <article class="article-card">
      <div class="job-top">
        <span class="pill">${escapeHtml(localizePlatform(article.platform || ""))}</span>
        <span>${escapeHtml(localizeContentKind(article.content_kind || "article"))}</span>
      </div>
      <h3>${escapeHtml(article.title)}</h3>
      <p>来源 ${escapeHtml(article.source_engine || "-")} · 账号 ${escapeHtml(article.account_name || "-")}</p>
      <p>关键词 ${escapeHtml(article.keyword || "-")} · 阅读 ${Number(article.read_count || 0)} · 评论 ${Number(article.comment_count || 0)}</p>
      <div class="card-actions">
        <a href="${escapeAttribute(article.source_url)}" target="_blank" rel="noreferrer">打开原文</a>
        <button type="button" class="link-button" data-open-article-id="${article.id}">本地预览（含评论）</button>
      </div>
    </article>
  `).join("");
  elements.localArticles.querySelectorAll("button[data-open-article-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const articleId = Number(button.getAttribute("data-open-article-id") || "0");
      if (articleId) {
        await openArticleModal(articleId);
      }
    });
  });
}

function showModal() {
  elements.articleModal.classList.remove("hidden");
  elements.articleModal.setAttribute("aria-hidden", "false");
}

function hideModal() {
  elements.articleModal.classList.add("hidden");
  elements.articleModal.setAttribute("aria-hidden", "true");
}

async function openArticleModal(articleId) {
  const payload = await requestJson(`/api/workflows/articles/${articleId}`);
  elements.modalTitle.textContent = payload.title || "本地预览";
  elements.modalMeta.textContent = [
    localizePlatform(payload.platform || ""),
    localizeContentKind(payload.content_kind || "article"),
    `来源 ${payload.source_engine || "-"}`,
    `账号 ${payload.account_name || "-"}`,
    `发布时间 ${payload.publish_time || "-"}`,
    `阅读 ${Number(payload.read_count || 0)}`,
    `评论 ${Number(payload.comment_count || 0)}`,
  ].join(" · ");
  elements.modalSourceLinkWrap.innerHTML = `<a href="${escapeAttribute(payload.source_url || "#")}" target="_blank" rel="noreferrer">打开原文链接</a>`;
  elements.modalContentText.textContent = payload.content_text || "";

  const comments = Array.isArray(payload.comments) ? payload.comments : [];
  if (!comments.length) {
    elements.modalComments.className = "comment-list empty-state";
    elements.modalComments.textContent = "暂无评论。";
  } else {
    elements.modalComments.className = "comment-list";
    elements.modalComments.innerHTML = comments.map((comment) => `
      <article class="comment-card">
        <p class="comment-head">
          <strong>${escapeHtml(comment.nickname || "匿名用户")}</strong>
          <span>${escapeHtml(comment.publish_time || "-")}</span>
          <span>赞 ${Number(comment.like_count || 0)} · 回复 ${Number(comment.sub_comment_count || 0)}</span>
        </p>
        <p>${escapeHtml(comment.content || "")}</p>
      </article>
    `).join("");
  }
  showModal();
}

async function openLocalPreviewBySource(article) {
  const params = new URLSearchParams();
  params.set("q", article.source_url || "");
  params.set("platform", article.platform || "");
  if (state.lastPreview?.job_id) {
    params.set("job_id", String(state.lastPreview.job_id));
  }
  params.set("page", "1");
  params.set("page_size", "1");
  let result = await requestJson(`/api/workflows/articles?${params.toString()}`);
  if (!result.items.length) {
    params.delete("job_id");
    result = await requestJson(`/api/workflows/articles?${params.toString()}`);
  }
  if (!result.items.length) {
    setStatus("未在本地库定位到该条内容，可先用“本地数据搜索”检索。", "error");
    return;
  }
  await openArticleModal(result.items[0].id);
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
  state.sources = await requestJson("/api/discovery/sources");
  renderPlatformSelector();
  renderSourceCards();
  renderLocalPlatformOptions();
}

async function loadJobs() {
  state.jobs = await requestJson("/api/workflows/jobs");
  renderJobs();
}

async function loadLocalArticles() {
  const params = new URLSearchParams();
  params.set("page", String(state.articleSearch.page));
  params.set("page_size", String(state.articleSearch.pageSize));
  if (state.articleSearch.query) {
    params.set("q", state.articleSearch.query);
  }
  if (state.articleSearch.platform) {
    params.set("platform", state.articleSearch.platform);
  }
  if (state.articleSearch.contentKind) {
    params.set("content_kind", state.articleSearch.contentKind);
  }
  if (state.articleSearch.jobId) {
    params.set("job_id", state.articleSearch.jobId);
  }
  const payload = await requestJson(`/api/workflows/articles?${params.toString()}`);
  state.articleSearch.total = Number(payload.total || 0);
  state.articleSearch.items = Array.isArray(payload.items) ? payload.items : [];
  renderLocalSearch();
}

async function runPreview(event) {
  event.preventDefault();
  const keywords = elements.keywordsInput.value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
  const platforms = Array.from(document.querySelectorAll('input[name="platform-option"]:checked'))
    .map((input) => input.value);
  if (!keywords.length) {
    setStatus("请至少输入一个关键词。", "error");
    return;
  }
  if (!platforms.length) {
    setStatus("请至少选择一个平台。", "error");
    return;
  }
  elements.runButton.disabled = true;
  setStatus("正在运行工作流预览...");
  try {
    const payload = {
      keywords,
      platforms,
      limit: Number(elements.limitInput.value),
      top_k: Number(elements.topKInput.value),
      fallback_to_mock: elements.fallbackInput.checked,
    };
    state.lastPreview = await requestJson("/api/workflows/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.hotPlatformFilter = "";
    renderPreview();
    await loadJobs();
    setStatus(`预览完成，任务 #${state.lastPreview.job_id}。`, "success");
  } catch (error) {
    setStatus(error.message || "预览失败", "error");
  } finally {
    elements.runButton.disabled = false;
  }
}

function onSelectAllPlatforms() {
  document.querySelectorAll('input[name="platform-option"]:not([disabled])').forEach((input) => {
    input.checked = true;
  });
}

function onClearPlatforms() {
  document.querySelectorAll('input[name="platform-option"]:not([disabled])').forEach((input) => {
    input.checked = false;
  });
}

async function onSubmitLocalSearch(event) {
  event.preventDefault();
  state.articleSearch.query = elements.localQueryInput.value.trim();
  state.articleSearch.platform = elements.localPlatformFilter.value;
  state.articleSearch.contentKind = elements.localKindFilter.value;
  state.articleSearch.jobId = String(elements.localJobIdInput.value || "").trim();
  state.articleSearch.page = 1;
  elements.localSearchButton.disabled = true;
  try {
    await loadLocalArticles();
  } finally {
    elements.localSearchButton.disabled = false;
  }
}

async function onPrevLocalPage() {
  if (state.articleSearch.page <= 1) {
    return;
  }
  state.articleSearch.page -= 1;
  await loadLocalArticles();
}

async function onNextLocalPage() {
  const totalPages = Math.max(1, Math.ceil(state.articleSearch.total / state.articleSearch.pageSize));
  if (state.articleSearch.page >= totalPages) {
    return;
  }
  state.articleSearch.page += 1;
  await loadLocalArticles();
}

function bindEvents() {
  elements.previewForm.addEventListener("submit", runPreview);
  elements.refreshSourcesButton.addEventListener("click", loadSources);
  elements.refreshJobsButton.addEventListener("click", loadJobs);
  elements.hotPlatformFilter.addEventListener("change", () => {
    state.hotPlatformFilter = elements.hotPlatformFilter.value;
    renderPreview();
  });
  elements.selectAllPlatformsButton.addEventListener("click", onSelectAllPlatforms);
  elements.clearPlatformsButton.addEventListener("click", onClearPlatforms);
  elements.localSearchForm.addEventListener("submit", onSubmitLocalSearch);
  elements.localPrevButton.addEventListener("click", onPrevLocalPage);
  elements.localNextButton.addEventListener("click", onNextLocalPage);
  elements.closeModalButton.addEventListener("click", hideModal);
  elements.articleModal.querySelectorAll("[data-close-modal]").forEach((node) => {
    node.addEventListener("click", hideModal);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideModal();
    }
  });
}

async function bootstrap() {
  bindEvents();
  renderPlatformSelector();
  renderLocalPlatformOptions();
  await Promise.allSettled([loadHealth(), loadSources(), loadJobs()]);
  renderPreview();
  await loadLocalArticles();
}

bootstrap();
