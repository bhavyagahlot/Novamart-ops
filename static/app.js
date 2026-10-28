document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chatForm");
  const customerNameInput = document.getElementById("customerName");
  const customerMessageInput = document.getElementById("customerMessage");
  const sendBtn = document.getElementById("sendBtn");
  const btnText = document.getElementById("btnText");
  const btnSpinner = document.getElementById("btnSpinner");

  // Output elements
  const replyContainer = document.getElementById("replyContainer");
  const replyBody = document.getElementById("replyBody");
  const replyStatusChip = document.getElementById("replyStatusChip");
  const approvalBanner = document.getElementById("approvalBanner");
  const approvalText = document.getElementById("approvalText");

  // Trace elements
  const traceRunId = document.getElementById("traceRunId");
  const agentsRanStrip = document.getElementById("agentsRanStrip");
  const metricsGrid = document.getElementById("metricsGrid");
  const metricInTokens = document.getElementById("metricInTokens");
  const metricOutTokens = document.getElementById("metricOutTokens");
  const metricCost = document.getElementById("metricCost");
  const metricLatency = document.getElementById("metricLatency");
  const stepsList = document.getElementById("stepsList");
  const inventoryChips = document.getElementById("inventoryChips");

  // Header elements
  const synapseDashboardLink = document.getElementById("synapseDashboardLink");
  const geminiModelPill = document.getElementById("geminiModelPill");

  // 1. Fetch initial configuration & products
  fetchConfig();
  fetchProducts();

  async function fetchConfig() {
    try {
      const res = await fetch("/api/config");
      if (res.ok) {
        const data = await res.json();
        if (data.synapse_url) {
          synapseDashboardLink.href = data.synapse_url;
        }
        if (data.gemini_model) {
          geminiModelPill.textContent = data.gemini_model;
        }
      }
    } catch (err) {
      console.warn("Could not load /api/config:", err);
    }
  }

  async function fetchProducts() {
    try {
      const res = await fetch("/api/products");
      if (res.ok) {
        const data = await res.json();
        renderProducts(data.products || []);
      }
    } catch (err) {
      console.warn("Could not load products:", err);
    }
  }

  function renderProducts(products) {
    if (!products.length) {
      inventoryChips.innerHTML = '<span class="inv-chip mono-text">No products in inventory</span>';
      return;
    }
    inventoryChips.innerHTML = products.map(p => `
      <span class="inv-chip mono-text" title="${p.description}">
        ${p.name}: <strong>$${p.price.toFixed(2)}</strong> (${p.stock} in stock)
      </span>
    `).join("");
  }

  // 2. Quick Actions
  document.querySelectorAll(".quick-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const query = btn.getAttribute("data-query");
      customerMessageInput.value = query;
      submitInquiry();
    });
  });

  // 3. Form Submit
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submitInquiry();
  });

  async function submitInquiry() {
    const customerName = customerNameInput.value.trim() || "Alex Mercer";
    const message = customerMessageInput.value.trim();
    if (!message) return;

    setLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_name: customerName,
          message: message
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Server error processing message");
      }

      const data = await response.json();
      renderExecutionResult(data);
      // Refresh inventory in case an order decremented stock
      fetchProducts();
    } catch (err) {
      console.error("Error executing inquiry:", err);
      replyStatusChip.className = "chip chip-error";
      replyStatusChip.textContent = "ERROR";
      replyBody.innerHTML = `<span style="color: #dc2626;">Error: ${err.message}</span>`;
      approvalBanner.style.display = "none";
    } finally {
      setLoading(false);
    }
  }

  function renderExecutionResult(data) {
    // 1. Trace ID
    traceRunId.textContent = `Run: ${data.run_id}`;

    // 2. Reply & Status
    replyBody.textContent = data.reply;
    updateChip(replyStatusChip, data.status);

    // 3. Approval Banner
    if (data.status === "WAITING_APPROVAL" && data.approval_notice) {
      approvalText.textContent = data.approval_notice;
      approvalBanner.style.display = "flex";
    } else {
      approvalBanner.style.display = "none";
    }

    // 4. Agents Ran Strip (Triage first, then specialized agent)
    if (data.agents_ran && data.agents_ran.length > 0) {
      agentsRanStrip.innerHTML = data.agents_ran.map(agent => `
        <div class="agent-row-card">
          <div class="agent-info">
            <span class="chip ${getChipClass(agent.status)}">${agent.status}</span>
            <span class="agent-title">${agent.agent_name}</span>
          </div>
          <div class="agent-metrics-mini mono-text">
            <span>In: ${agent.input_tokens}</span>
            <span>Out: ${agent.output_tokens}</span>
            <span>$${agent.cost_usd.toFixed(6)}</span>
            <span>${agent.latency_ms.toFixed(0)}ms</span>
          </div>
        </div>
      `).join("");
    } else {
      agentsRanStrip.innerHTML = '<div class="empty-trace-note">No agents registered.</div>';
    }

    // 5. Aggregated Metrics
    metricsGrid.style.display = "grid";
    metricInTokens.textContent = data.metrics.total_input_tokens;
    metricOutTokens.textContent = data.metrics.total_output_tokens;
    metricCost.textContent = `$${data.metrics.total_cost_usd.toFixed(6)}`;
    metricLatency.textContent = `${data.metrics.total_latency_ms.toFixed(0)} ms`;

    // 6. Detailed Steps
    if (data.steps && data.steps.length > 0) {
      stepsList.innerHTML = data.steps.map(s => `
        <div class="step-item">
          <div class="step-header">
            <span class="step-num mono-text">#${s.step_number}</span>
            <span class="step-agent">${s.agent_name}</span>
            <span class="step-action mono-text">${s.action}</span>
          </div>
          <div class="step-detail">${s.detail}</div>
        </div>
      `).join("");
    } else {
      stepsList.innerHTML = '<div class="empty-steps">No steps recorded.</div>';
    }
  }

  function getChipClass(status) {
    switch (status) {
      case "COMPLETED": return "chip-completed";
      case "WAITING_APPROVAL": return "chip-waiting";
      case "PROCESSING": return "chip-processing";
      case "ERROR": return "chip-error";
      default: return "chip-completed";
    }
  }

  function updateChip(el, status) {
    el.className = `chip ${getChipClass(status)}`;
    el.textContent = status;
  }

  function setLoading(isLoading) {
    sendBtn.disabled = isLoading;
    if (isLoading) {
      btnText.textContent = "Processing...";
      btnSpinner.style.display = "inline-block";
      replyStatusChip.className = "chip chip-processing";
      replyStatusChip.textContent = "PROCESSING";
    } else {
      btnText.textContent = "Send Inquiry";
      btnSpinner.style.display = "none";
    }
  }
});
