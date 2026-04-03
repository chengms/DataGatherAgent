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
  catalogTotal: 0,
  activeWorkspaceTab: "hot",
  lastPreview: null,
  previewFilters: {
    platform: "",
    kind: "",
    keyword: "",
  },
  fetchedFilters: {
    platform: "",
    keyword: "",
  },
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
  heroPlatformCount: document.getElementById("heroPlatformCount"),
  heroPlatformMeta: document.getElementById("heroPlatformMeta"),
  heroLiveCount: document.getElementById("heroLiveCount"),
  heroLiveMeta: document.getElementById("heroLiveMeta"),
  heroCatalogCount: document.getElementById("heroCatalogCount"),
  heroCatalogMeta: document.getElementById("heroCatalogMeta"),
  heroJobCount: document.getElementById("heroJobCount"),
  heroJobMeta: document.getElementById("heroJobMeta"),
  previewForm: document.getElementById("previewForm"),
  keywordsInput: document.getElementById("keywordsInput"),
  platformGrid: document.getElementById("platformGrid"),
  platformSelectionMeta: document.getElementById("platformSelectionMeta"),
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
  workspaceMeta: document.getElementById("workspaceMeta"),
  tabHotButton: document.getElementById("tabHotButton"),
  tabFetchedButton: document.getElementById("tabFetchedButton"),
  tabLocalButton: document.getElementById("tabLocalButton"),
  hotWorkspace: document.getElementById("hotWorkspace"),
  fetchedWorkspace: document.getElementById("fetchedWorkspace"),
  localWorkspace: document.getElementById("localWorkspace"),
  latestPreviewMeta: document.getElementById("latestPreviewMeta"),
  previewSummary: document.getElementById("previewSummary"),
  hotPlatformFilter: document.getElementById("hotPlatformFilter"),
  hotKindFilter: document.getElementById("hotKindFilter"),
  hotKeywordFilter: document.getElementById("hotKeywordFilter"),
  hotArticles: document.getElementById("hotArticles"),
  fetchedAvailabilityHint: document.getElementById("fetchedAvailabilityHint"),
  discoveryMeta: document.getElementById("discoveryMeta"),
  discoveryCandidates: document.getElementById("discoveryCandidates"),
  fetchedMeta: document.getElementById("fetchedMeta"),
  fetchedPlatformFilter: document.getElementById("fetchedPlatformFilter"),
  fetchedKeywordFilter: document.getElementById("fetchedKeywordFilter"),
  fetchedArticles: document.getElementById("fetchedArticles"),
  jobsMeta: document.getElementById("jobsMeta"),
  jobsList: document.getElementById("jobsList"),
  localMeta: document.getElementById("localMeta"),
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
    .replaceAll('"', "&quot;")
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

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function summarizeText(value, limit = 140) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) {
    return "";
  }
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, limit)}...`;
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

function getSelectedPlatforms() {
  return Array.from(document.querySelectorAll('input[name="platform-option"]:checked')).map((input) => input.value);
}

function syncPlatformSelectionUi() {
  const inputs = document.querySelectorAll('input[name="platform-option"]');
  const selected = [];
  inputs.forEach((input) => {
    const card = input.closest(".platform-option");
    if (card) {
      card.classList.toggle("selected", input.checked);
    }
    if (input.checked) {
      selected.push(input.value);
    }
  });
  elements.platformSelectionMeta.textContent = selected.length
    ? `已选择 ${selected.length} 个平台：${selected.map(localizePlatform).join(" / ")}`
    : "尚未选择平台";
}

function renderPlatformSelector() {
  const previous = new Set(getSelectedPlatforms());
  const capabilityMap = buildCapabilityMap();
  elements.platformGrid.innerHTML = PLATFORM_OPTIONS.map((platform) => {
    const checked = previous.size ? previous.has(platform.key) : DEFAULT_SELECTED_PLATFORMS.has(platform.key);
    const capability = capabilityMap.get(platform.key);
    const ready = Boolean(capability?.search && capability?.fetch && platform.supported);
    const live = Boolean(capability?.live);
    return `
      <label class="platform-option${platform.supported ? "" : " disabled"}${checked ? " selected" : ""}">
        <input
          type="checkbox"
          name="platform-option"
          value="${platform.key}"
          ${checked ? "checked" : ""}
          ${platform.supported ? "" : "disabled"}
        >
        <div class="platform-option-head">
          <span class="platform-option-title">${platform.label}</span>
          <span class="platform-option-tag">${platform.supported ? "已接入" : "即将支持"}</span>
        </div>
        <span class="platform-option-desc">${platform.description}</span>
        <div class="platform-option-foot">
          <span class="mini-pill ${ready ? "" : "muted"}">${ready ? "发现+抓取" : "能力待补齐"}</span>
          <span class="mini-pill ${live ? "" : "muted"}">${live ? "在线链路" : "离线/模拟"}</span>
        </div>
      </label>
    `;
  }).join("");
  syncPlatformSelectionUi();
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
          <span class="pill ${ready ? "" : "offline"}">${ready ? "可运行" : (platform.supported ? "未就绪" : "即将支持")}</span>
          <span class="kind">${platform.label}</span>
        </div>
        <h3>${platform.label}</h3>
        <p>${platform.description}</p>
        <div class="capability-row">
          <span class="mini-pill ${capability?.search ? "" : "muted"}">发现</span>
          <span class="mini-pill ${capability?.fetch ? "" : "muted"}">抓取</span>
          <span class="mini-pill ${live ? "" : "muted"}">在线</span>
        </div>
        <p>${ready ? (live ? "在线抓取链路已具备，可直接用于实时任务。" : "当前主要依赖离线能力或模拟链路。") : "当前不会纳入运行预览，建议先补齐接入或登录。"}</p>
      </article>
    `;
  }).join("");
}

function renderHeroSummary() {
  const capabilityMap = buildCapabilityMap();
  const supportedCount = PLATFORM_OPTIONS.filter((item) => item.supported).length;
  const readyCount = PLATFORM_OPTIONS.filter((item) => {
    const capability = capabilityMap.get(item.key);
    return item.supported && capability?.search && capability?.fetch;
  }).length;
  const liveCount = PLATFORM_OPTIONS.filter((item) => item.supported && capabilityMap.get(item.key)?.live).length;

  elements.heroPlatformCount.textContent = `${readyCount}/${supportedCount}`;
  elements.heroPlatformMeta.textContent = "就绪平台 / 已接入平台";
  elements.heroLiveCount.textContent = String(liveCount);
  elements.heroLiveMeta.textContent = liveCount ? "已发现可在线抓取链路" : "当前没有在线抓取链路";
  elements.heroCatalogCount.textContent = String(state.catalogTotal);
  elements.heroCatalogMeta.textContent = state.catalogTotal ? "支持全文搜索、原文跳转和评论预览" : "本地库尚未积累数据";
  elements.heroJobCount.textContent = String(state.jobs.length);
  elements.heroJobMeta.textContent = state.jobs.length ? "可回看最近运行摘要" : "尚未产生历史任务";
}

function setActiveWorkspaceTab(tab) {
  state.activeWorkspaceTab = tab;
  const viewMap = {
    hot: elements.hotWorkspace,
    fetched: elements.fetchedWorkspace,
    local: elements.localWorkspace,
  };
  const buttonMap = {
    hot: elements.tabHotButton,
    fetched: elements.tabFetchedButton,
    local: elements.tabLocalButton,
  };
  Object.entries(viewMap).forEach(([key, node]) => {
    node.classList.toggle("hidden", key !== tab);
  });
  Object.entries(buttonMap).forEach(([key, button]) => {
    button.classList.toggle("active", key === tab);
  });

  const messages = {
    hot: "优先查看经过排序的热门结果，并支持按平台、内容类型和关键词筛选。",
    fetched: "查看本次预览返回的发现候选与抓取明细，更接近采集平台常见的数据工作台。",
    local: "从本地库检索全文、账号、链接和评论，适合二次核对与回看历史任务沉淀。",
  };
  elements.workspaceMeta.textContent = messages[tab];
}

function normalizePreviewPayload(payload, source = "preview") {
  return {
    ...payload,
    platforms: Array.isArray(payload.platforms) ? payload.platforms : [],
    keywords: Array.isArray(payload.keywords) ? payload.keywords : [],
    hot_articles: Array.isArray(payload.hot_articles) ? payload.hot_articles : [],
    fetched_articles: Array.isArray(payload.fetched_articles) ? payload.fetched_articles : [],
    discovery_candidates: Array.isArray(payload.discovery_candidates) ? payload.discovery_candidates : [],
    preview_source: source,
  };
}

function renderHotFilterOptions() {
  const selectedPlatform = state.previewFilters.platform;
  const selectedKind = state.previewFilters.kind;
  const platformOptions = [{ value: "", label: "全部平台" }];
  const kindOptions = [{ value: "", label: "全部类型" }];
  const platforms = new Set();
  const kinds = new Set();

  for (const article of state.lastPreview?.hot_articles || []) {
    if (article.platform) {
      platforms.add(article.platform);
    }
    if (article.content_kind) {
      kinds.add(article.content_kind);
    }
  }

  platforms.forEach((platform) => platformOptions.push({ value: platform, label: localizePlatform(platform) }));
  kinds.forEach((kind) => kindOptions.push({ value: kind, label: localizeContentKind(kind) }));

  elements.hotPlatformFilter.innerHTML = platformOptions
    .map((item) => `<option value="${escapeAttribute(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
  elements.hotKindFilter.innerHTML = kindOptions
    .map((item) => `<option value="${escapeAttribute(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");

  elements.hotPlatformFilter.value = platformOptions.some((item) => item.value === selectedPlatform) ? selectedPlatform : "";
  elements.hotKindFilter.value = kindOptions.some((item) => item.value === selectedKind) ? selectedKind : "";
}

function renderFetchedPlatformOptions() {
  const selected = state.fetchedFilters.platform;
  const platformOptions = [{ value: "", label: "全部平台" }];
  const platforms = new Set();

  for (const article of state.lastPreview?.fetched_articles || []) {
    if (article.platform) {
      platforms.add(article.platform);
    }
  }

  platforms.forEach((platform) => platformOptions.push({ value: platform, label: localizePlatform(platform) }));
  elements.fetchedPlatformFilter.innerHTML = platformOptions
    .map((item) => `<option value="${escapeAttribute(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
  elements.fetchedPlatformFilter.value = platformOptions.some((item) => item.value === selected) ? selected : "";
}
function renderSummaryCards(preview) {
  const metrics = [
    { label: "关键词", value: preview.keywords.length, meta: "本次任务输入" },
    { label: "发现候选", value: preview.discovered_count, meta: "可供抓取的候选内容" },
    { label: "抓取正文", value: preview.fetched_count, meta: "已保存正文与评论" },
    { label: "热门输出", value: preview.ranked_count, meta: "排序后的结果集" },
  ];
  elements.previewSummary.innerHTML = metrics.map((metric) => `
    <article class="metric-card">
      <strong>${metric.value}</strong>
      <span>${metric.label}</span>
      <small>${metric.meta}</small>
    </article>
  `).join("");
}

function renderHotWorkspace() {
  renderHotFilterOptions();
  const preview = state.lastPreview;
  if (!preview) {
    elements.latestPreviewMeta.textContent = "还没有运行记录。";
    elements.previewSummary.innerHTML = "";
    elements.hotArticles.className = "article-list empty-state";
    elements.hotArticles.textContent = "运行一次预览后，这里会显示排序结果。";
    return;
  }

  const platforms = preview.platforms.length ? preview.platforms.map(localizePlatform).join(" / ") : "未指定平台";
  elements.latestPreviewMeta.textContent = `任务 #${preview.job_id || "-"} · 平台 ${platforms} · 关键词 ${preview.keywords.length} 个`;
  renderSummaryCards(preview);

  const keywordFilter = state.previewFilters.keyword.trim().toLowerCase();
  const visible = preview.hot_articles.filter((article) => {
    if (state.previewFilters.platform && article.platform !== state.previewFilters.platform) {
      return false;
    }
    if (state.previewFilters.kind && article.content_kind !== state.previewFilters.kind) {
      return false;
    }
    if (!keywordFilter) {
      return true;
    }
    const haystack = [article.title, article.account_name, article.keyword, article.score_reason].join(" ").toLowerCase();
    return haystack.includes(keywordFilter);
  });

  if (!visible.length) {
    elements.hotArticles.className = "article-list empty-state";
    elements.hotArticles.textContent = "当前筛选条件下没有可展示的热门结果。";
    return;
  }

  elements.hotArticles.className = "article-list";
  elements.hotArticles.innerHTML = visible.map((article, index) => `
    <article class="article-card data-card">
      <div class="data-card-top">
        <div class="chip-row">
          <span class="pill">${escapeHtml(localizePlatform(article.platform || ""))}</span>
          <span class="mini-pill">${escapeHtml(localizeContentKind(article.content_kind || "article"))}</span>
          <span class="mini-pill">${escapeHtml(article.source_engine || "未知来源")}</span>
        </div>
        <span class="score-pill">Score ${Number(article.total_score || 0).toFixed(4)}</span>
      </div>
      <h3>${escapeHtml(article.title)}</h3>
      <p class="card-summary">${escapeHtml(summarizeText(article.score_reason || "暂无评分说明", 120))}</p>
      <div class="meta-grid">
        <span>账号 ${escapeHtml(article.account_name || "-")}</span>
        <span>关键词 ${escapeHtml(article.keyword || "-")}</span>
        <span>发布时间 ${escapeHtml(formatDateTime(article.publish_time))}</span>
        <span>阅读 ${Number(article.read_count || 0)} · 评论 ${Number(article.comment_count || 0)}</span>
      </div>
      <div class="card-actions">
        <a href="${escapeAttribute(article.source_url || "#")}" target="_blank" rel="noreferrer">打开原文</a>
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

function renderFetchedWorkspace() {
  renderFetchedPlatformOptions();
  const preview = state.lastPreview;
  if (!preview) {
    elements.fetchedAvailabilityHint.textContent = "运行预览后，这里会展示发现候选与抓取明细。";
    elements.discoveryMeta.textContent = "尚无候选";
    elements.fetchedMeta.textContent = "尚无抓取数据";
    elements.discoveryCandidates.className = "article-list empty-state";
    elements.discoveryCandidates.textContent = "暂无候选数据。";
    elements.fetchedArticles.className = "article-list empty-state";
    elements.fetchedArticles.textContent = "暂无抓取明细。";
    return;
  }

  const keywordFilter = state.fetchedFilters.keyword.trim().toLowerCase();
  const candidates = preview.discovery_candidates.filter((item) => {
    if (!keywordFilter) {
      return true;
    }
    const haystack = [item.title, item.account_name, item.keyword, item.snippet].join(" ").toLowerCase();
    return haystack.includes(keywordFilter);
  });

  const fetchedItems = preview.fetched_articles.filter((item) => {
    if (state.fetchedFilters.platform && item.platform !== state.fetchedFilters.platform) {
      return false;
    }
    if (!keywordFilter) {
      return true;
    }
    const haystack = [item.title, item.account_name, item.keyword, item.content_text].join(" ").toLowerCase();
    return haystack.includes(keywordFilter);
  });

  elements.fetchedAvailabilityHint.textContent = preview.preview_source === "job"
    ? "历史任务仅保留热门结果摘要。发现候选和抓取明细仅在本次预览返回时可直接查看。"
    : "显示本次预览返回的候选与抓取明细，可据此快速核对抓取质量。";
  elements.discoveryMeta.textContent = `匹配 ${candidates.length} 条候选`;
  elements.fetchedMeta.textContent = `匹配 ${fetchedItems.length} 条抓取结果`;

  if (!candidates.length) {
    elements.discoveryCandidates.className = "article-list empty-state";
    elements.discoveryCandidates.textContent = preview.preview_source === "job"
      ? "当前任务摘要不包含候选列表。"
      : "当前筛选条件下没有候选数据。";
  } else {
    elements.discoveryCandidates.className = "article-list";
    elements.discoveryCandidates.innerHTML = candidates.map((item) => `
      <article class="article-card data-card compact-card">
        <div class="chip-row">
          <span class="pill">${escapeHtml(item.keyword || "候选")}</span>
          <span class="mini-pill">${escapeHtml(item.source_engine || "发现来源")}</span>
        </div>
        <h3>${escapeHtml(item.title)}</h3>
        <p class="card-summary">${escapeHtml(summarizeText(item.snippet || "", 110))}</p>
        <div class="meta-grid">
          <span>账号 ${escapeHtml(item.account_name || "-")}</span>
          <span>发现时间 ${escapeHtml(formatDateTime(item.discovered_at))}</span>
        </div>
        <div class="card-actions">
          <a href="${escapeAttribute(item.source_url || "#")}" target="_blank" rel="noreferrer">打开候选链接</a>
        </div>
      </article>
    `).join("");
  }

  if (!fetchedItems.length) {
    elements.fetchedArticles.className = "article-list empty-state";
    elements.fetchedArticles.textContent = preview.preview_source === "job"
      ? "当前任务摘要不包含抓取明细。"
      : "当前筛选条件下没有抓取明细。";
    return;
  }

  elements.fetchedArticles.className = "article-list";
  elements.fetchedArticles.innerHTML = fetchedItems.map((article, index) => `
    <article class="article-card data-card compact-card">
      <div class="data-card-top">
        <div class="chip-row">
          <span class="pill">${escapeHtml(localizePlatform(article.platform || ""))}</span>
          <span class="mini-pill">${escapeHtml(localizeContentKind(article.content_kind || "article"))}</span>
          <span class="mini-pill">${escapeHtml(article.source_engine || "抓取来源")}</span>
        </div>
        <span class="mini-pill">评论 ${Number(article.comment_count || 0)}</span>
      </div>
      <h3>${escapeHtml(article.title)}</h3>
      <p class="card-summary">${escapeHtml(summarizeText(article.content_text || "", 140))}</p>
      <div class="meta-grid">
        <span>账号 ${escapeHtml(article.account_name || "-")}</span>
        <span>关键词 ${escapeHtml(article.keyword || "-")}</span>
        <span>发布时间 ${escapeHtml(formatDateTime(article.publish_time))}</span>
        <span>阅读 ${Number(article.read_count || 0)}</span>
      </div>
      <div class="card-actions">
        <a href="${escapeAttribute(article.source_url || "#")}" target="_blank" rel="noreferrer">打开原文</a>
        <button type="button" class="link-button" data-open-fetched-local="${index}">本地预览（含评论）</button>
      </div>
    </article>
  `).join("");

  elements.fetchedArticles.querySelectorAll("button[data-open-fetched-local]").forEach((button) => {
    button.addEventListener("click", async () => {
      const index = Number(button.getAttribute("data-open-fetched-local") || "0");
      const article = fetchedItems[index];
      if (article) {
        await openLocalPreviewBySource(article);
      }
    });
  });
}
function renderJobs() {
  elements.jobsMeta.textContent = state.jobs.length ? `已加载 ${state.jobs.length} 条任务摘要` : "还没有历史任务。";
  if (!state.jobs.length) {
    elements.jobsList.className = "job-list empty-state";
    elements.jobsList.textContent = "还没有加载任务。";
    renderHeroSummary();
    return;
  }

  elements.jobsList.className = "job-list";
  elements.jobsList.innerHTML = state.jobs.map((job) => `
    <article class="job-card">
      <div class="job-top">
        <span class="pill ${job.status === "success" ? "" : "offline"}">${escapeHtml(localizeJobStatus(job.status))}</span>
        <button type="button" data-job-id="${job.id}">加载 #${job.id}</button>
      </div>
      <h3>${escapeHtml(localizePlatform(job.platform || ""))} 工作流</h3>
      <p>${escapeHtml(job.discovery_source || "-")} → ${escapeHtml(job.fetch_source || "-")}</p>
      <div class="meta-grid">
        <span>创建 ${escapeHtml(formatDateTime(job.created_at))}</span>
        <span>完成 ${escapeHtml(formatDateTime(job.finished_at))}</span>
        <span>发现 ${job.discovered_count}</span>
        <span>抓取 ${job.fetched_count} · 排序 ${job.ranked_count}</span>
      </div>
    </article>
  `).join("");

  elements.jobsList.querySelectorAll("button[data-job-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const jobId = button.getAttribute("data-job-id");
      if (!jobId) {
        return;
      }
      const detail = await requestJson(`/api/workflows/jobs/${jobId}`);
      state.lastPreview = normalizePreviewPayload({
        job_id: detail.job.id,
        keywords: safeParseKeywords(detail.job.keywords_json),
        platforms: String(detail.job.platform || "").split(",").filter(Boolean),
        discovered_count: detail.job.discovered_count,
        fetched_count: detail.job.fetched_count,
        ranked_count: detail.job.ranked_count,
        hot_articles: detail.hot_articles || [],
      }, "job");
      state.previewFilters.platform = "";
      state.previewFilters.kind = "";
      state.previewFilters.keyword = "";
      state.fetchedFilters.platform = "";
      state.fetchedFilters.keyword = "";
      elements.hotKeywordFilter.value = "";
      elements.fetchedKeywordFilter.value = "";
      setActiveWorkspaceTab("hot");
      renderWorkspace();
    });
  });
  renderHeroSummary();
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
  elements.localMeta.textContent = state.catalogTotal
    ? `本地库累计 ${state.catalogTotal} 条内容，支持全文检索、原文跳转和评论预览。`
    : "本地库暂无数据，运行任务后可在这里检索正文与评论。";

  if (!state.articleSearch.items.length) {
    elements.localArticles.className = "article-list empty-state";
    elements.localArticles.textContent = "暂无本地搜索结果。";
    renderHeroSummary();
    return;
  }

  elements.localArticles.className = "article-list";
  elements.localArticles.innerHTML = state.articleSearch.items.map((article) => `
    <article class="article-card data-card">
      <div class="data-card-top">
        <div class="chip-row">
          <span class="pill">${escapeHtml(localizePlatform(article.platform || ""))}</span>
          <span class="mini-pill">${escapeHtml(localizeContentKind(article.content_kind || "article"))}</span>
          <span class="mini-pill">${escapeHtml(article.source_engine || "本地存档")}</span>
        </div>
        <span class="mini-pill">任务 #${article.job_id}</span>
      </div>
      <h3>${escapeHtml(article.title)}</h3>
      <p class="card-summary">${escapeHtml(summarizeText(article.content_text || "", 150))}</p>
      <div class="meta-grid">
        <span>账号 ${escapeHtml(article.account_name || "-")}</span>
        <span>关键词 ${escapeHtml(article.keyword || "-")}</span>
        <span>发布时间 ${escapeHtml(formatDateTime(article.publish_time))}</span>
        <span>阅读 ${Number(article.read_count || 0)} · 评论 ${Number(article.comment_count || 0)}</span>
      </div>
      <div class="card-actions">
        <a href="${escapeAttribute(article.source_url || "#")}" target="_blank" rel="noreferrer">打开原文</a>
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
  renderHeroSummary();
}

function renderWorkspace() {
  renderHotWorkspace();
  renderFetchedWorkspace();
  renderLocalSearch();
  setActiveWorkspaceTab(state.activeWorkspaceTab);
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
    `发布时间 ${formatDateTime(payload.publish_time)}`,
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
    setStatus("未在本地库定位到该条内容，可切换到“本地库搜索”继续检索。", "error");
    setActiveWorkspaceTab("local");
    return;
  }
  await openArticleModal(result.items[0].id);
}

function isCatalogBaselineQuery() {
  return !state.articleSearch.query
    && !state.articleSearch.platform
    && !state.articleSearch.contentKind
    && !state.articleSearch.jobId;
}
async function loadHealth() {
  try {
    const payload = await requestJson("/health");
    const ok = payload.status === "ok";
    elements.healthBadge.textContent = ok ? "接口正常" : "接口状态未知";
    elements.healthBadge.classList.toggle("offline", !ok);
  } catch {
    elements.healthBadge.textContent = "接口离线";
    elements.healthBadge.classList.add("offline");
  }
}

async function loadSources() {
  state.sources = await requestJson("/api/discovery/sources");
  renderPlatformSelector();
  renderSourceCards();
  renderLocalPlatformOptions();
  renderHeroSummary();
}

async function loadJobs() {
  const payload = await requestJson("/api/workflows/jobs");
  state.jobs = Array.isArray(payload) ? [...payload].sort((a, b) => Number(b.id) - Number(a.id)) : [];
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
  if (isCatalogBaselineQuery()) {
    state.catalogTotal = state.articleSearch.total;
  }
  renderLocalSearch();
}

async function runPreview(event) {
  event.preventDefault();
  const keywords = elements.keywordsInput.value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
  const platforms = getSelectedPlatforms();

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
    const preview = await requestJson("/api/workflows/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.lastPreview = normalizePreviewPayload(preview, "preview");
    state.previewFilters.platform = "";
    state.previewFilters.kind = "";
    state.previewFilters.keyword = "";
    state.fetchedFilters.platform = "";
    state.fetchedFilters.keyword = "";
    elements.hotKeywordFilter.value = "";
    elements.fetchedKeywordFilter.value = "";
    setActiveWorkspaceTab("hot");
    renderWorkspace();
    await Promise.allSettled([loadJobs(), loadLocalArticles()]);
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
  syncPlatformSelectionUi();
}

function onClearPlatforms() {
  document.querySelectorAll('input[name="platform-option"]:not([disabled])').forEach((input) => {
    input.checked = false;
  });
  syncPlatformSelectionUi();
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
  elements.platformGrid.addEventListener("change", syncPlatformSelectionUi);
  elements.refreshSourcesButton.addEventListener("click", loadSources);
  elements.refreshJobsButton.addEventListener("click", loadJobs);
  elements.selectAllPlatformsButton.addEventListener("click", onSelectAllPlatforms);
  elements.clearPlatformsButton.addEventListener("click", onClearPlatforms);
  elements.tabHotButton.addEventListener("click", () => setActiveWorkspaceTab("hot"));
  elements.tabFetchedButton.addEventListener("click", () => setActiveWorkspaceTab("fetched"));
  elements.tabLocalButton.addEventListener("click", () => setActiveWorkspaceTab("local"));

  elements.hotPlatformFilter.addEventListener("change", () => {
    state.previewFilters.platform = elements.hotPlatformFilter.value;
    renderHotWorkspace();
  });
  elements.hotKindFilter.addEventListener("change", () => {
    state.previewFilters.kind = elements.hotKindFilter.value;
    renderHotWorkspace();
  });
  elements.hotKeywordFilter.addEventListener("input", () => {
    state.previewFilters.keyword = elements.hotKeywordFilter.value;
    renderHotWorkspace();
  });
  elements.fetchedPlatformFilter.addEventListener("change", () => {
    state.fetchedFilters.platform = elements.fetchedPlatformFilter.value;
    renderFetchedWorkspace();
  });
  elements.fetchedKeywordFilter.addEventListener("input", () => {
    state.fetchedFilters.keyword = elements.fetchedKeywordFilter.value;
    renderFetchedWorkspace();
  });

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
  renderHeroSummary();
  renderWorkspace();
  await Promise.allSettled([loadHealth(), loadSources(), loadJobs()]);
  await loadLocalArticles();
  renderWorkspace();
}

bootstrap();
