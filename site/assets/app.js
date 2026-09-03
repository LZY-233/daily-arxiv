const topicLabels = {
  llm: "LLM", multimodal: "MLLM / VLM", moe: "MoE", agent: "Agent",
  training: "预训练 / 后训练", architecture: "模型架构", reasoning: "推理",
  efficiency: "效率", evaluation: "评测", safety: "安全"
};
const tierLabels = { must_read: "必读", browse: "浏览", watch: "观察" };
const state = { papers: [], tier: "featured", query: "", topic: "all", sort: "score" };
const userState = JSON.parse(localStorage.getItem("daily-arxiv-state") || "{}");

const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const saveUserState = () => localStorage.setItem("daily-arxiv-state", JSON.stringify(userState));
const getPaperState = id => userState[id] || { saved: false, read: false, ignored: false };

function setPaperState(id, key) {
  const current = getPaperState(id);
  userState[id] = { ...current, [key]: !current[key] };
  saveUserState();
  render();
}

function visiblePapers() {
  const query = state.query.toLowerCase();
  const filtered = state.papers.filter(paper => {
    const local = getPaperState(paper.arxiv_id);
    const tierMatch = state.tier === "featured"
      ? paper.tier === "must_read" || paper.tier === "browse"
      : state.tier === "saved"
        ? local.saved
        : state.tier === "ignored"
          ? local.ignored
          : paper.tier === state.tier;
    const topicMatch = state.topic === "all" || (paper.topics || []).includes(state.topic);
    const haystack = `${paper.title} ${(paper.authors || []).join(" ")} ${paper.abstract_en} ${paper.abstract_zh || ""} ${paper.tldr_zh || ""}`.toLowerCase();
    return tierMatch && topicMatch && (!query || haystack.includes(query)) && (state.tier === "ignored" || !local.ignored);
  });
  const tierOrder = { must_read: 0, browse: 1, watch: 2 };
  return filtered.sort((a, b) => state.sort === "newest"
    ? new Date(b.updated_at) - new Date(a.updated_at)
    : (tierOrder[a.tier] - tierOrder[b.tier]) || (b.overall_score - a.overall_score));
}

function makeCard(paper, index) {
  const card = document.querySelector("#paper-template").content.firstElementChild.cloneNode(true);
  const local = getPaperState(paper.arxiv_id);
  card.dataset.tier = paper.tier;
  card.classList.toggle("is-read", local.read);
  card.querySelector(".rank-number").textContent = String(index + 1).padStart(2, "0");
  card.querySelector(".tier-label").textContent = tierLabels[paper.tier] || "观察";
  card.querySelector(".primary-category").textContent = paper.primary_category;
  card.querySelector(".updated-at").textContent = new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(paper.updated_at));
  const title = card.querySelector(".paper-title"); title.textContent = paper.title; title.href = paper.url;
  card.querySelector(".authors").textContent = paper.authors.join(" · ");
  card.querySelector(".topics").innerHTML = (paper.topics || []).map(topic => `<span class="topic">${escapeHtml(topicLabels[topic] || topic)}</span>`).join("");
  const hasChinese = Boolean(paper.abstract_zh);
  const abstract = card.querySelector(".abstract");
  const abstractText = paper.abstract_zh || paper.abstract_en;
  abstract.textContent = abstractText;
  card.querySelector(".abstract-label").textContent = hasChinese ? "中文摘要" : "英文摘要";
  const toggle = card.querySelector(".abstract-toggle");
  toggle.hidden = abstractText.length < 160;
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    toggle.textContent = expanded ? "展开摘要" : "收起摘要";
    abstract.classList.toggle("is-collapsed", expanded);
  });
  const tldrBlock = card.querySelector(".tldr-block");
  if (paper.tldr_zh) {
    tldrBlock.hidden = false;
    card.querySelector(".tldr").textContent = paper.tldr_zh;
  }
  const original = card.querySelector(".original-abstract");
  if (hasChinese) {
    original.hidden = false;
    card.querySelector(".abstract-original").textContent = paper.abstract_en;
  }
  card.querySelector(".abs-link").href = paper.url;
  card.querySelector(".pdf-link").href = paper.pdf_url;
  [["save", "saved"], ["read", "read"], ["ignore", "ignored"]].forEach(([name, key]) => {
    const button = card.querySelector(`.${name}-button`);
    button.classList.toggle("active", local[key]);
    if (name === "save") button.textContent = local.saved ? "★" : "☆";
    button.addEventListener("click", () => setPaperState(paper.arxiv_id, key));
  });
  return card;
}

function render() {
  const papers = visiblePapers();
  const list = document.querySelector("#paper-list");
  list.replaceChildren(...papers.map(makeCard));
  document.querySelector("#result-count").textContent = `${papers.length} 篇论文`;
  document.querySelector("#empty-state").hidden = papers.length > 0;
  document.querySelector("#section-title").textContent = state.tier === "saved"
    ? "我的收藏"
    : state.tier === "ignored"
      ? "已忽略"
      : state.tier === "featured"
        ? "今日精选"
        : tierLabels[state.tier];
}

async function start() {
  try {
    const response = await fetch("data/latest.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.papers = data.papers || [];
    const generated = new Date(data.generated_at);
    document.querySelector("#edition-date").textContent = new Intl.DateTimeFormat("zh-CN", { dateStyle: "long" }).format(generated).toUpperCase();
    document.querySelector("#issue-number").textContent = `${generated.getFullYear()}-${String(generated.getMonth() + 1).padStart(2, "0")}-${String(generated.getDate()).padStart(2, "0")}`;
    document.querySelector("#must-count").textContent = state.papers.filter(p => p.tier === "must_read").length;
    document.querySelector("#browse-count").textContent = state.papers.filter(p => p.tier === "browse").length;
    document.querySelector("#source-count").textContent = data.stats?.within_window ?? state.papers.length;
    const topics = [...new Set(state.papers.flatMap(p => p.topics || []))];
    const topicSelect = document.querySelector("#topic-filter");
    topics.forEach(topic => topicSelect.add(new Option(topicLabels[topic] || topic, topic)));
    render();
  } catch (error) {
    document.querySelector("#paper-list").innerHTML = `<p class="empty">无法读取本地数据：${escapeHtml(error.message)}。请通过本地 HTTP 服务器访问网站。</p>`;
  }
}

document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(tab => tab.classList.remove("active"));
  button.classList.add("active"); state.tier = button.dataset.tier; render();
}));
document.querySelector("#search").addEventListener("input", event => { state.query = event.target.value.trim(); render(); });
document.querySelector("#topic-filter").addEventListener("change", event => { state.topic = event.target.value; render(); });
document.querySelector("#sort-order").addEventListener("change", event => { state.sort = event.target.value; render(); });
document.querySelector("#reset-filters").addEventListener("click", () => {
  state.tier = "featured"; state.query = ""; state.topic = "all";
  document.querySelector("#search").value = ""; document.querySelector("#topic-filter").value = "all";
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.tier === "featured")); render();
});
start();
