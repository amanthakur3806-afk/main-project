/**
 * Multi-MCP Agent Platform Frontend Controller
 */

let agentsData = [];
let currentExecutionId = null;

function initApp() {
  initTabs();
  loadAgents();
  loadMCPCatalog();
  setupRunHandler();
  setupUploadHandler();

  // Set default query in textarea
  const queryBox = document.getElementById("queryInput");
  if (queryBox && !queryBox.value) {
    queryBox.value = "Give me a complete summary of customer ABC including recent activity and internal documentation.";
  }
}

// Ensure initApp runs whether DOMContentLoaded has already fired or not
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

// Tab Switcher
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");
    });
  });
}

// Load Agent List
async function loadAgents() {
  try {
    const res = await fetch("/agents");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    agentsData = await res.json();
    const select = document.getElementById("agentSelect");
    select.innerHTML = "";

    agentsData.forEach((agent, idx) => {
      const opt = document.createElement("option");
      opt.value = agent.agent_id;
      opt.textContent = `${agent.agent_name} (${agent.agent_id})`;
      if (idx === 0) opt.selected = true;
      select.appendChild(opt);
    });

    select.addEventListener("change", () => onAgentSelected(select.value));
    if (agentsData.length > 0) {
      onAgentSelected(agentsData[0].agent_id);
    }
  } catch (err) {
    console.error("Failed to load agents:", err);
    const select = document.getElementById("agentSelect");
    select.innerHTML = `<option value="customer_research_agent">Customer Research Specialist (customer_research_agent)</option>`;
  }
}

function onAgentSelected(agentId) {
  const agent = agentsData.find(a => a.agent_id === agentId);
  if (!agent) return;

  document.getElementById("agentModel").textContent = agent.model;
  const kb = agent.workflow_configuration?.knowledge_base || "None";
  document.getElementById("agentKB").textContent = kb;

  const toolsList = document.getElementById("agentToolsList");
  toolsList.innerHTML = "";
  (agent.allowed_tools || []).forEach(t => {
    const tag = document.createElement("span");
    tag.className = "tool-tag";
    tag.textContent = t;
    toolsList.appendChild(tag);
  });
}

function setPreset(queryText) {
  const box = document.getElementById("queryInput");
  if (box) box.value = queryText;
}
window.setPreset = setPreset;

// Run Agent Workflow
function setupRunHandler() {
  const runBtn = document.getElementById("runBtn");
  if (!runBtn) return;

  runBtn.addEventListener("click", async () => {
    const selectEl = document.getElementById("agentSelect");
    const agentId = selectEl.value || "customer_research_agent";
    const query = document.getElementById("queryInput").value.trim();
    const conversationId = document.getElementById("conversationId").value.trim() || "conv_001";

    if (!query) {
      alert("Please enter a query or select a preset.");
      return;
    }

    // UI Loading state
    runBtn.disabled = true;
    document.getElementById("runSpinner").style.display = "inline-block";
    document.getElementById("runBtnText").textContent = "Executing Multi-MCP Workflow...";

    try {
      const res = await fetch(`/agents/${agentId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, conversation_id: conversationId })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Agent execution failed (status: ${res.status}).`);
      }

      const data = await res.json();
      currentExecutionId = data.execution_id;

      // Render Final Answer
      renderAnswer(data);

      // Fetch & Render Execution Trace
      await fetchAndRenderTrace(data.execution_id);

      // Render Sources
      renderSources(data.sources || []);

      // Fetch & Render Prompt Audit
      await fetchAndRenderPrompt(data.execution_id);

    } catch (err) {
      alert("Error executing agent: " + err.message);
    } finally {
      runBtn.disabled = false;
      document.getElementById("runSpinner").style.display = "none";
      document.getElementById("runBtnText").textContent = "Run Agent Workflow";
    }
  });
}

function renderAnswer(data) {
  document.getElementById("welcomeState").style.display = "none";
  document.getElementById("resultContainer").style.display = "block";

  document.getElementById("execIdDisplay").textContent = data.execution_id;
  document.getElementById("execDurationDisplay").textContent = `${data.duration_ms}ms`;

  const formattedHtml = parseMarkdown(data.answer);
  document.getElementById("answerContent").innerHTML = formattedHtml;

  // Switch to answer tab
  const answerBtn = document.querySelector('[data-tab="answerTab"]');
  if (answerBtn) answerBtn.click();
}

async function fetchAndRenderTrace(executionId) {
  try {
    const res = await fetch(`/executions/${executionId}`);
    if (!res.ok) return;
    const data = await res.json();
    const steps = data.steps || [];

    document.getElementById("traceStepCount").textContent = steps.length;
    document.getElementById("traceEmptyState").style.display = "none";
    const timeline = document.getElementById("traceTimeline");
    timeline.style.display = "flex";
    timeline.innerHTML = "";

    steps.forEach(s => {
      const item = document.createElement("div");
      item.className = "trace-step-card";
      item.innerHTML = `
        <div class="step-info">
          <div class="step-number">${s.step_number}</div>
          <div>
            <div class="step-name">${escapeHtml(s.step_name)}</div>
            <div class="step-meta">Status: <span class="badge ${s.status === 'completed' ? 'badge-success' : 'badge-danger'}">${s.status}</span> • Duration: ${s.duration_ms}ms</div>
          </div>
        </div>
      `;
      timeline.appendChild(item);
    });
  } catch (err) {
    console.error("Failed to fetch trace:", err);
  }
}

function renderSources(sources) {
  document.getElementById("sourcesCount").textContent = sources.length;
  if (sources.length === 0) return;

  document.getElementById("sourcesEmptyState").style.display = "none";
  const container = document.getElementById("sourcesList");
  container.style.display = "flex";
  container.innerHTML = "";

  sources.forEach(src => {
    const card = document.createElement("div");
    card.className = "source-card";
    card.innerHTML = `
      <div class="source-card-header">
        <span class="source-title">📄 ${escapeHtml(src.document_name)} (Chunk #${src.chunk_index})</span>
        <span class="badge badge-purple">Similarity: ${(src.similarity_score * 100).toFixed(1)}%</span>
      </div>
      <div class="source-snippet">${escapeHtml(src.snippet)}</div>
    `;
    container.appendChild(card);
  });
}

async function fetchAndRenderPrompt(executionId) {
  try {
    const res = await fetch(`/executions/${executionId}/prompt`);
    if (res.ok) {
      const text = await res.text();
      document.getElementById("promptContent").textContent = text;
    }
  } catch (err) {
    console.error("Failed to load prompt log:", err);
  }
}

async function loadMCPCatalog() {
  try {
    const serversRes = await fetch("/mcp/servers");
    if (!serversRes.ok) return;
    const servers = await serversRes.json();
    const serverList = document.getElementById("mcpServerList");
    serverList.innerHTML = "";

    servers.forEach(s => {
      const card = document.createElement("div");
      card.className = "server-card";
      card.innerHTML = `
        <h4>${escapeHtml(s.server_name)}</h4>
        <p class="text-sm">ID: <code>${escapeHtml(s.server_id)}</code></p>
        <p class="text-sm">Transport: <span class="badge">${escapeHtml(s.transport)}</span></p>
        <p class="text-sm">Status: <span class="badge badge-success">${escapeHtml(s.status)}</span></p>
      `;
      serverList.appendChild(card);
    });

    const toolsRes = await fetch("/mcp/tools");
    if (!toolsRes.ok) return;
    const tools = await toolsRes.json();
    const tableDiv = document.getElementById("mcpToolsTable");

    let tableHtml = `
      <table>
        <thead>
          <tr>
            <th>Tool Name</th>
            <th>Server</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
    `;

    tools.forEach(t => {
      tableHtml += `
        <tr>
          <td><code>${escapeHtml(t.tool_name)}</code></td>
          <td><span class="badge">${escapeHtml(t.server_id)}</span></td>
          <td>${escapeHtml(t.description)}</td>
        </tr>
      `;
    });

    tableHtml += `</tbody></table>`;
    tableDiv.innerHTML = tableHtml;

  } catch (err) {
    console.error("Failed to load MCP catalog:", err);
  }
}

function setupUploadHandler() {
  const form = document.getElementById("uploadForm");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const kbId = document.getElementById("uploadKB").value;
    const fileInput = document.getElementById("uploadFile");
    const statusDiv = document.getElementById("uploadStatus");

    if (!fileInput.files || fileInput.files.length === 0) return;

    const formData = new FormData();
    formData.append("kb_id", kbId);
    formData.append("file", fileInput.files[0]);

    statusDiv.textContent = "Uploading & chunking...";

    try {
      const res = await fetch("/knowledge/upload", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      statusDiv.textContent = `✓ Ingested: ${data.documents_ingested} doc (${data.chunks_created} chunks in FAISS)`;
      fileInput.value = "";
    } catch (err) {
      statusDiv.textContent = "Upload failed: " + err.message;
    }
  });
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Robust Markdown Formatter
function parseMarkdown(md) {
  if (!md) return "";
  let html = md
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^\- (.*$)/gim, '<li>$1</li>')
    .replace(/\n\n/g, '<br><br>');
  return html;
}
