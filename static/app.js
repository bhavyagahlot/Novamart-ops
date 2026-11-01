/**
 * NovaMart Ops - Frontend Orchestration
 */

let currentConversationId = null;

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const nameInput = document.getElementById("customer-name");
  const messageInput = document.getElementById("customer-message");
  const submitBtn = document.getElementById("btn-submit");
  const btnText = submitBtn.querySelector(".btn-text");
  const btnSpinner = submitBtn.querySelector(".btn-spinner");
  const replyContent = document.getElementById("customer-reply-content");
  const replyTime = document.getElementById("reply-time");
  const approvalBanner = document.getElementById("approval-banner");
  const approvalNoticeText = document.getElementById("approval-notice-text");
  const agentChainList = document.getElementById("agent-chain-list");
  const traceSummary = document.getElementById("trace-summary");
  const synapseDashboardLink = document.getElementById("synapse-dashboard-link");

  // Fetch initial public configuration
  let synapseUrl = "/synapse-dashboard";
  if (synapseDashboardLink) {
    synapseDashboardLink.href = "/synapse-dashboard";
  }

  fetch("/api/config")
    .then(res => res.json())
    .then(config => {
      if (config.synapse_url && !config.synapse_url.includes("example.com")) {
        synapseUrl = config.synapse_url.includes("localhost") ? "/synapse-dashboard" : config.synapse_url;
      } else {
        synapseUrl = "/synapse-dashboard";
      }
      if (synapseDashboardLink) {
        synapseDashboardLink.href = synapseUrl;
      }
    })
    .catch(err => console.warn("Could not load public config:", err));

  // Quick-test buttons handler
  const quickButtons = document.querySelectorAll(".btn-quick");
  quickButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const promptText = btn.getAttribute("data-text");
      if (promptText) {
        messageInput.value = promptText;
        form.dispatchEvent(new Event("submit"));
      }
    });
  });

  // Form submit handler
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const customerName = nameInput.value.trim() || "Alex Rivera";
    const message = messageInput.value.trim();

    if (!message) return;

    // UI Loading state
    submitBtn.disabled = true;
    btnText.textContent = "Dispatching Agents...";
    btnSpinner.style.display = "inline-block";

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          customer_name: customerName,
          message: message,
          conversation_id: currentConversationId
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      currentConversationId = data.conversation_id;

      // Render Customer Reply
      replyContent.textContent = data.reply;
      const now = new Date();
      replyTime.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

      // Render Approval Notice
      if (data.requires_approval && data.approval_notice) {
        approvalBanner.style.display = "flex";
        approvalNoticeText.textContent = data.approval_notice;
      } else {
        approvalBanner.style.display = "none";
      }

      // Render Agent Execution Trace
      renderAgentTrace(data.runs);

    } catch (err) {
      console.error("Chat dispatch error:", err);
      replyContent.textContent = "Error executing multi-agent pipeline. Please ensure the server is running.";
      approvalBanner.style.display = "none";
    } finally {
      submitBtn.disabled = false;
      btnText.textContent = "Send Message";
      btnSpinner.style.display = "none";
    }
  });

  function renderAgentTrace(runs) {
    if (!runs || runs.length === 0) {
      agentChainList.innerHTML = `
        <div class="empty-trace-state">
          <div class="empty-icon">⚡</div>
          <div class="empty-title">No Runs Recorded</div>
        </div>
      `;
      return;
    }

    let totalTokens = 0;
    let totalCost = 0;

    const cardsHtml = runs.map((run, index) => {
      const inTok = run.input_tokens || 0;
      const outTok = run.output_tokens || 0;
      const runTokens = inTok + outTok;
      const cost = run.cost_usd || 0;
      const latency = run.latency_ms || 0;
      const status = run.status || "COMPLETED";

      totalTokens += runTokens;
      totalCost += cost;

      const stepsHtml = (run.steps || []).map(s => `
        <div class="step-item">
          <span class="step-bullet">›</span>
          <span>${escapeHtml(s.step)}</span>
          <span class="step-offset">${s.time_offset_ms ? s.time_offset_ms + 'ms' : ''}</span>
        </div>
      `).join("");

      return `
        <div class="agent-card">
          <div class="agent-card-header">
            <div class="agent-identity">
              <span class="agent-index">0${index + 1}</span>
              <span class="agent-name">${escapeHtml(run.agent_name)}</span>
            </div>
            <span class="chip chip-${status}">
              ${status === "WAITING_APPROVAL" ? "⏳ WAITING_APPROVAL" : status}
            </span>
          </div>

          <div class="agent-metrics">
            <div class="metric-item">
              <span>Tokens:</span>
              <span class="metric-val">${inTok} in / ${outTok} out</span>
            </div>
            <span class="dot-separator">•</span>
            <div class="metric-item">
              <span>Cost:</span>
              <span class="metric-val">$${cost.toFixed(6)}</span>
            </div>
            <span class="dot-separator">•</span>
            <div class="metric-item">
              <span>Latency:</span>
              <span class="metric-val">${latency}ms</span>
            </div>
          </div>

          <div class="trace-steps">
            <div class="steps-label">Execution Trace</div>
            ${stepsHtml}
          </div>
        </div>
      `;
    }).join("");

    agentChainList.innerHTML = cardsHtml;

    // Update aggregate summary
    traceSummary.innerHTML = `
      <span>${totalTokens} total tokens</span>
      <span class="dot-separator">•</span>
      <span>$${totalCost.toFixed(6)}</span>
    `;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
