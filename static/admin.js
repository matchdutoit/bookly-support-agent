const PALETTE = ["#1f6bff", "#23b4f6", "#6276ff", "#56c99d", "#f7b548", "#df4c5f"];

const state = {
    toolsLoaded: false,
    topics: [],
};

const pages = {
    home: document.getElementById("page-home"),
    convos: document.getElementById("page-convos"),
    build: document.getElementById("page-build"),
};

const tabPanels = {
    aop: document.getElementById("tab-aop"),
    tools: document.getElementById("tab-tools"),
};

const drawerOverlay = document.getElementById("drawer-overlay");
const conversationDrawer = document.getElementById("conversation-drawer");
const addToolDrawer = document.getElementById("add-tool-drawer");

const convoList = document.getElementById("convo-list");
const filterTopic = document.getElementById("filter-topic");
const filterMinMessages = document.getElementById("filter-min-messages");
const filterMaxMessages = document.getElementById("filter-max-messages");

const aopEditor = document.getElementById("aop-editor");
const aopStatus = document.getElementById("aop-status");
const toolsList = document.getElementById("tools-list");

const newToolStatus = document.getElementById("new-tool-status");

function escapeHtml(value) {
    return (value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

async function fetchJSON(url, options = {}) {
    const response = await fetch(url, options);
    let data = {};

    try {
        data = await response.json();
    } catch (error) {
        throw new Error("Unexpected server response");
    }

    if (!response.ok || data.success === false) {
        throw new Error(data.error || "Request failed");
    }

    return data;
}

function formatPercent(value) {
    return `${Number(value || 0).toFixed(1)}%`;
}

function formatDate(isoString) {
    if (!isoString) {
        return "-";
    }

    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) {
        return isoString;
    }

    return date.toLocaleString();
}

function renderDonut({ donutId, legendId, data, labelKey }) {
    const donut = document.getElementById(donutId);
    const legend = document.getElementById(legendId);

    if (!donut || !legend) {
        return;
    }

    const safeData = Array.isArray(data) ? data : [];
    const total = safeData.reduce((sum, item) => sum + Number(item.count || 0), 0);

    if (!safeData.length || total === 0) {
        donut.style.setProperty("--chart", "#e6ecf7");
        legend.innerHTML = '<div class="empty-state">No conversation data yet.</div>';
        return;
    }

    let progress = 0;
    const segments = [];
    const legendRows = [];

    safeData.forEach((item, index) => {
        const count = Number(item.count || 0);
        const pct = (count / total) * 100;
        const color = PALETTE[index % PALETTE.length];
        const start = progress;
        const end = progress + pct;

        segments.push(`${color} ${start}% ${end}%`);

        legendRows.push(`
            <div class="legend-item">
                <span class="legend-left">
                    <span class="legend-swatch" style="background:${color}"></span>
                    ${escapeHtml(item[labelKey] || "Unknown")}
                </span>
                <strong>${count}</strong>
            </div>
        `);

        progress = end;
    });

    donut.style.setProperty("--chart", `conic-gradient(${segments.join(",")})`);
    legend.innerHTML = legendRows.join("");
}

function renderBars(containerId, data, labelKey) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }

    const safeData = Array.isArray(data) ? data : [];
    const total = safeData.reduce((sum, item) => sum + Number(item.count || 0), 0);

    if (!safeData.length || total === 0) {
        container.innerHTML = '<div class="empty-state">No disposition data yet.</div>';
        return;
    }

    container.innerHTML = safeData
        .map((item) => {
            const count = Number(item.count || 0);
            const width = total ? (count / total) * 100 : 0;
            return `
                <div class="bar-row">
                    <div class="bar-head">
                        <span>${escapeHtml(item[labelKey] || "Unknown")}</span>
                        <strong>${count}</strong>
                    </div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width:${width}%"></div>
                    </div>
                </div>
            `;
        })
        .join("");
}

function setMetricValues(metrics) {
    document.getElementById("metric-deflection").textContent = formatPercent(metrics.deflection_rate);
    document.getElementById("metric-avg-user-messages").textContent = Number(metrics.avg_user_messages || 0).toFixed(1);
    document.getElementById("metric-top-topic").textContent = metrics.most_common_topic_label || "-";
}

function populateTopicFilter(topicBreakdown) {
    const labelsFromData = (topicBreakdown || []).map((item) => ({
        value: item.topic,
        label: item.topic_label,
    }));

    const fallback = [
        { value: "order_status", label: "Order Status" },
        { value: "returns_refunds", label: "Returns & Refunds" },
        { value: "order_changes", label: "Order Changes" },
        { value: "general_inquiry", label: "General Inquiry" },
    ];

    const merged = [...labelsFromData];
    fallback.forEach((option) => {
        if (!merged.find((item) => item.value === option.value)) {
            merged.push(option);
        }
    });

    state.topics = merged;

    filterTopic.innerHTML = [
        '<option value="all">All Topics</option>',
        ...merged.map((item) => `<option value="${item.value}">${escapeHtml(item.label)}</option>`),
    ].join("");
}

async function loadMetricsAndCharts() {
    const data = await fetchJSON("/api/admin/metrics?days=30");
    const metrics = data.metrics;

    setMetricValues(metrics);
    renderDonut({
        donutId: "home-topic-donut",
        legendId: "home-topic-legend",
        data: metrics.topic_breakdown,
        labelKey: "topic_label",
    });
    renderBars("home-disposition-bars", metrics.disposition_breakdown, "disposition_label");

    renderDonut({
        donutId: "convos-topic-donut",
        legendId: "convos-topic-legend",
        data: metrics.topic_breakdown,
        labelKey: "topic_label",
    });

    populateTopicFilter(metrics.topic_breakdown);
}

function getConvoFilters() {
    const params = new URLSearchParams({ days: "30" });

    if (filterTopic.value && filterTopic.value !== "all") {
        params.append("topic", filterTopic.value);
    }

    if (filterMinMessages.value !== "") {
        params.append("min_user_messages", filterMinMessages.value);
    }

    if (filterMaxMessages.value !== "") {
        params.append("max_user_messages", filterMaxMessages.value);
    }

    return params.toString();
}

function renderConversationList(conversations) {
    if (!Array.isArray(conversations) || conversations.length === 0) {
        convoList.innerHTML = '<div class="empty-state">No conversations match these filters.</div>';
        return;
    }

    convoList.innerHTML = conversations
        .map((conversation) => {
            const preview = conversation.last_user_message || "(No user message captured)";
            return `
                <article class="convo-item" data-conversation-id="${conversation.id}">
                    <div class="convo-item-top">
                        <span class="badge topic">${escapeHtml(conversation.topic_label)}</span>
                        <span class="badge disposition ${escapeHtml(conversation.disposition)}">${escapeHtml(conversation.disposition_label)}</span>
                    </div>
                    <p class="convo-preview">${escapeHtml(preview)}</p>
                    <div class="convo-meta">
                        ${conversation.user_message_count} user messages · Updated ${formatDate(conversation.updated_at)}
                    </div>
                </article>
            `;
        })
        .join("");
}

async function loadConversations() {
    const query = getConvoFilters();
    const data = await fetchJSON(`/api/admin/conversations?${query}`);
    renderConversationList(data.conversations);
}

function openDrawer(drawerElement) {
    closeDrawers();
    drawerOverlay.classList.add("active");
    drawerElement.classList.add("active");
    drawerElement.setAttribute("aria-hidden", "false");
}

function closeDrawers() {
    drawerOverlay.classList.remove("active");
    [conversationDrawer, addToolDrawer].forEach((drawer) => {
        drawer.classList.remove("active");
        drawer.setAttribute("aria-hidden", "true");
    });
}

function renderConversationDetail(conversation) {
    const drawerTitle = document.getElementById("drawer-title");
    const drawerMeta = document.getElementById("drawer-meta");
    const drawerMessages = document.getElementById("drawer-messages");

    drawerTitle.textContent = `Conversation #${conversation.id}`;
    drawerMeta.textContent = `${conversation.topic_label} · ${conversation.disposition_label} · ${conversation.user_message_count} user messages`;

    if (!Array.isArray(conversation.messages) || conversation.messages.length === 0) {
        drawerMessages.innerHTML = '<div class="empty-state">No messages found for this conversation.</div>';
        return;
    }

    drawerMessages.innerHTML = conversation.messages
        .map((message) => {
            const content = message.role === "tool"
                ? `<pre>${escapeHtml(message.content)}</pre>`
                : `<p>${escapeHtml(message.content)}</p>`;
            return `
                <article class="audit-message ${escapeHtml(message.role)}">
                    <div class="audit-message-head">
                        <span>${escapeHtml(message.role)}</span>
                        <span>${formatDate(message.created_at)}</span>
                    </div>
                    ${content}
                </article>
            `;
        })
        .join("");
}

async function openConversation(conversationId) {
    const data = await fetchJSON(`/api/admin/conversations/${conversationId}`);
    renderConversationDetail(data.conversation);
    openDrawer(conversationDrawer);
}

async function loadAop() {
    const data = await fetchJSON("/api/admin/build/aop");
    aopEditor.value = data.content || "";
}

function setTransientStatus(element, message, isError = false) {
    element.textContent = message;
    element.style.color = isError ? "#c4384f" : "#1f6bff";
    window.setTimeout(() => {
        if (element.textContent === message) {
            element.textContent = "";
        }
    }, 2500);
}

async function saveAop() {
    try {
        await fetchJSON("/api/admin/build/aop", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content: aopEditor.value }),
        });
        setTransientStatus(aopStatus, "Saved");
    } catch (error) {
        setTransientStatus(aopStatus, error.message, true);
    }
}

function renderTools(tools) {
    if (!Array.isArray(tools) || tools.length === 0) {
        toolsList.innerHTML = '<div class="empty-state">No tools found in tools.py.</div>';
        return;
    }

    toolsList.innerHTML = tools
        .map((tool) => {
            return `
                <article class="tool-card" data-tool-name="${escapeHtml(tool.name)}">
                    <div class="tool-header">
                        <h4>${escapeHtml(tool.name)}</h4>
                        <div>
                            <button class="btn btn-primary save-tool-btn">Save Tool</button>
                            <span class="status-text"></span>
                        </div>
                    </div>
                    <p class="tool-description">${escapeHtml(tool.description || "No description")}</p>
                    <textarea class="editor tool-editor" spellcheck="false">${escapeHtml(tool.code || "")}</textarea>
                </article>
            `;
        })
        .join("");
}

async function loadTools() {
    const data = await fetchJSON("/api/admin/tools");
    renderTools(data.tools);
    state.toolsLoaded = true;
}

async function saveTool(toolCard) {
    const toolName = toolCard.dataset.toolName;
    const editor = toolCard.querySelector(".tool-editor");
    const status = toolCard.querySelector(".status-text");

    try {
        await fetchJSON(`/api/admin/tools/${encodeURIComponent(toolName)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code: editor.value }),
        });
        setTransientStatus(status, "Saved");
    } catch (error) {
        setTransientStatus(status, error.message, true);
    }
}

function clearNewToolForm() {
    document.getElementById("new-tool-name").value = "";
    document.getElementById("new-tool-description").value = "";
    document.getElementById("new-tool-parameters").value = '{\n  "type": "object",\n  "properties": {},\n  "required": []\n}';
    document.getElementById("new-tool-code").value = "";
}

async function createNewTool() {
    const name = document.getElementById("new-tool-name").value.trim();
    const description = document.getElementById("new-tool-description").value.trim();
    const code = document.getElementById("new-tool-code").value;
    const rawParameters = document.getElementById("new-tool-parameters").value;

    let parameters = {};
    try {
        parameters = JSON.parse(rawParameters || "{}");
    } catch (error) {
        setTransientStatus(newToolStatus, "Parameters must be valid JSON", true);
        return;
    }

    try {
        await fetchJSON("/api/admin/tools", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name,
                description,
                parameters,
                code,
            }),
        });

        setTransientStatus(newToolStatus, "Tool created");
        closeDrawers();
        clearNewToolForm();
        await loadTools();
    } catch (error) {
        setTransientStatus(newToolStatus, error.message, true);
    }
}

function activatePage(pageName) {
    document.querySelectorAll(".nav-item").forEach((item) => {
        item.classList.toggle("active", item.dataset.page === pageName);
    });

    Object.entries(pages).forEach(([name, element]) => {
        element.classList.toggle("active", name === pageName);
    });
}

function activateTab(tabName) {
    document.querySelectorAll(".tab-item").forEach((item) => {
        item.classList.toggle("active", item.dataset.tab === tabName);
    });

    Object.entries(tabPanels).forEach(([name, panel]) => {
        panel.classList.toggle("active", name === tabName);
    });

    if (tabName === "tools" && !state.toolsLoaded) {
        loadTools().catch((error) => {
            toolsList.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        });
    }
}

function bindEvents() {
    document.querySelectorAll(".nav-item").forEach((item) => {
        item.addEventListener("click", async () => {
            const pageName = item.dataset.page;
            activatePage(pageName);

            if (pageName === "convos") {
                await loadConversations();
            }
        });
    });

    document.querySelectorAll(".tab-item").forEach((item) => {
        item.addEventListener("click", () => activateTab(item.dataset.tab));
    });

    document.getElementById("apply-filters").addEventListener("click", () => {
        loadConversations().catch((error) => {
            convoList.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        });
    });

    document.getElementById("clear-filters").addEventListener("click", () => {
        filterTopic.value = "all";
        filterMinMessages.value = "";
        filterMaxMessages.value = "";
        loadConversations().catch((error) => {
            convoList.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        });
    });

    convoList.addEventListener("click", (event) => {
        const card = event.target.closest(".convo-item");
        if (!card) {
            return;
        }

        const conversationId = card.dataset.conversationId;
        if (!conversationId) {
            return;
        }

        openConversation(conversationId).catch((error) => {
            convoList.insertAdjacentHTML(
                "afterbegin",
                `<div class="empty-state">${escapeHtml(error.message)}</div>`,
            );
        });
    });

    document.getElementById("close-conversation-drawer").addEventListener("click", closeDrawers);
    document.getElementById("close-add-tool-drawer").addEventListener("click", closeDrawers);
    drawerOverlay.addEventListener("click", closeDrawers);

    document.getElementById("save-aop").addEventListener("click", saveAop);

    toolsList.addEventListener("click", (event) => {
        const saveButton = event.target.closest(".save-tool-btn");
        if (!saveButton) {
            return;
        }

        const toolCard = event.target.closest(".tool-card");
        if (!toolCard) {
            return;
        }

        saveTool(toolCard);
    });

    document.getElementById("open-add-tool").addEventListener("click", () => {
        newToolStatus.textContent = "";
        openDrawer(addToolDrawer);
    });

    document.getElementById("save-new-tool").addEventListener("click", createNewTool);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeDrawers();
        }
    });
}

async function bootstrap() {
    bindEvents();
    activatePage("home");
    activateTab("aop");

    try {
        await Promise.all([loadMetricsAndCharts(), loadConversations(), loadAop()]);
    } catch (error) {
        const message = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        convoList.innerHTML = message;
        document.getElementById("home-topic-legend").innerHTML = message;
        document.getElementById("home-disposition-bars").innerHTML = message;
    }
}

bootstrap();
