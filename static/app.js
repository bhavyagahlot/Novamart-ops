/**
 * NovaMart Ops — Enterprise SaaS Multi-Agent Control Plane
 */

let currentConversationId = null;
let activeTab = "overview";
let killSwitchActive = false;

function bootApp() {
  try { initClock(); } catch(e) { console.error("initClock error", e); }
  try { initNavigation(); } catch(e) { console.error("initNavigation error", e); }
  try { initCustomerOps(); } catch(e) { console.error("initCustomerOps error", e); }
  try { initStoreCatalog(); } catch(e) { console.error("initStoreCatalog error", e); }
  try { initAgentNetwork(); } catch(e) { console.error("initAgentNetwork error", e); }
  try { initLiveTrace(); } catch(e) { console.error("initLiveTrace error", e); }
  try { initRequestHistory(); } catch(e) { console.error("initRequestHistory error", e); }
  try { initSynapseMonitoring(); } catch(e) { console.error("initSynapseMonitoring error", e); }
  try { initSettings(); } catch(e) { console.error("initSettings error", e); }

  // Load initial metrics, catalog, and settings immediately
  try { loadOverviewAnalytics(); } catch(e) { console.error("loadOverviewAnalytics error", e); }
  try { loadStoreCatalog(); } catch(e) { console.error("loadStoreCatalog error", e); }
  try { loadSettingsView(); } catch(e) { console.error("loadSettingsView error", e); }
  try { checkKillSwitchStatus(); } catch(e) { console.error("checkKillSwitchStatus error", e); }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootApp);
} else {
  bootApp();
}

// ==============================================================================
// 1. Clock & System Header
// ==============================================================================
function initClock() {
  const clockEl = document.getElementById("live-clock");
  if (!clockEl) return;
  function tick() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour12: false });
  }
  tick();
  setInterval(tick, 1000);
}

// ==============================================================================
// 2. Tab Navigation
// ==============================================================================
function initNavigation() {
  const navButtons = document.querySelectorAll(".nav-item");
  const tabViews = document.querySelectorAll(".view-tab");
  const titleEl = document.getElementById("current-view-title");

  const titles = {
    "overview": "Overview Dashboard",
    "catalog": "Electronics Store Catalog",
    "customer-ops": "Customer Operations Console",
    "agent-network": "Multi-Agent Topology Visualization",
    "live-trace": "Live Execution Trace",
    "request-history": "Request Audit History",
    "synapse-monitor": "Synapse OS Observability & Governance",
    "settings": "System Settings & Policies"
  };

  navButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      if (!targetTab) return;

      activeTab = targetTab;

      // Update Nav buttons
      navButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      // Switch Tab view
      tabViews.forEach(v => v.classList.remove("active"));
      const activeView = document.getElementById(`tab-${targetTab}`);
      if (activeView) activeView.classList.add("active");

      // Update Title
      if (titleEl && titles[targetTab]) {
        titleEl.textContent = titles[targetTab];
      }

      // Refresh view-specific data
      if (targetTab === "overview") loadOverviewAnalytics();
      if (targetTab === "catalog") loadStoreCatalog();
      if (targetTab === "live-trace") loadLiveTraceFeed();
      if (targetTab === "request-history") loadRequestHistory();
      if (targetTab === "synapse-monitor") loadSynapseApprovals();
      if (targetTab === "settings") loadSettingsView();
    });
  });
}

// ==============================================================================
// 3. Overview Dashboard & Visualizations
// ==============================================================================
async function loadOverviewAnalytics() {
  const refreshBtn = document.getElementById("btn-refresh-analytics");
  if (refreshBtn) refreshBtn.classList.add("loading");

  try {
    const res = await fetch("/api/analytics");
    if (!res.ok) throw new Error("Could not fetch analytics");
    const data = await res.json();

    // Populate KPIs safely
    const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setTxt("kpi-total-requests", data.total_requests || 0);
    setTxt("kpi-total-runs", data.total_runs || 0);
    
    const successRate = data.total_runs > 0 ? Math.round((data.successful_executions / data.total_runs) * 100) : 100;
    setTxt("kpi-success-rate", `${successRate}%`);
    setTxt("kpi-successful-count", data.successful_executions || 0);
    
    setTxt("kpi-waiting-count", data.waiting_approval || 0);
    setTxt("kpi-failed-count", data.failed_executions || 0);

    setTxt("kpi-total-tokens", (data.total_tokens || 0).toLocaleString());
    setTxt("kpi-token-split", `${(data.input_tokens || 0).toLocaleString()} in / ${(data.output_tokens || 0).toLocaleString()} out`);

    setTxt("kpi-total-cost", `$${(data.total_cost_usd || 0).toFixed(6)}`);
    setTxt("kpi-avg-latency", `${Math.round(data.average_latency_ms || 0)} ms`);

    // Update Pending approvals badge in sidebar
    const badge = document.getElementById("sidebar-pending-badge");
    if (badge) {
      if (data.waiting_approval > 0) {
        badge.style.display = "inline-block";
        badge.textContent = data.waiting_approval;
      } else {
        badge.style.display = "none";
      }
    }

    // Render Charts
    renderAgentDistributionChart(data.agent_distribution || []);
    renderTokenConsumptionChart(data.agent_distribution || []);
    renderRecentTimelineChart(data.recent_runs || []);

  } catch (err) {
    console.error("Overview metrics error:", err);
  } finally {
    if (refreshBtn) refreshBtn.classList.remove("loading");
  }
}

function renderAgentDistributionChart(distribution) {
  const container = document.getElementById("agent-distribution-chart");
  if (!container) return;

  if (!distribution || distribution.length === 0) {
    container.innerHTML = `<div class="empty-placeholder"><div class="empty-desc">No agent executions recorded yet.</div></div>`;
    return;
  }

  const totalRuns = distribution.reduce((sum, item) => sum + item.run_count, 0);

  const colors = {
    "Triage Agent": "#8b5cf6",
    "Order Agent": "#3b82f6",
    "Pricing Agent": "#f59e0b",
    "Billing Agent": "#10b981"
  };

  const barsHtml = distribution.map(item => {
    const pct = totalRuns > 0 ? Math.round((item.run_count / totalRuns) * 100) : 0;
    const color = colors[item.agent_name] || "#64748b";
    return `
      <div style="margin-bottom: 12px; width: 100%;">
        <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px;">
          <span style="font-weight: 600; color: #f8fafc;">${item.agent_name}</span>
          <span class="mono-text" style="color: var(--text-secondary);">${item.run_count} runs (${pct}%)</span>
        </div>
        <div style="height: 8px; width: 100%; background: var(--bg-surface); border-radius: 999px; overflow: hidden; border: 1px solid var(--border-subtle);">
          <div style="height: 100%; width: ${pct}%; background: ${color}; border-radius: 999px; transition: width 0.5s ease;"></div>
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = `<div style="width: 100%; padding: 10px 0;">${barsHtml}</div>`;
}

function renderTokenConsumptionChart(distribution) {
  const container = document.getElementById("agent-tokens-chart");
  if (!container) return;

  if (!distribution || distribution.length === 0) {
    container.innerHTML = `<div class="empty-placeholder"><div class="empty-desc">No token metrics recorded.</div></div>`;
    return;
  }

  const maxTokens = Math.max(...distribution.map(d => d.tokens || 1));

  const itemsHtml = distribution.map(item => {
    const pct = Math.max(5, Math.round(((item.tokens || 0) / maxTokens) * 100));
    return `
      <div style="margin-bottom: 12px; width: 100%;">
        <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px;">
          <span style="font-weight: 500; color: #f8fafc;">${item.agent_name}</span>
          <span class="mono-text" style="color: var(--text-secondary);">${(item.tokens || 0).toLocaleString()} tokens • $${(item.cost || 0).toFixed(6)}</span>
        </div>
        <div style="height: 8px; width: 100%; background: var(--bg-surface); border-radius: 999px; overflow: hidden; border: 1px solid var(--border-subtle);">
          <div style="height: 100%; width: ${pct}%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); border-radius: 999px; transition: width 0.5s ease;"></div>
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = `<div style="width: 100%; padding: 10px 0;">${itemsHtml}</div>`;
}

function renderRecentTimelineChart(recentRuns) {
  const container = document.getElementById("recent-activity-chart");
  if (!container) return;

  if (!recentRuns || recentRuns.length === 0) {
    container.innerHTML = `<div class="empty-placeholder"><div class="empty-desc">No execution timeline data available.</div></div>`;
    return;
  }

  const maxLat = Math.max(...recentRuns.map(r => r.latency_ms || 1));

  const bars = recentRuns.map((r, i) => {
    const heightPct = Math.max(8, Math.min(100, Math.round(((r.latency_ms || 10) / maxLat) * 100)));
    const color = r.status === "COMPLETED" ? "#10b981" : (r.status === "WAITING_APPROVAL" ? "#f59e0b" : "#ef4444");
    const timeStr = r.created_at ? r.created_at.split(" ")[1] : `#${i+1}`;
    
    return `
      <div style="display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1; height: 160px; justify-content: flex-end;" title="${r.agent_name}: ${r.latency_ms}ms, ${r.tokens} tokens, Status: ${r.status}">
        <div class="mono-text" style="font-size: 10px; color: var(--text-muted);">${Math.round(r.latency_ms)}ms</div>
        <div style="width: 18px; height: ${heightPct}%; background: ${color}; border-radius: 4px; transition: height 0.3s ease; opacity: 0.85;"></div>
        <div class="mono-text" style="font-size: 9.5px; color: var(--text-dim); transform: rotate(-35deg); transform-origin: left top; margin-top: 6px;">${timeStr}</div>
      </div>
    `;
  }).join("");

  container.innerHTML = `
    <div style="width: 100%; display: flex; align-items: flex-end; justify-content: space-between; gap: 8px; padding-bottom: 24px; border-bottom: 1px solid var(--border-subtle);">
      ${bars}
    </div>
  `;
}

// ==============================================================================
// 3.5. Electronics Storefront & Product Catalog
// ==============================================================================
let cachedProducts = [];
let currentCategoryFilter = "ALL";
let currentSearchQuery = "";

const PRODUCT_METADATA = {
  1: {
    icon: "💻",
    desc: "16-inch Liquid Retina XDR display, M-Series silicon, 32GB Unified Memory, 1TB NVMe PCIe 4.0 SSD, MagSafe 3 fast charging.",
    specs: ["16\" Liquid Retina", "32GB RAM", "1TB SSD", "M-Silicon", "Space Gray"]
  },
  2: {
    icon: "💻",
    desc: "Ultra-portable 1.2kg wedge chassis, 13.6-inch IPS True Tone, 16GB RAM, 512GB SSD, whisper-quiet fanless architecture, 18hr battery.",
    specs: ["13.6\" IPS", "16GB RAM", "512GB SSD", "Fanless", "Midnight"]
  },
  3: {
    icon: "📱",
    desc: "6.8-inch AMOLED 120Hz LTPO display, 200MP quad-sensor camera array, Snapdragon 8 Gen 3, 5G Sub-6/mmWave, 5000mAh battery.",
    specs: ["6.8\" AMOLED 120Hz", "200MP Quad Cam", "256GB Storage", "5G Sub-6", "Titanium"]
  },
  4: {
    icon: "🎧",
    desc: "Hybrid active noise canceling, 40mm custom beryllium drivers, spatial audio with head tracking, ultra-low latency wireless, 40hr playtime.",
    specs: ["Active Noise Canceling", "40mm Beryllium", "Spatial Audio", "40hr Battery"]
  },
  5: {
    icon: "⌚",
    desc: "1.4-inch AMOLED display, sapphire crystal, optical bio-tracker (Heart Rate, ECG, SpO2), multi-band dual GPS, 5ATM water resistance.",
    specs: ["1.4\" AMOLED", "ECG + SpO2", "Dual GPS", "5ATM Water", "4-Day Battery"]
  },
  6: {
    icon: "⚡",
    desc: "Compact 100W gallium nitride (GaN II) fast charger. 2x USB-C Power Delivery 3.0, 1x USB-A QC 4.0. Charges laptops & phones simultaneously.",
    specs: ["100W GaN II", "2x USB-C + 1x USB-A", "PD 3.0 + QC 4.0", "Foldable Plug"]
  }
};

function initStoreCatalog() {
  const filterContainer = document.getElementById("catalog-category-filters");
  const searchInput = document.getElementById("catalog-search-input");
  const refreshBtn = document.getElementById("btn-refresh-catalog");

  if (filterContainer) {
    const pills = filterContainer.querySelectorAll(".filter-pill");
    pills.forEach(pill => {
      pill.addEventListener("click", () => {
        pills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        currentCategoryFilter = pill.getAttribute("data-category") || "ALL";
        renderStoreCatalog();
      });
    });
  }

  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentSearchQuery = e.target.value.trim().toLowerCase();
        renderStoreCatalog();
      }, 250);
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      loadStoreCatalog();
    });
  }
}

async function loadStoreCatalog() {
  const container = document.getElementById("store-catalog-grid");
  const refreshBtn = document.getElementById("btn-refresh-catalog");
  if (refreshBtn) refreshBtn.classList.add("loading");

  try {
    const res = await fetch("/api/products");
    if (!res.ok) throw new Error("Failed to fetch product inventory");
    cachedProducts = await res.json();
    renderStoreCatalog();
  } catch (err) {
    console.error("Store catalog load error:", err);
    if (container) {
      container.innerHTML = `<div class="empty-placeholder"><div class="empty-desc" style="color: var(--danger);">Failed to load products from database. Please verify backend service.</div></div>`;
    }
  } finally {
    if (refreshBtn) refreshBtn.classList.remove("loading");
  }
}

function renderStoreCatalog() {
  const container = document.getElementById("store-catalog-grid");
  if (!container) return;

  if (!cachedProducts || cachedProducts.length === 0) {
    container.innerHTML = `<div class="empty-placeholder"><div class="empty-desc">No products found in SQLite database.</div></div>`;
    return;
  }

  // Filter products by category and search query
  const filtered = cachedProducts.filter(p => {
    const matchCat = currentCategoryFilter === "ALL" || (p.category && p.category.toLowerCase() === currentCategoryFilter.toLowerCase());
    const matchSearch = !currentSearchQuery || 
      p.name.toLowerCase().includes(currentSearchQuery) || 
      p.category.toLowerCase().includes(currentSearchQuery);
    return matchCat && matchSearch;
  });

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-placeholder" style="grid-column: 1 / -1;"><div class="empty-desc">No electronics match the current filter or search query.</div></div>`;
    return;
  }

  container.innerHTML = filtered.map(product => {
    const meta = PRODUCT_METADATA[product.id] || {
      icon: "⚡",
      desc: `High-performance electronics product from NovaMart catalog. Guaranteed quality with 1-year warranty.`,
      specs: ["1-Year Warranty", "Free 2-Day Shipping"]
    };

    let stockBadge = "";
    let isOutOfStock = false;
    if (product.stock > 10) {
      stockBadge = `<span class="stock-pill stock-in">● In Stock (${product.stock} units)</span>`;
    } else if (product.stock > 0) {
      stockBadge = `<span class="stock-pill stock-low">⚠️ Low Stock (${product.stock} left)</span>`;
    } else {
      stockBadge = `<span class="stock-pill stock-out">✕ Sold Out</span>`;
      isOutOfStock = true;
    }

    const specsHtml = meta.specs.map(s => `<span class="spec-chip">${escapeHtml(s)}</span>`).join("");

    return `
      <div class="product-store-card">
        <div>
          <div class="product-card-top">
            <div class="product-icon-box">${meta.icon}</div>
            <span class="product-category-badge">${escapeHtml(product.category)}</span>
          </div>

          <h3 class="product-name-title">${escapeHtml(product.name)}</h3>
          <p class="product-desc-text">${escapeHtml(meta.desc)}</p>

          <div class="product-specs-chips">
            ${specsHtml}
          </div>
        </div>

        <div>
          <div class="product-price-stock-row">
            <div>
              <span style="font-size: 11px; color: var(--text-muted); display: block; text-transform: uppercase;">Direct Price</span>
              <span class="product-price-val">$${product.price.toFixed(2)}</span>
            </div>
            ${stockBadge}
          </div>

          <div class="product-card-actions">
            <button class="btn-primary" style="font-size: 12px; padding: 8px 10px; justify-content: center;" 
              ${isOutOfStock ? 'disabled title="Out of stock"' : ''}
              onclick="quickOrderProduct('${escapeHtml(product.name)}', ${product.price})">
              <span>⚡ Order via AI</span>
            </button>
            <button class="btn-secondary" style="font-size: 12px; padding: 8px 10px; justify-content: center;"
              onclick="quickDiscountProduct('${escapeHtml(product.name)}')">
              <span>🏷️ Ask Discount</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function quickOrderProduct(productName, price) {
  // Switch to Customer Operations tab
  const opsTabBtn = document.querySelector('.nav-item[data-tab="customer-ops"]');
  if (opsTabBtn) opsTabBtn.click();

  // Populate form
  const nameInput = document.getElementById("customer-name");
  const messageInput = document.getElementById("customer-message");
  const form = document.getElementById("chat-form");

  if (nameInput && !nameInput.value.trim()) {
    nameInput.value = "Alex Rivera";
  }
  if (messageInput) {
    messageInput.value = `I want to order 1 ${productName}`;
  }

  // Submit form
  if (form) {
    setTimeout(() => {
      form.dispatchEvent(new Event("submit"));
    }, 150);
  }
}

function quickDiscountProduct(productName) {
  // Switch to Customer Operations tab
  const opsTabBtn = document.querySelector('.nav-item[data-tab="customer-ops"]');
  if (opsTabBtn) opsTabBtn.click();

  // Populate form
  const nameInput = document.getElementById("customer-name");
  const messageInput = document.getElementById("customer-message");
  const form = document.getElementById("chat-form");

  if (nameInput && !nameInput.value.trim()) {
    nameInput.value = "Alex Rivera";
  }
  if (messageInput) {
    messageInput.value = `Can I get a 20% discount on the ${productName}?`;
  }

  // Submit form
  if (form) {
    setTimeout(() => {
      form.dispatchEvent(new Event("submit"));
    }, 150);
  }
}

// ==============================================================================
// 4. Customer Operations Terminal
// ==============================================================================
function initCustomerOps() {
  const form = document.getElementById("chat-form");
  const nameInput = document.getElementById("customer-name");
  const messageInput = document.getElementById("customer-message");
  const submitBtn = document.getElementById("btn-submit-chat");
  const btnText = submitBtn.querySelector(".btn-text");
  const btnSpinner = submitBtn.querySelector(".btn-spinner");
  const replyText = document.getElementById("reply-text");
  const replyTimestamp = document.getElementById("reply-timestamp");
  const approvalBanner = document.getElementById("approval-alert-banner");
  const approvalNoticeText = document.getElementById("approval-alert-text");
  const sequenceContainer = document.getElementById("ops-agent-sequence");
  const traceMeta = document.getElementById("ops-trace-meta");

  // Quick Scenarios buttons
  const scenarioBtns = document.querySelectorAll(".scenario-btn");
  scenarioBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const msg = btn.getAttribute("data-text");
      const name = btn.getAttribute("data-name");
      if (name) nameInput.value = name;
      if (msg) messageInput.value = msg;
      form.dispatchEvent(new Event("submit"));
    });
  });

  // Form submission handler
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const customer = nameInput.value.trim() || "Customer";
    const message = messageInput.value.trim();
    if (!message) return;

    // Loading State
    submitBtn.disabled = true;
    btnText.textContent = "Autonomous Pipeline Executing...";
    btnSpinner.style.display = "inline-block";
    replyText.textContent = "Analyzing query with Triage Agent and verifying stock/policies...";
    approvalBanner.style.display = "none";

    // Visual Topology Activation
    highlightActiveTopologyNode("triage");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_name: customer,
          message: message,
          conversation_id: currentConversationId
        })
      });

      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);

      const data = await res.json();
      currentConversationId = data.conversation_id;

      // Update Reply Box
      replyText.textContent = data.reply;
      const now = new Date();
      replyTimestamp.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

      // Approval Banner
      if (data.requires_approval && data.approval_notice) {
        approvalBanner.style.display = "flex";
        approvalNoticeText.textContent = data.approval_notice;
      } else {
        approvalBanner.style.display = "none";
      }

      // Render Sequence
      renderExecutionSequence(data.runs);

      // Highlight Specialist Node in Topology
      const specialistRun = data.runs.find(r => r.agent_name !== "Triage Agent");
      if (specialistRun) {
        if (specialistRun.agent_name.includes("Order")) highlightActiveTopologyNode("order");
        if (specialistRun.agent_name.includes("Pricing")) highlightActiveTopologyNode("pricing");
        if (specialistRun.agent_name.includes("Billing")) highlightActiveTopologyNode("billing");
      }

      // Refresh Overview Metrics in background
      loadOverviewAnalytics();

    } catch (err) {
      console.error("Pipeline failure:", err);
      replyText.textContent = "Pipeline execution error. Please verify backend service.";
    } finally {
      submitBtn.disabled = false;
      btnText.textContent = "Execute Multi-Agent Pipeline";
      btnSpinner.style.display = "none";
    }
  });

  function renderExecutionSequence(runs) {
    if (!runs || runs.length === 0) {
      sequenceContainer.innerHTML = `<div class="empty-placeholder"><div class="empty-desc">No execution recorded.</div></div>`;
      return;
    }

    let totalTokens = 0;
    let totalCost = 0;
    let totalLatency = 0;

    const cardsHtml = runs.map((run, idx) => {
      totalTokens += (run.input_tokens || 0) + (run.output_tokens || 0);
      totalCost += (run.cost_usd || 0);
      totalLatency += (run.latency_ms || 0);

      const stepsHtml = (run.steps || []).map(s => `
        <div class="step-row">
          <span class="step-bullet">›</span>
          <span>${escapeHtml(s.step)}</span>
          <span class="step-offset">${s.time_offset_ms ? s.time_offset_ms + 'ms' : ''}</span>
        </div>
      `).join("");

      return `
        <div class="agent-exec-card">
          <div class="exec-header">
            <div class="exec-title-row">
              <span class="mono-text" style="font-size: 11px; color: var(--text-muted); background: var(--bg-card); padding: 2px 6px; border-radius: 4px;">0${idx + 1}</span>
              <span class="agent-badge-name">${escapeHtml(run.agent_name)}</span>
            </div>
            <span class="chip chip-${run.status}">${run.status}</span>
          </div>

          <div class="exec-metrics-bar">
            <span>Tokens: ${run.input_tokens} in / ${run.output_tokens} out</span>
            <span>•</span>
            <span>Cost: $${(run.cost_usd || 0).toFixed(6)}</span>
            <span>•</span>
            <span>Latency: ${run.latency_ms}ms</span>
          </div>

          <div class="exec-steps">
            ${stepsHtml}
          </div>
        </div>
      `;
    }).join("");

    sequenceContainer.innerHTML = cardsHtml;
    traceMeta.textContent = `${Math.round(totalLatency)} ms • ${totalTokens} tokens • $${totalCost.toFixed(6)}`;
  }
}

// ==============================================================================
// 5. Topology Visualization & Active Nodes
// ==============================================================================
function initAgentNetwork() {
  // Static setup for topology
}

function highlightActiveTopologyNode(agentKey) {
  const nodes = ["triage", "order", "pricing", "billing"];
  nodes.forEach(key => {
    const el = document.getElementById(`node-${key}`);
    const chip = document.getElementById(`chip-${key}`);
    const cable = document.getElementById(`cable-${key}`);

    if (key === agentKey) {
      if (el) el.style.borderColor = "var(--primary)";
      if (chip) { chip.textContent = "ACTIVE"; chip.className = "chip chip-PROCESSING"; }
      if (cable) cable.setAttribute("stroke", "var(--primary)");
    } else {
      if (el) el.style.borderColor = "var(--border-default)";
      if (chip) { chip.textContent = "IDLE"; chip.className = "chip chip-COMPLETED"; }
      if (cable) cable.setAttribute("stroke", "#334155");
    }
  });

  // Revert back after 4 seconds
  setTimeout(() => {
    nodes.forEach(key => {
      const el = document.getElementById(`node-${key}`);
      const chip = document.getElementById(`chip-${key}`);
      const cable = document.getElementById(`cable-${key}`);
      if (el) el.style.borderColor = key === "triage" ? "rgba(139, 92, 246, 0.4)" : "var(--border-default)";
      if (chip) { chip.textContent = key === "triage" ? "READY" : "IDLE"; chip.className = "chip chip-COMPLETED"; }
      if (cable) cable.setAttribute("stroke", "#334155");
    });
  }, 4000);
}

// ==============================================================================
// 6. Live Execution Trace Feed
// ==============================================================================
async function loadLiveTraceFeed() {
  const feedContainer = document.getElementById("full-trace-feed");
  const filterSelect = document.getElementById("filter-trace-agent");
  if (!feedContainer) return;

  try {
    const res = await fetch("/api/v1/runs?limit=30");
    if (!res.ok) throw new Error("Could not load trace feed");
    const runs = await res.json();

    const selectedAgent = filterSelect ? filterSelect.value : "ALL";
    const filteredRuns = selectedAgent === "ALL" 
      ? runs 
      : runs.filter(r => r.agent_name.toLowerCase().includes(selectedAgent.toLowerCase()));

    if (filteredRuns.length === 0) {
      feedContainer.innerHTML = `<div class="empty-placeholder"><div class="empty-desc">No execution runs match filter.</div></div>`;
      return;
    }

    feedContainer.innerHTML = filteredRuns.map(run => {
      let steps = [];
      try {
        steps = typeof run.steps_json === "string" ? JSON.parse(run.steps_json) : (run.steps || []);
      } catch (e) { steps = []; }

      const stepsHtml = steps.map(s => `
        <div class="step-row">
          <span class="step-bullet">›</span>
          <span>${escapeHtml(s.step || s.action || "Step")}</span>
          <span class="step-offset">${s.time_offset_ms ? s.time_offset_ms + 'ms' : ''}</span>
        </div>
      `).join("");

      return `
        <div class="agent-exec-card">
          <div class="exec-header">
            <div>
              <span class="mono-text" style="font-size: 11px; color: var(--text-muted);">${run.id} • ${run.created_at}</span>
              <div style="font-size: 14px; font-weight: 600; color: #ffffff; margin-top: 2px;">${escapeHtml(run.agent_name)}</div>
            </div>
            <span class="chip chip-${run.status}">${run.status}</span>
          </div>

          <div class="exec-metrics-bar">
            <span>Tokens: ${run.input_tokens || 0} in / ${run.output_tokens || 0} out</span>
            <span>•</span>
            <span>Cost: $${(run.cost_usd || 0).toFixed(6)}</span>
            <span>•</span>
            <span>Latency: ${run.latency_ms || 0}ms</span>
          </div>

          <div style="font-size: 13px; color: var(--text-primary); background: var(--bg-card); padding: 10px 12px; border-radius: 6px; border: 1px solid var(--border-subtle);">
            ${escapeHtml(run.output_text || "No output summary.")}
          </div>

          ${steps.length > 0 ? `<div class="exec-steps">${stepsHtml}</div>` : ''}
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("Live trace error:", err);
  }
}

function initLiveTrace() {
  const filterSelect = document.getElementById("filter-trace-agent");
  if (filterSelect) {
    filterSelect.addEventListener("change", loadLiveTraceFeed);
  }
}

// ==============================================================================
// 7. Request History & Modal Trace Inspector
// ==============================================================================
async function loadRequestHistory() {
  const tableBody = document.getElementById("history-table-body");
  const searchInput = document.getElementById("history-search-input");
  const statusSelect = document.getElementById("history-status-filter");
  const agentSelect = document.getElementById("history-agent-filter");
  if (!tableBody) return;

  const search = searchInput ? searchInput.value.trim() : "";
  const status = statusSelect ? statusSelect.value : "ALL";
  const agent = agentSelect ? agentSelect.value : "ALL";

  try {
    const url = `/api/history?search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}&agent=${encodeURIComponent(agent)}&limit=50`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Could not load history");
    const records = await res.json();

    if (records.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px;">No historical requests found matching criteria.</td></tr>`;
      return;
    }

    tableBody.innerHTML = records.map(r => `
      <tr>
        <td class="mono-text" style="color: var(--primary); font-size: 12px;">${r.conversation_id}</td>
        <td><strong>${escapeHtml(r.customer_name)}</strong></td>
        <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(r.query)}</td>
        <td class="mono-text" style="font-size: 11.5px; color: var(--text-secondary);">${r.agents_chain}</td>
        <td><span class="chip chip-${r.final_status}">${r.final_status}</span></td>
        <td class="mono-text">${r.total_tokens}</td>
        <td class="mono-text">$${(r.total_cost || 0).toFixed(6)}</td>
        <td class="mono-text" style="font-size: 11px;">${r.started_at}</td>
        <td>
          <button class="btn-secondary" onclick="openConversationModal('${r.conversation_id}', '${escapeHtml(r.customer_name)}')">
            Inspect
          </button>
        </td>
      </tr>
    `).join("");

  } catch (err) {
    console.error("History loading error:", err);
  }
}

function initRequestHistory() {
  const searchInput = document.getElementById("history-search-input");
  const statusSelect = document.getElementById("history-status-filter");
  const agentSelect = document.getElementById("history-agent-filter");

  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(loadRequestHistory, 300);
    });
  }

  if (statusSelect) statusSelect.addEventListener("change", loadRequestHistory);
  if (agentSelect) agentSelect.addEventListener("change", loadRequestHistory);

  // Modal Close
  const closeBtn = document.getElementById("btn-close-modal");
  const modal = document.getElementById("conversation-modal");
  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => modal.style.display = "none");
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.style.display = "none";
    });
  }
}

async function openConversationModal(conversationId, customerName) {
  const modal = document.getElementById("conversation-modal");
  const titleEl = document.getElementById("modal-conv-id");
  const metaEl = document.getElementById("modal-conv-meta");
  const contentEl = document.getElementById("modal-trace-content");

  if (!modal || !contentEl) return;

  titleEl.textContent = `Conversation ${conversationId}`;
  metaEl.textContent = `Customer: ${customerName} • Fetching trace events...`;
  contentEl.innerHTML = `<div class="empty-placeholder"><div class="btn-spinner"></div></div>`;
  modal.style.display = "flex";

  try {
    const res = await fetch(`/api/trace/${conversationId}`);
    if (!res.ok) throw new Error("Failed to fetch conversation trace");
    const runs = await res.json();

    metaEl.textContent = `Customer: ${customerName} • ${runs.length} agent executions`;

    contentEl.innerHTML = runs.map((run, i) => {
      const stepsHtml = (run.steps || []).map(s => `
        <div class="step-row">
          <span class="step-bullet">›</span>
          <span>${escapeHtml(s.step || "Step")}</span>
          <span class="step-offset">${s.time_offset_ms ? s.time_offset_ms + 'ms' : ''}</span>
        </div>
      `).join("");

      return `
        <div class="agent-exec-card">
          <div class="exec-header">
            <div>
              <span class="mono-text" style="font-size: 11px; color: var(--text-muted);">${run.id}</span>
              <div style="font-size: 14px; font-weight: 600; color: #ffffff;">Stage 0${i+1}: ${escapeHtml(run.agent_name)}</div>
            </div>
            <span class="chip chip-${run.status}">${run.status}</span>
          </div>

          <div class="exec-metrics-bar">
            <span>Tokens: ${run.input_tokens} in / ${run.output_tokens} out</span>
            <span>•</span>
            <span>Cost: $${(run.cost_usd || 0).toFixed(6)}</span>
            <span>•</span>
            <span>Latency: ${run.latency_ms}ms</span>
          </div>

          <div style="font-size: 13px; color: var(--text-primary); background: var(--bg-card); padding: 10px 12px; border-radius: 6px; border: 1px solid var(--border-subtle);">
            ${escapeHtml(run.output_text)}
          </div>

          <div class="exec-steps">${stepsHtml}</div>
        </div>
      `;
    }).join("");

  } catch (err) {
    contentEl.innerHTML = `<div style="color: var(--danger); padding: 20px;">Could not load trace details.</div>`;
  }
}

// ==============================================================================
// 8. Synapse Monitoring & Governance
// ==============================================================================
async function loadSynapseApprovals() {
  const container = document.getElementById("synapse-approvals-queue");
  if (!container) return;

  try {
    const res = await fetch("/api/approvals");
    if (!res.ok) throw new Error("Could not fetch approvals");
    const waitingRuns = await res.json();

    if (waitingRuns.length === 0) {
      container.innerHTML = `
        <div class="empty-placeholder" style="padding: 32px 16px;">
          <div class="text-success" style="font-size: 24px; margin-bottom: 6px;">✓</div>
          <div class="empty-title">Queue Clear</div>
          <div class="empty-desc">All customer operations satisfied automated thresholds. No actions pending approval.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = waitingRuns.map(run => `
      <div class="approval-row" id="approval-card-${run.id}">
        <div class="approval-meta">
          <div class="approval-title">${escapeHtml(run.agent_name)} Escalation: ${run.id}</div>
          <div class="approval-subtext">${escapeHtml(run.output_text)}</div>
          <div class="mono-text" style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
            Conversation: ${run.conversation_id} • Latency: ${run.latency_ms}ms • Tokens: ${run.input_tokens + run.output_tokens}
          </div>
        </div>
        <div class="approval-actions">
          <button class="btn-approve" onclick="handleApprovalDecision('${run.id}', 'APPROVED')">
            ✓ Approve Request
          </button>
          <button class="btn-reject" onclick="handleApprovalDecision('${run.id}', 'REJECTED')">
            ✕ Reject
          </button>
        </div>
      </div>
    `).join("");

  } catch (err) {
    console.error("Synapse approvals error:", err);
  }
}

async function handleApprovalDecision(runId, decision) {
  try {
    const res = await fetch(`/api/v1/runs/${runId}/approval`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision: decision, note: `Human operator decision: ${decision}` })
    });
    if (res.ok) {
      loadSynapseApprovals();
      loadOverviewAnalytics();
    }
  } catch (err) {
    alert("Approval submission error: " + err);
  }
}

async function checkKillSwitchStatus() {
  try {
    const res = await fetch("/api/killswitch");
    if (!res.ok) return;
    const data = await res.json();
    killSwitchActive = data.active;
    updateKillSwitchUI();
  } catch (e) {}
}

function updateKillSwitchUI() {
  const sidebarLabel = document.getElementById("sidebar-killswitch-status");
  const cardLabel = document.getElementById("killswitch-status-label");
  const btn = document.getElementById("btn-toggle-killswitch");

  if (sidebarLabel) {
    sidebarLabel.textContent = killSwitchActive ? "Kill Switch: HALTED" : "Kill Switch: Normal";
    sidebarLabel.style.color = killSwitchActive ? "var(--danger)" : "var(--text-muted)";
  }

  if (cardLabel) {
    cardLabel.textContent = killSwitchActive ? "Status: ENGAGED (ALL AGENTS HALTED)" : "Status: Inactive (Normal Operation)";
    cardLabel.style.color = killSwitchActive ? "var(--danger)" : "var(--text-secondary)";
  }

  if (btn) {
    btn.innerHTML = killSwitchActive 
      ? "<span>🟢 Disengage Kill Switch (Resume Normal Operations)</span>" 
      : "<span>🚨 Engage Emergency Kill Switch</span>";
    btn.className = killSwitchActive ? "btn-primary" : "btn-danger-outline";
  }
}

function initSynapseMonitoring() {
  const killSwitchBtn = document.getElementById("btn-toggle-killswitch");
  if (killSwitchBtn) {
    killSwitchBtn.addEventListener("click", async () => {
      const nextState = !killSwitchActive;
      try {
        const res = await fetch("/api/killswitch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ active: nextState })
        });
        if (res.ok) {
          const data = await res.json();
          killSwitchActive = data.active;
          updateKillSwitchUI();
        }
      } catch (err) {
        alert("Failed to toggle kill switch: " + err);
      }
    });
  }
}

// ==============================================================================
// 9. Settings View
// ==============================================================================
async function loadSettingsView() {
  try {
    const res = await fetch("/api/settings");
    if (res.ok) {
      const cfg = await res.json();
      const refEl = document.getElementById("setting-refund-limit");
      if (refEl && cfg.refund_approval_limit != null) refEl.value = cfg.refund_approval_limit;
      const discEl = document.getElementById("setting-discount-limit");
      if (discEl && cfg.discount_approval_limit_percent != null) discEl.value = cfg.discount_approval_limit_percent;
      const modelEl = document.getElementById("setting-gemini-model");
      if (modelEl && cfg.gemini_model) modelEl.value = cfg.gemini_model;
      const urlEl = document.getElementById("setting-synapse-url");
      if (urlEl && cfg.synapse_url) urlEl.value = cfg.synapse_url;
    }
  } catch (err) {
    console.error("Settings load error:", err);
  }

  try {
    // Load Products Inventory Preview
    const prodRes = await fetch("/api/products");
    if (prodRes.ok) {
      const products = await prodRes.json();
      const countEl = document.getElementById("settings-products-count");
      if (countEl) countEl.textContent = `${products.length} products`;
      
      const prodGrid = document.getElementById("catalog-preview-items");
      if (prodGrid) {
        prodGrid.innerHTML = products.map(p => `
          <div class="catalog-item-chip">
            <span style="font-weight: 500;">${escapeHtml(p.name)}</span>
            <span class="mono-text" style="color: var(--primary);">$${p.price.toFixed(2)} (Stock: ${p.stock})</span>
          </div>
        `).join("");
      }
    }
  } catch (e) {
    console.error("Catalog preview error:", e);
  }

  try {
    // Load Orders Count
    const orderRes = await fetch("/api/orders");
    if (orderRes.ok) {
      const orders = await orderRes.json();
      const orderCountEl = document.getElementById("settings-orders-count");
      if (orderCountEl) orderCountEl.textContent = `${orders.length} orders in database`;
    }
  } catch (e) {
    console.error("Orders load error:", e);
  }
}

function initSettings() {
  const form = document.getElementById("settings-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      refund_approval_limit: parseFloat(document.getElementById("setting-refund-limit").value),
      discount_approval_limit_percent: parseFloat(document.getElementById("setting-discount-limit").value),
      gemini_model: document.getElementById("setting-gemini-model").value,
      synapse_url: document.getElementById("setting-synapse-url").value
    };

    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        alert("Configuration saved successfully.");
      }
    } catch (err) {
      alert("Failed to save settings: " + err);
    }
  });
}

// Helper: Escape HTML
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
