const state = {
  view: new URLSearchParams(window.location.search).get("view") || "dashboard",
  incidentTab: "active",
  analyticsTab: "live",
};

let surveyMap = null;

const API_BASE_URL = window.IZEE_API_BASE_URL || "http://127.0.0.1:8000";

const pageTitles = {
  dashboard: "Dashboard",
  map: "Live Map",
  analytics: "Analytics",
  incidents: "Incidents",
  communications: "Communications",
  users: "Users",
  regions: "Regions",
  configuration: "Configuration",
  logs: "Logs & Reports",
};

const metrics = [
  ["Active Vehicles", "284", "+12 from yesterday", "icon-bus", "green"],
  ["Active Routes", "42", "All operational", "icon-pulse", "blue"],
  ["On-Time Performance", "87.3%", "+2.1% this week", "icon-up", "green"],
  ["Active Incidents", "7", "3 resolved today", "icon-alert", "orange"],
];

const alerts = [
  ["orange", "Route 15 - Minor delay at Nasr City station", "5 min ago", "New", "blue"],
  ["blue", "Vehicle #2487 completed maintenance inspection", "12 min ago", "Resolved", "green"],
  ["red", "Route 8 - Vehicle breakdown at Heliopolis", "18 min ago", "In Progress", "orange"],
  ["blue", "Morning rush hour completed - 94% on-time arrival", "1 hour ago", "Resolved", "green"],
];

const routes = [
  ["Route 1 - Downtown Loop", 92, "12 vehicles", "green"],
  ["Route 8 - Heliopolis Express", 74, "8 vehicles", "danger"],
  ["Route 15 - Nasr City Line", 78, "10 vehicles", "warning"],
  ["Route 22 - Airport Shuttle", 96, "6 vehicles", "green"],
  ["Route 34 - University Route", 88, "15 vehicles", "warning"],
  ["Route 42 - Industrial Zone", 91, "7 vehicles", "green"],
];

const vehicles = [
  ["#2487", "Route 1", "42 km/h", "34", "green", 30, 26],
  ["#2488", "Route 8", "15 km/h", "28", "orange", 45, 34],
  ["#2489", "Route 15", "38 km/h", "41", "green", 58, 42],
  ["#2490", "Route 22", "0 km/h", "12", "gray", 68, 52],
  ["#2491", "Route 34", "45 km/h", "39", "green", 82, 62],
];

// The live map intentionally starts empty.  It is populated only from the
// tracking endpoint; demo vehicles must never appear in operations view.
let liveVehicles = [];
let liveVehicleError = "";
let selectedLiveRoute = "all";
let selectedLiveVehicleId = null;
let selectedVehicleRouteGeometry = [];
let liveMap = null;

const incidents = [
  ["Vehicle Breakdown - Route 8", "Engine failure on vehicle #2488 at Heliopolis", "Heliopolis, Abbas El Akkad St", "Driver - Mohamed Ali", "2024-12-24 09:45", "Field Team Alpha", "In Progress", "INC-2024-001", "critical"],
  ["Traffic Congestion - Route 15", "Heavy traffic causing 12 min delay", "Nasr City, Mustafa El-Nahas St", "Driver - Ahmed Hassan", "2024-12-24 10:12", "Unassigned", "New", "INC-2024-002", "warning"],
  ["Scheduled Maintenance Alert", "Vehicle #2490 due for inspection", "Main Depot", "System Auto-Alert", "2024-12-24 07:00", "Maintenance Team", "In Progress", "INC-2024-004", "warning"],
];
let liveIncidents = incidents;
let incidentFilterStatus = "active";
let incidentFilterSource = "all";
let supervisorServiceChecks = [];
let incidentError = "";
let controlMessages = [];
let messageError = "";
let messageDraft = {
  recipientId: "all",
  subject: "",
  body: "",
};
let messageAudienceTab = "drivers";
let messagingStats = { messages_sent_today: 0, active_recipients: 0, active_drivers: 0, active_supervisors: 0, broadcast_messages_today: 0 };

function html(strings, ...values) {
  return strings.reduce((out, str, i) => out + str + (values[i] ?? ""), "");
}

function badge(text, tone = "green") {
  return `<span class="badge ${tone}">${text}</span>`;
}

function icon(name) {
  return `<span class="icon ${name}" aria-hidden="true"></span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function metricCard([label, value, hint, icon, tone]) {
  return html`
    <article class="card metric-card">
      <div>
        <div class="label">${label}</div>
        <div class="value">${value}</div>
        <div class="hint">${hint}</div>
      </div>
      <div class="metric-icon ${tone}">${icon.startsWith("icon-") ? window.icon(icon) : icon}</div>
    </article>
  `;
}

function normalize(value, min, max) {
  if (!Number.isFinite(value) || min === max) return 50;
  return Math.min(92, Math.max(8, ((value - min) / (max - min)) * 100));
}

function statusTone(status) {
  if (status === "stale") return "orange";
  if (status === "stopped") return "gray";
  return "green";
}

function dashboardMetrics() {
  return metrics.map((metric) => {
    if (metric[0] === "Active Vehicles") {
      return [metric[0], String(liveVehicles.length), liveVehicleError || "From live vehicle endpoint", metric[3], metric[4]];
    }
    return metric;
  });
}

function getJson(url) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("GET", url, true);
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`HTTP ${request.status}`));
        return;
      }
      try {
        resolve(JSON.parse(request.responseText));
      } catch (error) {
        reject(error);
      }
    };
    request.onerror = () => reject(new Error("Network request failed"));
    request.send();
  });
}

async function loadLiveVehicles() {
  try {
    const data = await getJson(`${API_BASE_URL}/vehicles/live?limit=100&_=${Date.now()}`);
    const rows = Array.isArray(data.vehicles) ? data.vehicles : [];
    liveVehicleError = rows.length ? "" : "No active vehicles yet";
    liveVehicles = rows
      .filter((vehicle) => vehicle.status !== "stale" && vehicle.status !== "unavailable")
      .filter((vehicle) => vehicle.route_id && Number.isFinite(Number(vehicle.lat)) && Number.isFinite(Number(vehicle.lon)))
      .map((vehicle) => ({
        id: vehicle.vehicle_id || "Unknown",
        routeId: String(vehicle.route_id),
        route: vehicle.route_name || vehicle.route_label || vehicle.route_id,
        speed: `${Math.round(vehicle.speed_kmh || 0)} km/h`,
        pax: "-",
        tone: statusTone(vehicle.status),
        x: normalize(Number(vehicle.lon), 31.20, 31.45),
        y: normalize(Number(vehicle.lat), 30.18, 29.95),
        source: vehicle.source || "backend",
        area: vehicle.area || `${vehicle.lat}, ${vehicle.lon}`,
        updated: vehicle.timestamp || "",
        lat: Number(vehicle.lat),
        lon: Number(vehicle.lon),
      }));
    if (selectedLiveVehicleId && !liveVehicles.some(vehicle => vehicle.id === selectedLiveVehicleId)) {
      selectedLiveVehicleId = null;
      selectedVehicleRouteGeometry = [];
    }
  } catch (error) {
    liveVehicleError = `Cannot reach backend at ${API_BASE_URL}`;
  }
  if (state.view === "dashboard" || state.view === "map") render();
}

async function loadIncidents() {
  try {
    const data = await getJson(`${API_BASE_URL}/incidents?scope=control_center&limit=100&_=${Date.now()}`);
    const rows = Array.isArray(data.incidents) ? data.incidents : [];
    incidentError = rows.length ? "" : "No incidents stored yet";
    if (rows.length) {
      liveIncidents = rows.map((incident) => {
        const status = incident.status === "new" ? "New" : incident.status || "In Progress";
        const level = incident.severity === "critical" ? "critical" : "warning";
        const isServiceCheck = incident.raw_payload?.report_type === "service_check" || incident.category === "Service Check";
        const title = isServiceCheck
          ? `Service Check - ${incident.vehicle_id || "Vehicle"}`
          : `${incident.category} - ${incident.vehicle_id || "Vehicle"}`;
        const place = incident.location_label || [incident.lat, incident.lon].filter(Boolean).join(", ") || "Unknown location";
        
        let reporter = "Unknown";
        if (incident.source === "passenger_app") {
          reporter = `Passenger`;
        } else if (incident.source === "supervisor_app") {
          reporter = `Supervisor`;
        } else if (incident.source === "driver_app") {
          reporter = `Driver - ${incident.vehicle_id || "Unknown"}`;
        } else {
          reporter = incident.source || "Driver";
        }

        return [
          title,
          incident.details || "Driver submitted incident report",
          place,
          reporter,
          incident.created_at || "",
          incident.transmitted_to_control ? "Received by Control Center" : "Control Center",
          status,
          incident.incident_id || "",
          level,
          incident.source,
        ];
      });
    }
  } catch (error) {
    incidentError = `Cannot reach incidents API at ${API_BASE_URL}`;
  }
  if (state.view === "incidents" || state.view === "dashboard") render();
}

async function loadServiceChecks() {
  try {
    const data = await getJson(`${API_BASE_URL}/service-checks?_=${Date.now()}`);
    if (data && Array.isArray(data.service_checks)) {
      supervisorServiceChecks = data.service_checks;
    }
  } catch (error) {
    console.error("Failed to load service checks:", error);
  }
}

async function loadControlMessages() {
  try {
    const data = await getJson(`${API_BASE_URL}/messages?limit=1000&_=${Date.now()}`);
    const rows = Array.isArray(data.messages) ? data.messages : [];
    messageError = rows.length ? "" : "No messages sent yet";
    controlMessages = rows;
  } catch (error) {
    messageError = `Cannot reach messages API at ${API_BASE_URL}`;
  }
  if (state.view === "communications") render();
}

async function loadMessagingStats() {
  try {
    messagingStats = await getJson(`${API_BASE_URL}/control-center/messaging/stats?_=${Date.now()}`);
  } catch (_) {
    // Keep the last successful value; presence is not inferred from database users.
  }
  if (state.view === "users") {
    // The per-user status comes from the same socket registry. Reload the
    // directory whenever stats change so its rows match Active Now immediately.
    await loadCcUsers();
    render();
  } else if (state.view === "communications") {
    render();
  }
}

async function sendControlMessage(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const recipientId = form.elements.recipient_id.value;
  const subject = form.elements.subject ? form.elements.subject.value.trim() : "";
  const body = form.elements.body.value.trim();
  if ((!subject && messageAudienceTab !== "supervisors") || !body || (messageAudienceTab === "supervisors" && !recipientId)) return;

  const isSupervisor = messageAudienceTab === "supervisors";
  const isDriverBroadcast = !isSupervisor && recipientId === "all";

  try {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/messages`, true);
    request.setRequestHeader("Content-Type", "application/json");
    await new Promise((resolve, reject) => {
      request.onload = () => request.status >= 200 && request.status < 300 ? resolve() : reject(new Error(`HTTP ${request.status}`));
      request.onerror = () => reject(new Error("Network request failed"));
      request.send(JSON.stringify({
        recipient_type: isSupervisor ? "supervisor" : (isDriverBroadcast ? "all_drivers" : "driver"),
        recipient_id: isDriverBroadcast ? null : recipientId,
        sender: "Control Center",
        subject: isSupervisor ? "" : subject,
        body,
        priority: subject.toLowerCase().includes("urgent") ? "urgent" : "normal",
        source: "control_center",
      }));
    });
    form.reset();
    messageDraft = { recipientId: "all", subject: "", body: "" };
    // Refresh both data sources so the counters immediately reflect the send
    // and the current number of available recipients.
    await Promise.all([loadControlMessages(), loadCcUsers(), loadMessagingStats()]);
    if (state.view === "communications") render();
  } catch (error) {
    messageError = `Could not send message: ${error.message}`;
    render();
  }
}

window.setMessageAudienceTab = (tab) => {
  syncMessageDraft();
  messageAudienceTab = tab;
  messageDraft.recipientId = tab === "drivers" ? "all" : "";
  render();
};

function syncMessageDraft() {
  const form = document.querySelector("#message-form");
  if (!form) return;

  messageDraft = {
    recipientId: form.elements.recipient_id?.value || "",
    subject: form.elements.subject?.value || "",
    body: form.elements.body?.value || "",
  };
}

function renderDashboard() {
  return html`
    <div class="grid kpi-grid">${dashboardMetrics().map(metricCard).join("")}</div>
    <div class="grid two-col" style="margin-top:24px">
      <section class="card">
        <h3 class="card-title">Live Alerts & Incidents</h3>
        <div class="alert-list">
          ${alerts.map(([dot, title, time, status, tone]) => html`
            <div class="alert-row">
              <div><span class="dot ${dot}"></span><strong>${title}</strong></div>
              <div class="meta">${time} &nbsp; ${badge(status, tone)}</div>
            </div>
          `).join("")}
        </div>
      </section>
      <section class="card">
        <h3 class="card-title">Service Health Indicators</h3>
        <div class="health-list">
          ${routes.map(([name, value, count, tone]) => html`
            <div class="health-row">
              <div><span class="dot ${tone === "danger" ? "red" : tone === "warning" ? "orange" : ""}"></span><strong>${name}</strong></div>
              <div class="bar"><span class="${tone}" style="width:${value}%"></span></div>
              <div class="meta">${count}<br>${value}%</div>
            </div>
          `).join("")}
        </div>
      </section>
    </div>
    <div class="grid three-col" style="margin-top:24px">
      ${[
        ["Routes Normal", "39", "92.8% of all routes", "green"],
        ["Routes Delayed", "3", "Avg delay: 8 minutes", "orange"],
        ["Routes Disrupted", "0", "No disruptions", "red"],
      ].map(([label, value, hint, tone]) => html`
        <article class="card stat-card">
          <div class="meta"><span class="dot ${tone === "orange" ? "orange" : tone === "red" ? "red" : ""}"></span>${label}</div>
          <div class="value">${value}</div>
          <div class="meta">${hint}</div>
        </article>
      `).join("")}
    </div>
  `;
}

function activeMapVehicles() {
  return selectedLiveRoute === "all"
    ? liveVehicles
    : liveVehicles.filter(vehicle => vehicle.routeId === selectedLiveRoute);
}

window.selectLiveRoute = (routeId) => {
  selectedLiveRoute = routeId;
  selectedLiveVehicleId = null;
  selectedVehicleRouteGeometry = [];
  render();
};

window.selectLiveVehicle = async (vehicleId) => {
  selectedLiveVehicleId = vehicleId;
  selectedVehicleRouteGeometry = [];
  render();
  try {
    const data = await getJson(`${API_BASE_URL}/driver/route-info?vehicle_id=${encodeURIComponent(vehicleId)}`);
    const route = data.route || data;
    const geometry = Array.isArray(route.geometry) ? route.geometry : [];
    selectedVehicleRouteGeometry = geometry
      .map(point => [Number(point.lat), Number(point.lon)])
      .filter(([lat, lon]) => Number.isFinite(lat) && Number.isFinite(lon));
  } catch (error) {
    console.warn("Route geometry unavailable for selected vehicle", error);
  }
  if (selectedLiveVehicleId === vehicleId && state.view === "map") render();
};

function renderMap() {
  const mapVehicles = activeMapVehicles();
  const routeOptions = [...new Map(liveVehicles.map(vehicle => [vehicle.routeId, vehicle.route])).entries()];
  const selectedVehicle = liveVehicles.find(vehicle => vehicle.id === selectedLiveVehicleId);
  return html`
    <div class="toolbar">
      <div class="filters">
        <button class="btn ${selectedLiveRoute === "all" ? "primary" : ""}" onclick="selectLiveRoute('all')">All Routes (${liveVehicles.length})</button>
        ${routeOptions.map(([routeId, routeName]) => `<button class="btn ${selectedLiveRoute === routeId ? "primary" : ""}" onclick="selectLiveRoute('${escapeHtml(routeId)}')">${escapeHtml(routeName)} (${liveVehicles.filter(vehicle => vehicle.routeId === routeId).length})</button>`).join("")}
      </div>
      <div class="actions">
        <label class="meta"><input type="checkbox" checked disabled> Auto-refresh</label>
        <button class="btn primary" onclick="loadLiveVehicles()">Refresh Now</button>
      </div>
    </div>
    <div class="map-layout">
      <section class="map-canvas" aria-label="Vehicle map preview">
        <div id="live-map" class="leaflet-live-map"></div>
        ${selectedVehicle ? `<div class="map-selection"><strong>${escapeHtml(selectedVehicle.id)}</strong><span>${escapeHtml(selectedVehicle.route)}</span><button aria-label="Clear selected vehicle" onclick="selectLiveRoute('${escapeHtml(selectedLiveRoute)}')">×</button></div>` : '<div class="map-selection map-selection-muted">Select a vehicle to show it and its route on the map.</div>'}
      </section>
      <section class="card">
        <h3 class="card-title">${selectedLiveRoute === "all" ? "Active Vehicles" : `Active Vehicles — ${escapeHtml(routeOptions.find(([id]) => id === selectedLiveRoute)?.[1] || selectedLiveRoute)}`}</h3>
        ${liveVehicleError ? `<p class="meta">${liveVehicleError}</p>` : ""}
        <div class="vehicle-list">
          ${mapVehicles.length === 0 ? '<p class="meta">No active vehicles for this route.</p>' : mapVehicles.map((vehicle) => html`
            <button class="vehicle-row vehicle-select ${vehicle.id === selectedLiveVehicleId ? "is-selected" : ""}" type="button" onclick="selectLiveVehicle('${escapeHtml(vehicle.id)}')">
              <div class="row-line"><strong><span class="dot ${vehicle.tone}"></span>Vehicle ${vehicle.id}</strong><span class="meta">${vehicle.route}</span></div>
              <div class="row-line"><span class="meta">Speed: ${vehicle.speed}</span><span class="meta">${vehicle.area || ""}</span></div>
            </button>
          `).join("")}
        </div>
      </section>
    </div>
  `;
}

window.switchAnalyticsTab = (tab) => {
  state.analyticsTab = tab;
  render();
};

function renderAnalytics() {
  const activeTab = state.analyticsTab || "live";
  return html`
    <div class="toolbar" style="margin-bottom: 24px; border-bottom: 1px solid var(--line); padding-bottom: 12px;">
      <div class="filters">
        <button class="btn ${activeTab === 'live' ? 'primary' : ''}" onclick="switchAnalyticsTab('live')">Live Operations</button>
        <button class="btn ${activeTab === 'survey' ? 'primary' : ''}" onclick="switchAnalyticsTab('survey')">Cairo Travel Survey Insights</button>
      </div>
    </div>
    ${activeTab === "live" ? renderLiveAnalytics() : renderSurveyAnalytics()}
  `;
}

function renderLiveAnalytics() {
  return html`
    <div class="grid two-col">
      <section class="card chart-card">
        <h3 class="card-title">On-Time Trend</h3>
        <div class="chart-box">
          <svg class="line-chart" viewBox="0 0 720 250" role="img" aria-label="On-time percentage trend">
            <g stroke="#e5e7eb">${[40,80,120,160,200].map(y => `<line x1="40" x2="690" y1="${y}" y2="${y}"/>`).join("")}</g>
            <polyline fill="none" stroke="#16a34a" stroke-width="4" points="40,72 145,64 250,84 355,58 460,68 565,52 690,46"/>
            ${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d,i) => `<text x="${40+i*108}" y="235" fill="#667085" font-size="14">${d}</text>`).join("")}
          </svg>
        </div>
      </section>
      <section class="card chart-card">
        <h3 class="card-title">Hourly Service Volume</h3>
        <div class="chart-box">
          <svg class="bar-chart" viewBox="0 0 720 250" role="img" aria-label="Service volume by hour">
            <g stroke="#e5e7eb">${[40,80,120,160,200].map(y => `<line x1="40" x2="690" y1="${y}" y2="${y}"/>`).join("")}</g>
            ${[104,105,103,104,105,104,103,104].map((h,i) => `<rect x="${60+i*78}" y="${210-h}" width="36" height="${h}" fill="#16a34a"/>`).join("")}
            ${["06:00","08:00","10:00","12:00","14:00","16:00","18:00","20:00"].map((d,i) => `<text x="${48+i*78}" y="235" fill="#667085" font-size="13">${d}</text>`).join("")}
          </svg>
        </div>
      </section>
    </div>
    <div class="grid two-col" style="margin-top:24px">
      <section class="card">
        <h3 class="card-title">Delay Distribution</h3>
        <div class="donut-wrap">
          <div class="donut"></div>
          <div class="alert-list">
            <div class="row-line"><span><span class="dot"></span>On Time</span><strong>248</strong></div>
            <div class="row-line"><span><span class="dot orange"></span>Minor Delay</span><strong>28</strong></div>
            <div class="row-line"><span><span class="dot red"></span>Major Delay</span><strong>8</strong></div>
          </div>
        </div>
      </section>
      <section class="card">
        <h3 class="card-title">Route-Level Performance</h3>
        ${performanceTable()}
      </section>
    </div>
  `;
}

function renderSurveyAnalytics() {
  const survey = window.SURVEY_DATA || {
    total_records: 0,
    mode_split: {},
    hourly_purpose: {},
    demographics: { gender: {}, age: {}, income: {} },
    hotspots: []
  };

  // 1. Calculate highlights
  let dominantMode = "N/A";
  let maxModeCount = 0;
  for (const [mode, count] of Object.entries(survey.mode_split)) {
    if (count > maxModeCount) {
      maxModeCount = count;
      dominantMode = mode;
    }
  }

  let peakHour = "N/A";
  let maxHourCount = 0;
  for (const [hour, purposes] of Object.entries(survey.hourly_purpose)) {
    const totalHourCount = Object.values(purposes).reduce((sum, val) => sum + val, 0);
    if (totalHourCount > maxHourCount) {
      maxHourCount = totalHourCount;
      peakHour = hour;
    }
  }

  let dominantPurpose = "N/A";
  let maxPurposeCount = 0;
  const purposeCounts = {};
  for (const [hour, purposes] of Object.entries(survey.hourly_purpose)) {
    for (const [purpose, count] of Object.entries(purposes)) {
      purposeCounts[purpose] = (purposeCounts[purpose] || 0) + count;
    }
  }
  for (const [purpose, count] of Object.entries(purposeCounts)) {
    if (purpose === "other" || purpose === "no_answer" || purpose === "") continue;
    if (count > maxPurposeCount) {
      maxPurposeCount = count;
      dominantPurpose = purpose;
    }
  }

  dominantMode = dominantMode.replace(/_/g, " ");
  dominantMode = dominantMode.charAt(0).toUpperCase() + dominantMode.slice(1);
  dominantPurpose = dominantPurpose.charAt(0).toUpperCase() + dominantPurpose.slice(1);

  const totalModesCount = Object.values(survey.mode_split).reduce((sum, val) => sum + val, 0) || 1;
  const sortedModes = Object.entries(survey.mode_split).sort((a, b) => b[1] - a[1]);

  const hours = Object.keys(survey.hourly_purpose).sort();
  const hourlyTotals = hours.map(h => {
    return Object.values(survey.hourly_purpose[h]).reduce((sum, val) => sum + val, 0);
  });
  const maxHourlyVolume = Math.max(...hourlyTotals, 1);

  return html`
    <div class="grid kpi-grid" style="margin-bottom:24px">
      ${[
        ["Surveyed Commuters", Number(survey.total_records).toLocaleString(), "Total Cairo respondents", "icon-users", "green"],
        ["Dominant Mode", dominantMode, `${maxModeCount.toLocaleString()} trips`, "icon-bus", "blue"],
        ["Peak Travel Hour", peakHour, `Highest hourly density`, "icon-pulse", "orange"],
        ["Primary Trip Purpose", dominantPurpose, `${maxPurposeCount.toLocaleString()} commutes`, "icon-trend", "purple"],
      ].map(metricCard).join("")}
    </div>

    <div class="grid two-col">
      <section class="card chart-card">
        <h3 class="card-title">Hourly Travel Volume</h3>
        <div class="chart-box">
          <svg class="bar-chart" viewBox="0 0 720 250" role="img" aria-label="Hourly travel volume">
            <g stroke="#e5e7eb">
              ${[40, 80, 120, 160, 200].map(y => `<line x1="40" x2="690" y1="${y}" y2="${y}"/>`).join("")}
            </g>
            ${hours.map((h, i) => {
              const count = hourlyTotals[i];
              const barHeight = (count / maxHourlyVolume) * 160;
              const x = 50 + i * 26;
              const y = 210 - barHeight;
              const labelText = i % 4 === 0 ? h : "";
              return html`
                <rect x="${x}" y="${y}" width="18" height="${barHeight}" fill="var(--blue)" rx="2">
                  <title>${h}: ${count} trips</title>
                </rect>
                ${labelText ? html`<text x="${x - 4}" y="232" fill="#667085" font-size="10">${labelText}</text>` : ""}
              `;
            }).join("")}
          </svg>
        </div>
      </section>

      <section class="card">
        <h3 class="card-title">Mode Choice Split</h3>
        <div style="display:flex; flex-direction:column; gap:16px; justify-content:center; min-height:220px; padding:10px 0;">
          ${sortedModes.slice(0, 7).map(([mode, count]) => {
            const pct = ((count / totalModesCount) * 100).toFixed(1);
            return html`
              <div class="progress-bar-container">
                <span class="mode-label">${mode.replace(/_/g, ' ')}</span>
                <div class="progress-bar-bg">
                  <div class="progress-bar-fill" style="width:${pct}%;"></div>
                </div>
                <span class="meta mode-pct">${pct}%</span>
              </div>
            `;
          }).join("")}
        </div>
      </section>
    </div>

    <div class="grid two-col" style="margin-top:24px">
      <section class="card">
        <h3 class="card-title">Cairo Travel Hotspots (Origins & Destinations)</h3>
        <p class="meta" style="margin-top:-14px; margin-bottom:14px;">
          Visualizing Cairo travel patterns. Green is Origin, Red is Destination. Hover over paths to view direction and commuter profiles.
        </p>
        <div id="survey-map" style="min-height: 400px; height: 400px; border-radius: 8px; border: 1px solid var(--line); position: relative; z-index: 10;"></div>
      </section>

      <section class="card" style="display:flex; flex-direction:column; gap:20px;">
        <h3 class="card-title" style="margin-bottom:10px;">Commuter Demographics</h3>
        
        <div>
          <h4 style="margin:0 0 10px; font-size:14px; color:var(--muted)">Gender Distribution</h4>
          ${Object.entries(survey.demographics.gender)
            .filter(([gender]) => gender !== "no_answer" && gender !== "no answer" && gender !== "")
            .map(([gender, count], _, arr) => {
              const total = arr.reduce((sum, [_, c]) => sum + c, 0) || 1;
              const pct = ((count / total) * 100).toFixed(1);
              return html`
                <div class="progress-bar-container">
                  <span class="demog-label" style="text-transform:capitalize;">${gender}</span>
                  <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${pct}%; background:var(--green-2)"></div></div>
                  <span class="meta demog-pct">${pct}%</span>
                </div>
              `;
            }).join("")}
        </div>

        <div>
          <h4 style="margin:0 0 10px; font-size:14px; color:var(--muted)">Age Demographics</h4>
          ${Object.entries(survey.demographics.age).sort().slice(0, 6).map(([age, count]) => {
            const total = Object.values(survey.demographics.age).reduce((a,b)=>a+b, 0) || 1;
            const pct = ((count / total) * 100).toFixed(1);
            return html`
              <div class="progress-bar-container">
                <span class="demog-label">${age}</span>
                <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${pct}%; background:var(--orange)"></div></div>
                <span class="meta demog-pct">${pct}%</span>
              </div>
            `;
          }).join("")}
        </div>

        <div>
          <h4 style="margin:0 0 10px; font-size:14px; color:var(--muted)">Income Distribution (EGP)</h4>
          ${Object.entries(survey.demographics.income).sort().slice(0, 6).map(([income, count]) => {
            const total = Object.values(survey.demographics.income).reduce((a,b)=>a+b, 0) || 1;
            const pct = ((count / total) * 100).toFixed(1);
            return html`
              <div class="progress-bar-container">
                <span class="demog-label">${income.replace('no_answer', 'Unknown')}</span>
                <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${pct}%; background:var(--purple)"></div></div>
                <span class="meta demog-pct">${pct}%</span>
              </div>
            `;
          }).join("")}
        </div>
      </section>
    </div>
  `;
}

function performanceTable() {
  const data = [
    ["Route 1", "145", "92%", "2.3 min", "Excellent", "green"],
    ["Route 8", "98", "74%", "8.1 min", "Needs Attention", "red"],
    ["Route 15", "112", "78%", "6.5 min", "Good", "orange"],
    ["Route 22", "76", "96%", "1.2 min", "Excellent", "green"],
    ["Route 34", "134", "88%", "3.8 min", "Good", "orange"],
  ];
  return html`
    <table class="table">
      <thead><tr><th>Route</th><th>Trips</th><th>On-Time %</th><th>Avg Delay</th><th>Status</th></tr></thead>
      <tbody>${data.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td><td>${badge(r[4], r[5])}</td></tr>`).join("")}</tbody>
    </table>
  `;
}

window.setIncidentFilterStatus = (status) => {
  incidentFilterStatus = status;
  render();
};

window.setIncidentFilterSource = (source) => {
  incidentFilterSource = source;
  render();
};

function renderIncidents() {
  // 1. Status Filter
  let filtered = liveIncidents;
  if (incidentFilterStatus === "active") {
    filtered = filtered.filter((inc) => inc[6].toLowerCase() !== "resolved");
  } else if (incidentFilterStatus === "resolved") {
    filtered = filtered.filter((inc) => inc[6].toLowerCase() === "resolved");
  }

  // 2. Source Filter (index 9)
  if (incidentFilterSource === "passenger") {
    filtered = filtered.filter((inc) => inc[9] === "passenger_app");
  } else if (incidentFilterSource === "driver") {
    filtered = filtered.filter((inc) => inc[9] === "driver_app" || !inc[9]);
  } else if (incidentFilterSource === "supervisor") {
    filtered = filtered.filter((inc) => inc[9] === "supervisor_app");
  }

  // Count helper functions for the UI badges
  const activeCount = liveIncidents.filter((inc) => inc[6].toLowerCase() !== "resolved").length;
  const resolvedCount = liveIncidents.filter((inc) => inc[6].toLowerCase() === "resolved").length;
  const allCount = liveIncidents.length;

  const passengerCount = liveIncidents.filter((inc) => inc[9] === "passenger_app").length;
  const driverCount = liveIncidents.filter((inc) => inc[9] === "driver_app" || !inc[9]).length;
  const supervisorCount = liveIncidents.filter((inc) => inc[9] === "supervisor_app").length;

  return html`
    <div class="grid four-metrics kpi-grid">
      ${[
        ["Critical", String(filtered.filter(inc => inc[8] === "critical").length), "", "icon-alert", "red"],
        ["Warning", String(filtered.filter(inc => inc[8] === "warning").length), "", "icon-alert", "orange"],
        ["Resolved", String(liveIncidents.filter(inc => inc[6].toLowerCase() === "resolved").length), "", "OK", "green"],
        ["Filtered Count", String(filtered.length), "", "LIST", "blue"],
      ].map(metricCard).join("")}
    </div>
    <section class="card" style="margin-top:24px">
      <div class="toolbar" style="display:flex; flex-direction:column; gap:16px; align-items:start;">
        <div style="display:flex; justify-content:space-between; width:100%; align-items:center; flex-wrap:wrap; gap:12px;">
          <div class="filters" style="display:flex; gap:8px;">
            <button class="btn ${incidentFilterStatus === "active" ? "primary" : ""}" onclick="setIncidentFilterStatus('active')">Active Incidents (${activeCount})</button>
            <button class="btn ${incidentFilterStatus === "resolved" ? "primary" : ""}" onclick="setIncidentFilterStatus('resolved')">Resolved (${resolvedCount})</button>
            <button class="btn ${incidentFilterStatus === "all" ? "primary" : ""}" onclick="setIncidentFilterStatus('all')">All (${allCount})</button>
          </div>
          <button class="btn primary">Create New Incident</button>
        </div>
        
        <div class="filters" style="display:flex; gap:8px; border-top: 1px solid #f1f5f9; padding-top:12px; width:100%;">
          <span style="font-weight:600; color:#475569; align-self:center; margin-right:8px;">Source:</span>
          <button class="btn ${incidentFilterSource === "all" ? "primary" : ""}" onclick="setIncidentFilterSource('all')">All Sources</button>
          <button class="btn ${incidentFilterSource === "passenger" ? "primary" : ""}" onclick="setIncidentFilterSource('passenger')">Passenger (${passengerCount})</button>
          <button class="btn ${incidentFilterSource === "driver" ? "primary" : ""}" onclick="setIncidentFilterSource('driver')">Driver (${driverCount})</button>
          <button class="btn ${incidentFilterSource === "supervisor" ? "primary" : ""}" onclick="setIncidentFilterSource('supervisor')">Supervisor (${supervisorCount})</button>
        </div>
      </div>
      
      ${incidentError ? `<p class="meta">${incidentError}</p>` : ""}
      <div class="alert-list" style="margin-top:16px;">
        ${filtered.map(([title, desc, place, driver, time, team, status, id, level]) => html`
          <article class="incident-card ${level === "warning" ? "warning" : ""}">
            <div class="incident-title">${title} ${badge(status, status.toLowerCase() === "new" ? "blue" : (status.toLowerCase() === "resolved" ? "green" : "orange"))} <span class="meta">${id}</span></div>
            <div>${desc}</div>
            <div class="incident-meta">
              <span>Loc: ${place}</span><span>Reporter: ${driver}</span><span>${time}</span><span>${team}</span>
            </div>
            <div class="filters"><button class="btn primary">${status.toLowerCase() === "new" ? "Acknowledge" : "Mark Resolved"}</button><button class="btn">View Details</button><button class="btn">Assign</button></div>
          </article>
        `).join("")}
        ${filtered.length === 0 ? html`<div style="text-align:center; padding:32px; color:#667085; font-weight:500;">No incidents match the selected filter.</div>` : ""}
      </div>
    </section>
  `;
}

function renderCommunications() {
  const audience = messageAudienceTab === "supervisors" ? "supervisors" : "drivers";
  const people = audience === "supervisors" ? ccAllSupervisors : ccAllDrivers;
  const recipientOptions = [
    ...(audience === "drivers" ? [{ id: "all", label: "All Drivers (broadcast)" }] : []),
    ...people.map(person => ({
      id: person.driver_id,
      label: `${person.name || person.driver_id} (${person.driver_id})`,
    })),
  ];
  const visibleMessages = controlMessages.filter((message) => {
    const recipientType = String(message.recipient_type || "").toLowerCase();
    const sender = String(message.sender || "").toLowerCase();
    const isSupervisorConversation =
      message.source === "supervisor_app" ||
      recipientType === "supervisor" ||
      recipientType === "supervisors" ||
      sender.startsWith("supervisor_");
    const isDriverConversation =
      message.source === "driver_app" ||
      recipientType === "driver" ||
      recipientType === "all_drivers" ||
      recipientType.endsWith("_drivers") ||
      sender.startsWith("driver_");
    return audience === "supervisors" ? isSupervisorConversation : isDriverConversation;
  });
  // The API stores created_at in UTC. Compare UTC calendar dates so a message
  // sent shortly after Cairo midnight is still counted with the API's day.
  const utcToday = new Date().toISOString().slice(0, 10);
  const isToday = (message) => {
    const createdAt = String(message.created_at || "");
    return createdAt.slice(0, 10) === utcToday;
  };
  const isFromControlCenter = (message) =>
    message.source === "control_center" ||
    String(message.sender || "").toLowerCase() === "control center";
  const messagesSentToday = controlMessages.filter(message =>
    isFromControlCenter(message) && isToday(message)
  ).length;
  const broadcastMessagesToday = controlMessages.filter((message) => {
    const recipientType = String(message.recipient_type || "").toLowerCase();
    return isFromControlCenter(message) && isToday(message) &&
      (recipientType === "all_drivers" || recipientType.endsWith("_drivers"));
  }).length;
  const activeRecipients = Number(messagingStats.active_recipients || 0);
  return html`
    <div class="grid three-col">
      ${[
        ["Messages Sent Today", String(messagingStats.messages_sent_today || 0), "From Control Center", "icon-message", "green"],
        ["Active Recipients", String(activeRecipients), `${messagingStats.active_drivers || 0} drivers · ${messagingStats.active_supervisors || 0} supervisors`, "icon-users", "blue"],
        ["Broadcast Messages", String(messagingStats.broadcast_messages_today || 0), "Driver broadcasts sent today", "ALL", "orange"],
      ].map(metricCard).join("")}
    </div>
    <div class="grid two-col" style="margin-top:24px">
      <section class="card">
        <h3 class="card-title">Send New Message</h3>
        <form class="form-grid" id="message-form">
          <div class="field span-2">
            <label>Recipients</label>
            <div class="filters" style="margin-bottom:8px">
              <button class="btn ${audience === "drivers" ? "primary" : ""}" type="button" onclick="setMessageAudienceTab('drivers')">Drivers</button>
              <button class="btn ${audience === "supervisors" ? "primary" : ""}" type="button" onclick="setMessageAudienceTab('supervisors')">Supervisors</button>
            </div>
            <select name="recipient_id" required>
              ${audience === "supervisors" ? '<option value="">Choose a supervisor…</option>' : ''}
              ${recipientOptions.map(person => `<option value="${escapeHtml(person.id)}" ${messageDraft.recipientId === String(person.id) ? "selected" : ""}>${escapeHtml(person.label)}</option>`).join("")}
            </select>
            <p class="meta" style="margin-top:6px">${audience === "supervisors" ? "Messages are private to the selected supervisor." : "Choose one driver for a private message, or send a driver broadcast."}</p>
          </div>
          ${audience === "drivers" ? html`<div class="field span-2"><label>Subject</label><input name="subject" value="${escapeHtml(messageDraft.subject)}" placeholder="Enter subject"></div>` : ""}
          <div class="field span-2"><label>Message</label><textarea name="body" placeholder="Type your message here...">${escapeHtml(messageDraft.body)}</textarea></div>
          <div class="filters span-2"><button class="btn primary" type="submit">Send Message</button><button class="btn" type="button">Save Draft</button></div>
        </form>
      </section>
      <section class="card">
        <h3 class="card-title">${audience === "supervisors" ? "Supervisor Conversations" : "Driver Conversations"}</h3>
        ${messageError ? `<p class="meta">${messageError}</p>` : ""}
        <div class="message-list">
          ${visibleMessages.length === 0
            ? `<p class="meta">No ${audience} messages yet.</p>`
            : visibleMessages.map((message) => {
              const fromSupervisor = message.source === "supervisor_app";
              const fromDriver = message.source === "driver_app";
              const title = message.subject || (fromSupervisor ? "Supervisor Message" : fromDriver ? "Driver Message" : "Control Center Message");
              const direction = (fromSupervisor || fromDriver)
                ? `From: ${message.sender || "Unknown"}`
                : `To: ${message.recipient_id || message.recipient_type || "Unknown"}`;
              return html`<div class="message-row"><div class="row-line"><strong>${escapeHtml(title)}</strong><span class="meta">${escapeHtml(message.created_at || "")}</span></div><span class="meta">${escapeHtml(direction)}</span><p>${escapeHtml(message.body || "")}</p>${badge(message.read ? "Read" : "Delivered")}</div>`;
            }).join("")}
        </div>
      </section>
    </div>
  `;
}

let ccUsers = [];
let ccUsersError = "";
let userSearch = "";

window.setUserSearch = (input) => {
  const value = input.value;
  const cursor = input.selectionStart ?? value.length;
  userSearch = value.toLowerCase();
  render();
  requestAnimationFrame(() => {
    const replacement = document.getElementById("users-search");
    if (!replacement) return;
    replacement.focus();
    replacement.setSelectionRange(cursor, cursor);
  });
};
window.addControlCenterUser = async () => {
  const user_id = prompt("User ID (for example: driver_101)")?.trim();
  if (!user_id) return;
  const name = prompt("Full name")?.trim();
  const role = prompt("Role: Driver, Supervisor, or Operator", "Driver")?.trim();
  if (!name || !role) return;
  try { await postJson(`${API_BASE_URL}/control-center/users`, { user_id, name, role }); await loadCcUsers(); render(); }
  catch (error) { alert(`Could not add user: ${error.message}`); }
};
window.editControlCenterUser = async (userId, name, role) => {
  const nextName = prompt("Full name", name)?.trim();
  const nextRole = prompt("Role: Driver, Supervisor, or Operator", role)?.trim();
  if (!nextName || !nextRole) return;
  try { await putJson(`${API_BASE_URL}/control-center/users/${encodeURIComponent(userId)}`, { user_id: userId, name: nextName, role: nextRole }); await loadCcUsers(); render(); }
  catch (error) { alert(`Could not update user: ${error.message}`); }
};
window.toggleUserSuspension = async (userId, currentlySuspended) => {
  const suspending = !currentlySuspended;
  if (!confirm(suspending ? "Suspend this user? They will no longer be able to send or receive Control Center messages." : "Reactivate this user?")) return;
  try { await postJson(`${API_BASE_URL}/control-center/users/${encodeURIComponent(userId)}/suspend`, { suspended: suspending }); await Promise.all([loadCcUsers(), loadMessagingStats()]); render(); }
  catch (error) { alert(`Could not update user status: ${error.message}`); }
};
window.viewUserAssignment = (name, assignment) => alert(`${name}\nCurrent assignment: ${assignment || "None"}\n\nAssignment creation and editing remain managed by the Supervisor.`);
let assignModalOpen = false;
let assignDriverId = "";
let assignDriverName = "";
let assignRouteId = "A-12 Express";
let assignTripId = "";
let assignVehicleId = "";
let assignServiceDate = new Date().toISOString().split("T")[0];
let assignStartTime = "08:15 AM";
let assignEndTime = "09:30 AM";

window.openAssignModal = (driverId, driverName) => {
  assignDriverId = driverId;
  assignDriverName = driverName;
  assignVehicleId = driverId;
  assignModalOpen = true;

  const validRoutes = (ccBusRoutes || []).filter(r => (r.mode || "").toLowerCase() === "bus");
  if (validRoutes.length > 0) {
    assignRouteId = validRoutes[0].route_id;
  } else {
    assignRouteId = "Route 8";
  }

  render();
};

window.closeAssignModal = () => {
  assignModalOpen = false;
  render();
};

window.submitAssignment = async (event) => {
  event.preventDefault();
  try {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/drivers/${assignDriverId}/assignments`, true);
    request.setRequestHeader("Content-Type", "application/json");
    await new Promise((resolve, reject) => {
      request.onload = () => request.status >= 200 && request.status < 300 ? resolve() : reject(new Error(`HTTP ${request.status}`));
      request.onerror = () => reject(new Error("Network request failed"));
      request.send(JSON.stringify({
        route_id: assignRouteId,
        route_name: assignRouteId,
        trip_id: assignTripId || null,
        vehicle_id: assignVehicleId || null,
        service_date: assignServiceDate,
        start_time: assignStartTime,
        end_time: assignEndTime,
        assigned_by: "Control Center"
      }));
    });
    assignModalOpen = false;
    await loadCcUsers();
    render();
  } catch (error) {
    alert(`Failed to save assignment: ${error.message}`);
  }
};

async function loadCcUsers() {
  try {
    const data = await getJson(`${API_BASE_URL}/control-center/drivers?_=${Date.now()}`);
    if (data && Array.isArray(data.users)) {
      // Communications uses the same user directory as the Users page. Keep
      // these recipient lists current here as well, rather than only when the
      // Regions screen happens to load its metadata.
      ccAllSupervisors = data.users.filter(u => u.role === "Supervisor");
      ccAllDrivers = data.users.filter(u => u.role === "Driver");
      ccUsers = data.users.map(u => [
        u.name,
        u.role,
        u.assignment,
        u.status,
        u.last_active,
        u.driver_id
      ]);
      ccUsersError = "";
    }
  } catch (error) {
    ccUsersError = `Cannot load users from backend: ${error.message}`;
  }
}

function renderAssignModal() {
  if (!assignModalOpen) return "";
  return html`
    <div class="modal-overlay" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;">
      <div class="modal-card card" style="width:100%;max-width:500px;background:white;padding:24px;border-radius:8px;box-shadow:0 8px 30px rgba(0,0,0,0.12);box-sizing:border-box;">
        <h3 class="card-title" style="margin-top:0;margin-bottom:20px;font-size:18px;font-weight:700;">Assign Route to ${escapeHtml(assignDriverName)}</h3>
        <form id="assign-form" onsubmit="submitAssignment(event)" class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
          <div class="field span-2" style="grid-column: span 2; display:flex;flex-direction:column;gap:6px;">
            <label style="font-weight:600;font-size:13px;color:#344054;">Select Route</label>
            <select name="route_id" onchange="assignRouteId = this.value" style="padding:10px;border:1px solid #d0d5dd;border-radius:6px;outline:none;font-size:14px;">
              ${(ccBusRoutes || [])
                .filter(r => (r.mode || "").toLowerCase() === "bus")
                .map(r => html`
                  <option value="${escapeHtml(r.route_id)}" ${assignRouteId === r.route_id ? "selected" : ""}>
                    ${escapeHtml(r.route_long_name || r.route_short_name || r.route_id)}
                  </option>
                `).join("")}
              ${(ccBusRoutes || []).filter(r => (r.mode || "").toLowerCase() === "bus").length === 0 ? html`
                <option value="Route 8" ${assignRouteId === "Route 8" ? "selected" : ""}>Route 8</option>
                <option value="Route 15" ${assignRouteId === "Route 15" ? "selected" : ""}>Route 15</option>
              ` : ""}
            </select>
          </div>
          <div class="field" style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-weight:600;font-size:13px;color:#344054;">Trip ID (Optional)</label>
            <input name="trip_id" value="${escapeHtml(assignTripId)}" placeholder="e.g. T-900" oninput="assignTripId = this.value" style="padding:10px;border:1px solid #d0d5dd;border-radius:6px;outline:none;font-size:14px;">
          </div>
          <div class="field" style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-weight:600;font-size:13px;color:#344054;">Vehicle ID (Optional)</label>
            <input name="vehicle_id" value="${escapeHtml(assignVehicleId)}" placeholder="e.g. bus_001" oninput="assignVehicleId = this.value" style="padding:10px;border:1px solid #d0d5dd;border-radius:6px;outline:none;font-size:14px;">
          </div>
          <div class="field" style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-weight:600;font-size:13px;color:#344054;">Service Date</label>
            <input type="date" name="service_date" value="${assignServiceDate}" onchange="assignServiceDate = this.value" style="padding:10px;border:1px solid #d0d5dd;border-radius:6px;outline:none;font-size:14px;">
          </div>
          <div class="field" style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-weight:600;font-size:13px;color:#344054;">Start Time</label>
            <input name="start_time" value="${escapeHtml(assignStartTime)}" placeholder="e.g. 08:15 AM" oninput="assignStartTime = this.value" style="padding:10px;border:1px solid #d0d5dd;border-radius:6px;outline:none;font-size:14px;">
          </div>
          <div class="field span-2" style="grid-column: span 2; display:flex;flex-direction:column;gap:6px;">
            <label style="font-weight:600;font-size:13px;color:#344054;">End Time</label>
            <input name="end_time" value="${escapeHtml(assignEndTime)}" placeholder="e.g. 09:30 AM" oninput="assignEndTime = this.value" style="padding:10px;border:1px solid #d0d5dd;border-radius:6px;outline:none;font-size:14px;">
          </div>
          <div class="filters span-2" style="grid-column: span 2; margin-top:16px;display:flex;justify-content:flex-end;gap:12px;">
            <button class="btn" type="button" onclick="closeAssignModal()" style="padding:10px 16px;border:1px solid #d0d5dd;border-radius:6px;background:white;cursor:pointer;font-weight:600;">Cancel</button>
            <button class="btn primary" type="submit" style="padding:10px 16px;border:none;border-radius:6px;background:#16a34a;color:white;cursor:pointer;font-weight:600;">Save Assignment</button>
          </div>
        </form>
      </div>
    </div>
  `;
}


function renderUsers() {
  const displayUsers = ccUsers.length ? ccUsers : [
    ["Mohamed Ali", "Driver", "Route 8", "active", "5 min ago", "driver_test_001"],
    ["Ahmed Hassan", "Driver", "Route 15", "active", "2 min ago", "driver_test_002"],
    ["Fatima Said", "Supervisor", "Zone A", "active", "1 hour ago", "supervisor_1"],
    ["Omar Ibrahim", "Driver", "Route 22", "inactive", "2 days ago", "driver_test_003"],
    ["Sara Mahmoud", "Operator", "Control Center", "active", "Now", "operator_1"],
  ];
  const filteredUsers = displayUsers.filter(([name, role, assignment, status, last, id]) =>
    !userSearch || `${name} ${role} ${assignment} ${status} ${id}`.toLowerCase().includes(userSearch));
  const totalUsers = displayUsers.length;
  // Use the exact same WebSocket-presence total as Communications.
  // Do not infer activity from stored database user statuses.
  const activeUsers = Number(messagingStats.active_recipients || 0);
  const lastActiveLabel = (value) => {
    if (!value || value === "Never" || value === "Now") return value || "Never";
    const time = new Date(value);
    if (Number.isNaN(time.valueOf())) return value;
    const seconds = Math.max(0, Math.floor((Date.now() - time.valueOf()) / 1000));
    if (seconds < 60) return "Just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
    return `${Math.floor(seconds / 86400)} days ago`;
  };
  return html`
    <div class="grid three-col">
      ${[
        ["Total Users", String(totalUsers), "Current directory", "icon-users", "green"],
        ["Active Now", String(activeUsers), "Matches messaging Active Recipients", "ON", "blue"],
        ["New This Week", "—", "Not tracked", "+", "orange"],
      ].map(metricCard).join("")}
    </div>
    <section class="card" style="margin-top:24px">
      ${ccUsersError ? `<p style="color:#C5221F;font-weight:600;margin-bottom:12px;">${ccUsersError}</p>` : ""}
      <div class="search-row"><input id="users-search" value="${escapeHtml(userSearch)}" oninput="setUserSearch(this)" placeholder="Search users..."><button class="btn primary" onclick="addControlCenterUser()">Add New User</button></div>
      <table class="table">
        <thead><tr><th>Name</th><th>Role</th><th>Assignment</th><th>Status</th><th>Last Active</th><th>Actions</th></tr></thead>
        <tbody>${filteredUsers.map(([name, role, assignment, status, last, driver_id]) => html`
          <tr>
            <td><span class="avatar" style="display:inline-grid;width:32px;height:32px;margin-right:10px;align-items:center;justify-content:center;border-radius:50%;background:#e2e8f0;font-weight:bold;font-size:12px;color:#475569;">${name.split(" ").map(n => n[0]).join("")}</span>${name}</td>
            <td>${role}</td>
            <td>${assignment}</td>
            <td>${badge(status, status === "online" || status === "active" ? "green" : status === "suspended" ? "red" : "gray")}</td>
            <td class="meta">${lastActiveLabel(last)}</td>
            <td>
              ${role === "Driver" ? html`<button class="btn" onclick="viewUserAssignment('${escapeHtml(name)}','${escapeHtml(assignment)}')">View Assignment</button>` : ""}
              <button class="btn" onclick="editControlCenterUser('${escapeHtml(driver_id)}','${escapeHtml(name)}','${escapeHtml(role)}')">Edit</button>
              <button class="btn" onclick="toggleUserSuspension('${escapeHtml(driver_id)}', ${status === "suspended"})">${status === "suspended" ? "Reactivate" : "Suspend"}</button>
            </td>
          </tr>
        `).join("")}</tbody>
      </table>
    </section>
  `;
}

// --- Region Management State & Helpers ---
let ccRegions = [];
let ccRegionsError = "";
let ccAllRoutes = [];
let ccBusRoutes = [];
let ccAllVehicles = [];
let ccAllSupervisors = [];
let ccAllDrivers = [];
let activeRegionSummary = {};
let selectedRegion = null;
let showRegionModal = null; // "create", "edit"
let showMappingModal = null; // "routes", "routes-add", "drivers", "drivers-add", "supervisors", "vehicles"
let currentMappings = [];

function routeKey(route) {
  return String(route?.route_id ?? route?.id ?? "");
}

function routeDisplayName(route) {
  const id = routeKey(route);
  const shortName = route?.route_short_name || route?.route_name || id;
  const longName = route?.route_long_name || route?.description || "";
  return longName ? `${shortName} - ${longName}` : shortName;
}

function routeMode(route) {
  return route?.mode || route?.route_type || "Bus";
}

function routeCheckboxId(prefix, routeId, index) {
  return `${prefix}-${index}-${String(routeId).replace(/[^a-zA-Z0-9_-]/g, "_")}`;
}

function normalizedBusRouteOptions() {
  return ccBusRoutes.map((route) => ({
    route,
    id: routeKey(route),
    label: routeDisplayName(route),
    mode: routeMode(route),
  })).filter((route) => {
    const searchable = `${route.id} ${route.label}`.toLowerCase();
    const shortName = String(route.route.route_short_name || "").trim().toLowerCase();
    const knownPlaceholderIds = new Set(["CTA 1023", "Route 8", "Route 15", "A-12 Express"]);
    return route.id &&
      !knownPlaceholderIds.has(route.id) &&
      String(route.mode).toLowerCase() === "bus" &&
      Number(route.route.route_type) === 3 &&
      shortName !== "box" &&
      !searchable.includes("microbus") &&
      !searchable.includes("minibus") &&
      !searchable.includes("paratransit") &&
      !searchable.includes("tomnaya") &&
      !searchable.includes("suzuki");
  });
}

function driverCheckboxId(prefix, driverId, index) {
  return `${prefix}-${index}-${String(driverId).replace(/[^a-zA-Z0-9_-]/g, "_")}`;
}

function postJson(url, data) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url, true);
    request.setRequestHeader("Content-Type", "application/json");
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`HTTP ${request.status}: ${request.responseText}`));
        return;
      }
      try {
        resolve(request.responseText ? JSON.parse(request.responseText) : {});
      } catch (error) {
        resolve({});
      }
    };
    request.onerror = () => reject(new Error("Network request failed"));
    request.send(JSON.stringify(data));
  });
}

function putJson(url, data) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", url, true);
    request.setRequestHeader("Content-Type", "application/json");
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`HTTP ${request.status}: ${request.responseText}`));
        return;
      }
      try {
        resolve(request.responseText ? JSON.parse(request.responseText) : {});
      } catch (error) {
        resolve({});
      }
    };
    request.onerror = () => reject(new Error("Network request failed"));
    request.send(JSON.stringify(data));
  });
}

async function loadCcRegions() {
  try {
    const data = await getJson(`${API_BASE_URL}/control/regions?_=${Date.now()}`);
    if (Array.isArray(data)) {
      ccRegions = data;
      ccRegionsError = "";
      for (const r of ccRegions) {
        try {
          const sum = await getJson(`${API_BASE_URL}/control/regions/${r.region_id}/summary?_=${Date.now()}`);
          activeRegionSummary[r.region_id] = sum;
        } catch (_) {}
      }
    }
  } catch (error) {
    ccRegionsError = `Cannot load regions: ${error.message}`;
  }
}

async function loadRegionMeta() {
  try {
    const busRouteData = await getJson(`${API_BASE_URL}/control-center/bus-routes?_=${Date.now()}`);
    ccBusRoutes = Array.isArray(busRouteData) ? busRouteData : (busRouteData.routes || []);
    ccAllRoutes = ccBusRoutes;
  } catch (error) {
    console.error("Failed to load bus routes: ", error);
  }

  try {
    const vehicleData = await getJson(`${API_BASE_URL}/control/vehicles?_=${Date.now()}`);
    ccAllVehicles = vehicleData.vehicles || [];
  } catch (error) {
    console.error("Failed to load vehicles: ", error);
  }

  try {
    const userData = await getJson(`${API_BASE_URL}/control-center/drivers?_=${Date.now()}`);
    const users = userData.users || [];
    ccAllSupervisors = users.filter(u => u.role === "Supervisor");
    ccAllDrivers = users.filter(u => u.role === "Driver");
  } catch (error) {
    console.error("Failed to load users: ", error);
  }
}

window.openCreateRegionModal = () => {
  selectedRegion = null;
  showRegionModal = "create";
  render();
};

window.openEditRegionModal = async (regionId) => {
  try {
    const detail = await getJson(`${API_BASE_URL}/control-center/regions/${regionId}?_=${Date.now()}`);
    selectedRegion = detail;
    showRegionModal = "edit";
  } catch (error) {
    console.error("Failed to load region detail:", error);
    selectedRegion = ccRegions.find(r => r.region_id === regionId);
    showRegionModal = "edit";
  }
  render();
};

window.closeRegionModal = () => {
  showRegionModal = null;
  render();
};

window.openMappingModal = async (regionId, type) => {
  selectedRegion = ccRegions.find(r => r.region_id === regionId);
  showMappingModal = type;
  currentMappings = [];
  render();
  
  try {
    if (type === "routes") {
      console.log("MAP_ROUTES_AVAILABLE_COUNT", normalizedBusRouteOptions().length);
      const data = await getJson(`${API_BASE_URL}/control/regions/${regionId}/routes`);
      currentMappings = data.map(x => x.route_id);
      console.log("REGION_ASSIGNED_ROUTES_AFTER_SAVE", currentMappings);
    } else if (type === "drivers") {
      console.log("MAP_DRIVERS_AVAILABLE_COUNT", ccAllDrivers.length);
      const data = await getJson(`${API_BASE_URL}/control/regions/${regionId}/drivers`);
      currentMappings = data.map(x => x.driver_id);
      console.log("REGION_ASSIGNED_DRIVERS_AFTER_SAVE", currentMappings);
    } else if (type === "supervisors") {
      const data = await getJson(`${API_BASE_URL}/control/regions/${regionId}/supervisors`);
      currentMappings = data.map(x => x.supervisor_id);
    } else if (type === "vehicles") {
      const data = await getJson(`${API_BASE_URL}/control/regions/${regionId}/vehicles`);
      currentMappings = data.map(x => x.vehicle_id);
      console.log("MAP_VEHICLES_SELECTED_FROM_BACKEND", currentMappings);
    }
  } catch (error) {
    console.error("Failed to load mappings: ", error);
  }
  render();
};

window.openAddRoutesModal = async () => {
  if (!selectedRegion) return;
  showMappingModal = "routes-add";
  try {
    const data = await getJson(`${API_BASE_URL}/control/regions/${selectedRegion.region_id}/routes`);
    currentMappings = data.map(x => x.route_id);
    console.log("REGION_ASSIGNED_ROUTES_AFTER_SAVE", currentMappings);
  } catch (error) {
    console.error("Failed to load assigned routes before add:", error);
  }
  render();
};

window.openAddDriversModal = async () => {
  if (!selectedRegion) return;
  showMappingModal = "drivers-add";
  try {
    const data = await getJson(`${API_BASE_URL}/control/regions/${selectedRegion.region_id}/drivers`);
    currentMappings = data.map(x => x.driver_id);
    console.log("REGION_ASSIGNED_DRIVERS_AFTER_SAVE", currentMappings);
  } catch (error) {
    console.error("Failed to load assigned drivers before add:", error);
  }
  render();
};

window.closeMappingModal = () => {
  showMappingModal = null;
  render();
};

window.submitRegionForm = async (event) => {
  event.preventDefault();
  const form = event.target;
  const checkedBoxes = form.querySelectorAll('input[name="mapped_route"]:checked');
  const route_ids = Array.from(checkedBoxes).map(cb => cb.value);
  const checkedDriverBoxes = form.querySelectorAll('input[name="mapped_driver"]:checked');
  const driver_ids = Array.from(checkedDriverBoxes).map(cb => cb.value);

  if (route_ids.length === 0) {
    const confirmSave = confirm("Warning: No bus routes selected for this region. Are you sure you want to save?");
    if (!confirmSave) {
      return;
    }
  }

  const region_id = form.elements.region_id ? form.elements.region_id.value : (selectedRegion ? selectedRegion.region_id : "");
  const payload = {
    region_id: region_id,
    region_name: form.elements.region_name.value,
    description: form.elements.description.value,
    active: form.elements.active.checked,
    route_ids: route_ids,
    driver_ids: driver_ids
  };

  try {
    if (showRegionModal === "create") {
      await postJson(`${API_BASE_URL}/control/regions`, payload);
    } else {
      await putJson(`${API_BASE_URL}/control-center/regions/${selectedRegion.region_id}`, payload);
    }
    showRegionModal = null;
    await loadCcRegions();
    render();
  } catch (error) {
    alert(`Failed to save region: ${error.message}`);
  }
};

window.filterBusRoutes = (query) => {
  const q = query.toLowerCase().trim();
  const items = document.querySelectorAll(".route-checkbox-item");
  items.forEach(item => {
    const text = item.getAttribute("data-search-text") || "";
    if (text.includes(q)) {
      item.style.display = "flex";
    } else {
      item.style.display = "none";
    }
  });
};

window.submitMappingForm = async (event) => {
  event.preventDefault();
  const form = event.target;
  const checkboxes = form.querySelectorAll('input[type="checkbox"]:checked');
  const selectedValues = Array.from(checkboxes).map(cb => cb.value);
  
  try {
    if (showMappingModal === "routes" || showMappingModal === "routes-add") {
      const finalRouteIds = showMappingModal === "routes-add"
        ? Array.from(new Set([...currentMappings.map(String), ...selectedValues.map(String)]))
        : selectedValues;
      console.log("MAP_ROUTES_SELECTED_IDS_BEFORE_SAVE", finalRouteIds);
      const routesPayload = {
        routes: finalRouteIds.map(r_id => {
          const r = normalizedBusRouteOptions().find(x => x.id === r_id);
          return {
            route_id: r_id,
            route_name: r ? r.label : r_id,
            mode: r ? r.mode : "Bus"
          };
        })
      };
      console.log("SAVE_REGION_ROUTE_MAPPINGS_PAYLOAD", routesPayload);
      await postJson(`${API_BASE_URL}/control/regions/${selectedRegion.region_id}/routes`, routesPayload);
      const assignedRoutes = await getJson(`${API_BASE_URL}/control/regions/${selectedRegion.region_id}/routes`);
      console.log("REGION_ASSIGNED_ROUTES_AFTER_SAVE", assignedRoutes.map(route => route.route_id));
    } else if (showMappingModal === "drivers" || showMappingModal === "drivers-add") {
      const finalDriverIds = showMappingModal === "drivers-add"
        ? Array.from(new Set([...currentMappings.map(String), ...selectedValues.map(String)]))
        : selectedValues;
      console.log("MAP_DRIVERS_SELECTED_IDS_BEFORE_SAVE", finalDriverIds);
      const driversPayload = { drivers: finalDriverIds };
      console.log("SAVE_REGION_DRIVER_MAPPINGS_PAYLOAD", driversPayload);
      await postJson(`${API_BASE_URL}/control/regions/${selectedRegion.region_id}/drivers`, driversPayload);
      const assignedDrivers = await getJson(`${API_BASE_URL}/control/regions/${selectedRegion.region_id}/drivers`);
      console.log("REGION_ASSIGNED_DRIVERS_AFTER_SAVE", assignedDrivers.map(driver => driver.driver_id));
    } else if (showMappingModal === "supervisors") {
      const supervisorsPayload = {
        supervisors: selectedValues
      };
      await postJson(`${API_BASE_URL}/control/regions/${selectedRegion.region_id}/supervisors`, supervisorsPayload);
    } else if (showMappingModal === "vehicles") {
      console.log("MAP_VEHICLES_SELECTED_IDS_BEFORE_SAVE", selectedValues);
      const vehiclesPayload = {
        region_id: selectedRegion.region_id,
        vehicle_ids: selectedValues,
        vehicles: selectedValues
      };
      console.log("SAVE_REGION_VEHICLES_PAYLOAD", vehiclesPayload);
      const vehiclesResponse = await postJson(`${API_BASE_URL}/control/regions/${selectedRegion.region_id}/vehicles`, vehiclesPayload);
      console.log("SAVE_REGION_VEHICLES_RESPONSE", vehiclesResponse);
      
      // Clear old state completely and reload active mappings from backend
      currentMappings = [];
      const supervisorVehicles = await getJson(`${API_BASE_URL}/control/regions/${selectedRegion.region_id}/vehicles`);
      currentMappings = supervisorVehicles.map(x => x.vehicle_id);
      console.log("SUPERVISOR_VEHICLES_RESPONSE_AFTER_SAVE", supervisorVehicles);
    }
    showMappingModal = null;
    await loadCcRegions();
    await loadCcUsers();
    render();
  } catch (error) {
    alert(`Failed to save mappings: ${error.message}`);
  }
};

function renderRegions() {
  return html`
    <div class="search-row" style="margin-bottom: 24px;">
      <div style="flex-grow:1;">
        <p class="meta" style="margin:0;">Manage geographic zones, map routes, and assign supervisor authorities.</p>
      </div>
      <button class="btn primary" onclick="openCreateRegionModal()">Create Region</button>
    </div>

    ${ccRegionsError ? html`<div class="card" style="border-left: 4px solid #F20A18; padding: 12px; margin-bottom: 20px;"><p style="color:#F20A18; font-weight:600; margin:0;">${ccRegionsError}</p></div>` : ""}

    <div class="grid three-col">
      ${ccRegions.map(region => {
        const sum = activeRegionSummary[region.region_id] || {
          supervisors: [],
          routes_count: 0,
          vehicles_count: 0,
          active_duties: 0,
          active_incidents: 0
        };
        const statusTone = region.active ? "green" : "gray";
        const statusLabel = region.active ? "Active" : "Inactive";
        const incidentsTone = sum.active_incidents > 0 ? "red" : "gray";
        
        return html`
          <section class="card region-card" style="position: relative; display: flex; flex-direction: column; justify-content: space-between; min-height: 290px;">
            <div>
              <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:12px;">
                <h3 class="card-title" style="margin:0;">${escapeHtml(region.region_name)}</h3>
                ${badge(statusLabel, statusTone)}
              </div>
              <p class="meta" style="margin-bottom: 16px; min-height: 40px;">${escapeHtml(region.description || "No description provided.")}</p>
              
              <div style="font-size:13px; line-height:1.8; margin-bottom:20px;">
                <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding:4px 0;">
                  <span style="color:#667085; font-weight:500;">Supervisors:</span>
                  <span style="font-weight:600; color:#101828;">${sum.supervisors.length ? escapeHtml(sum.supervisors.join(", ")) : "None"}</span>
                </div>
                <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding:4px 0;">
                  <span style="color:#667085; font-weight:500;">Routes:</span>
                  <span style="font-weight:600; color:#101828;">${sum.routes_count} mapped</span>
                </div>
                <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding:4px 0;">
                  <span style="color:#667085; font-weight:500;">Vehicles:</span>
                  <span style="font-weight:600; color:#101828;">${sum.vehicles_count} mapped</span>
                </div>
                <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding:4px 0;">
                  <span style="color:#667085; font-weight:500;">Active Duties:</span>
                  <span style="font-weight:600; color:#101828;">${badge(sum.active_duties, sum.active_duties > 0 ? "blue" : "gray")}</span>
                </div>
                <div style="display:flex; justify-content:space-between; padding:4px 0;">
                  <span style="color:#667085; font-weight:500;">Active Incidents:</span>
                  <span>${badge(sum.active_incidents, incidentsTone)}</span>
                </div>
              </div>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-top:auto;">
              <button class="btn" onclick="openMappingModal('${region.region_id}', 'routes')" style="font-size:12px; padding:6px 8px;">Map Routes</button>
              <button class="btn" onclick="openMappingModal('${region.region_id}', 'drivers')" style="font-size:12px; padding:6px 8px;">Map Drivers</button>
              <button class="btn" onclick="openMappingModal('${region.region_id}', 'supervisors')" style="font-size:12px; padding:6px 8px;">Map Supervisors</button>
              <button class="btn" onclick="openMappingModal('${region.region_id}', 'vehicles')" style="font-size:12px; padding:6px 8px;">Map Vehicles</button>
              <button class="btn" onclick="openEditRegionModal('${region.region_id}')" style="font-size:12px; padding:6px 8px;">Edit Region</button>
            </div>
          </section>
        `;
      }).join("")}
      
      ${ccRegions.length === 0 ? html`<div class="span-3 card" style="text-align:center; padding:40px;"><p class="meta">No regions found. Click 'Create Region' to add one.</p></div>` : ""}
    </div>
  `;
}

function renderRegionModals() {
  if (showRegionModal) {
    const isEdit = showRegionModal === "edit";
    const nameVal = isEdit && selectedRegion ? selectedRegion.region_name : "";
    const descVal = isEdit && selectedRegion ? (selectedRegion.description || "") : "";
    const activeChecked = isEdit && selectedRegion ? (selectedRegion.active ? "checked" : "") : "checked";
    const selectedRouteIds = new Set((isEdit && selectedRegion && selectedRegion.route_ids) ? selectedRegion.route_ids.map(String) : []);
    const selectedDriverIds = new Set((isEdit && selectedRegion && selectedRegion.driver_ids) ? selectedRegion.driver_ids.map(String) : []);
    const routeOptions = normalizedBusRouteOptions();
    
    return html`
      <div class="modal-overlay">
        <div class="modal-card card region-modal-card">
          <h3 class="card-title modal-title">${isEdit ? "Edit Region" : "Create New Region"}</h3>
          <form onsubmit="submitRegionForm(event)" class="modal-form">
            <div class="form-grid modal-scroll">
              <div class="field span-2">
                <label>Region ID *</label>
                <input name="region_id" ${isEdit ? "readonly style='background:#f3f3f3; color:#777;'" : "required"} value="${escapeHtml(isEdit && selectedRegion ? selectedRegion.region_id : "")}" placeholder="e.g. Zone_East">
              </div>
              <div class="field span-2">
                <label>Region Name *</label>
                <input name="region_name" required value="${escapeHtml(nameVal)}" placeholder="e.g. Zone East">
              </div>
              <div class="field span-2">
                <label>Description</label>
                <textarea name="description" rows="3" placeholder="Enter region description...">${escapeHtml(descVal)}</textarea>
              </div>
              <div class="field span-2">
                <label>Mapped Bus Routes</label>
                <input type="text" id="route-search" class="route-search-input" oninput="filterBusRoutes(this.value)" placeholder="Search bus routes...">
                <div id="bus-routes-list" class="route-checkbox-list">
                  ${routeOptions.map((route, index) => {
                    const isChecked = selectedRouteIds.has(String(route.id));
                    const inputId = routeCheckboxId("region-route", route.id, index);
                    return html`
                      <div class="route-checkbox-item" data-route-id="${escapeHtml(route.id)}" data-search-text="${escapeHtml(route.label.toLowerCase())}">
                        <input type="checkbox" name="mapped_route" value="${escapeHtml(route.id)}" id="${escapeHtml(inputId)}" ${isChecked ? 'checked' : ''}>
                        <label for="${escapeHtml(inputId)}">${escapeHtml(route.label)}</label>
                      </div>
                    `;
                  })}
                  ${routeOptions.length === 0 ? html`<p class="meta empty-list-note">No bus routes loaded from backend.</p>` : ""}
                </div>
              </div>
              <div class="field span-2">
                <label>Mapped Drivers</label>
                <input type="text" class="route-search-input" oninput="filterBusRoutes(this.value)" placeholder="Search drivers...">
                <div class="route-checkbox-list">
                  ${ccAllDrivers.map((driver, index) => {
                    const id = driver.driver_id;
                    const label = `${driver.name || id} (${id})`;
                    const isChecked = selectedDriverIds.has(String(id));
                    const inputId = driverCheckboxId("region-driver", id, index);
                    return html`
                      <div class="route-checkbox-item" data-driver-id="${escapeHtml(id)}" data-search-text="${escapeHtml(label.toLowerCase())}">
                        <input type="checkbox" name="mapped_driver" value="${escapeHtml(id)}" id="${escapeHtml(inputId)}" ${isChecked ? 'checked' : ''}>
                        <label for="${escapeHtml(inputId)}">${escapeHtml(label)}</label>
                      </div>
                    `;
                  }).join("")}
                  ${ccAllDrivers.length === 0 ? html`<p class="meta empty-list-note">No drivers loaded from backend.</p>` : ""}
                </div>
              </div>
              <div class="field span-2" style="display:flex; flex-direction:row; align-items:center; gap:8px;">
                <input type="checkbox" name="active" id="region-active" ${activeChecked}>
                <label for="region-active" style="margin:0; cursor:pointer; font-weight: 500;">Active Zone (visible to supervisors)</label>
              </div>
            </div>
            <div class="modal-actions">
              <button class="btn" type="button" onclick="closeRegionModal()">Cancel</button>
              <button class="btn primary" type="submit">Save Region</button>
            </div>
          </form>
        </div>
      </div>
    `;
  }

  if (showMappingModal) {
    let title = "";
    let description = "Select items to associate with this operational region.";
    let extraActions = "";
    let options = [];
    
    if (showMappingModal === "routes") {
      title = `Assigned Routes - ${selectedRegion.region_name}`;
      description = "This region owns only the routes shown here. Use Add Routes to include more available bus routes.";
      const assignedIds = currentMappings.map(String);
      options = assignedIds.map((routeId) => {
        const route = normalizedBusRouteOptions().find(r => String(r.id) === String(routeId));
        return {
          id: routeId,
          label: route ? route.label : routeId,
          checked: true
        };
      });
      extraActions = html`<button class="btn primary" type="button" onclick="openAddRoutesModal()">Add Routes</button>`;
    } else if (showMappingModal === "routes-add") {
      title = `Add Routes - ${selectedRegion.region_name}`;
      description = "Available bus routes not currently owned by this region.";
      const assignedIds = new Set(currentMappings.map(String));
      options = normalizedBusRouteOptions()
        .filter(r => !assignedIds.has(String(r.id)))
        .map(r => ({
          id: r.id,
          label: r.label,
          checked: false
        }));
    } else if (showMappingModal === "drivers") {
      title = `Assigned Drivers - ${selectedRegion.region_name}`;
      description = "This region owns only the drivers shown here. Use Add Drivers to include more available drivers.";
      const assignedIds = currentMappings.map(String);
      options = assignedIds.map((driverId) => {
        const driver = ccAllDrivers.find(d => String(d.driver_id) === String(driverId));
        return {
          id: driverId,
          label: driver ? `${driver.name || driver.driver_id} (${driver.driver_id})` : driverId,
          checked: true
        };
      });
      extraActions = html`<button class="btn primary" type="button" onclick="openAddDriversModal()">Add Drivers</button>`;
    } else if (showMappingModal === "drivers-add") {
      title = `Add Drivers - ${selectedRegion.region_name}`;
      description = "Available drivers not currently owned by this region.";
      const assignedIds = new Set(currentMappings.map(String));
      options = ccAllDrivers
        .filter(d => !assignedIds.has(String(d.driver_id)))
        .map(d => ({
          id: d.driver_id,
          label: `${d.name || d.driver_id} (${d.driver_id})`,
          checked: false
        }));
    } else if (showMappingModal === "supervisors") {
      title = `Assign Supervisors - ${selectedRegion.region_name}`;
      options = ccAllSupervisors.map(s => ({
        id: s.driver_id,
        label: `${s.name} (${s.driver_id})`,
        checked: currentMappings.includes(s.driver_id)
      }));
    } else if (showMappingModal === "vehicles") {
      title = `Map Vehicles - ${selectedRegion.region_name}`;
      options = ccAllVehicles.map(v => ({
        id: v,
        label: `Vehicle ${v}`,
        checked: currentMappings.includes(v)
      }));
    }
    
    return html`
      <div class="modal-overlay">
        <div class="modal-card card region-modal-card">
          <h3 class="card-title modal-title">${escapeHtml(title)}</h3>
          <p class="meta" style="margin-top:0; margin-bottom:16px;">${escapeHtml(description)}</p>
          <form onsubmit="submitMappingForm(event)" class="modal-form">
            <div class="mapping-list modal-scroll">
              ${options.map((opt, index) => {
                const inputId = routeCheckboxId("mapping-item", opt.id, index);
                return html`
                <label class="mapping-item" for="${escapeHtml(inputId)}">
                  <input id="${escapeHtml(inputId)}" type="checkbox" value="${escapeHtml(opt.id)}" ${opt.checked ? "checked" : ""}>
                  <span>${escapeHtml(opt.label)}</span>
                </label>
              `;}).join("")}
              ${options.length === 0 ? html`<p class="meta" style="text-align:center; margin:20px 0;">No items available to map.</p>` : ""}
            </div>
            <div class="modal-actions">
              <button class="btn" type="button" onclick="closeMappingModal()">Cancel</button>
              ${extraActions}
              <button class="btn primary" type="submit">Save Mappings</button>
            </div>
          </form>
        </div>
      </div>
    `;
  }
  return "";
}

function renderConfiguration() {
  return html`
    <div class="grid two-col">
      <section class="card">
        <h3 class="card-title">Route Configuration</h3>
        <div class="form-grid">
          <div class="field span-2"><label>Select Route</label><select><option>Route 1 - Downtown Loop</option><option>Route 8 - Heliopolis Express</option></select></div>
          <div class="field"><label>Headway (minutes)</label><input value="10"></div>
          <div class="field"><label>Peak Headway</label><input value="7"></div>
          <div class="field"><label>Operating Hours</label><input value="05:00 - 23:00"></div>
          <div class="field"><label>Fare</label><input value="5 EGP"></div>
          <button class="btn primary span-2">Save Route Settings</button>
        </div>
      </section>
      <section class="card">
        <h3 class="card-title">Service Calendar</h3>
        <div class="form-grid">
          <div class="field span-2"><label>Service Type</label><select><option>Regular Service</option><option>Holiday Service</option></select></div>
          <div class="field span-2"><label>Active Days</label><div class="filters"><label><input type="checkbox" checked> Mon</label><label><input type="checkbox" checked> Tue</label><label><input type="checkbox" checked> Wed</label><label><input type="checkbox" checked> Thu</label><label><input type="checkbox" checked> Fri</label><label><input type="checkbox" checked> Sat</label><label><input type="checkbox" checked> Sun</label></div></div>
          <div class="field span-2"><label>Next Holiday</label><input type="date"></div>
          <button class="btn primary span-2">Update Calendar</button>
        </div>
      </section>
      <section class="card">
        <h3 class="card-title">Alert Settings</h3>
        <div class="check-list">
          ${["Vehicle breakdown alerts", "Delay threshold exceeded", "Passenger capacity warnings", "Maintenance due notifications", "Off-route alerts"].map(x => `<label class="check-row">${x}<input type="checkbox" checked></label>`).join("")}
        </div>
      </section>
      <section class="card">
        <h3 class="card-title">System Parameters</h3>
        <div class="form-grid">
          <div class="field span-2"><label>Delay Threshold (minutes)</label><input value="5"></div>
          <div class="field span-2"><label>Maximum Passenger Capacity</label><input value="60"></div>
          <div class="field span-2"><label>Refresh Interval (seconds)</label><input value="30"></div>
          <button class="btn primary span-2">Apply Settings</button>
        </div>
      </section>
    </div>
  `;
}

window.downloadServiceCheckFile = (incidentId) => {
  const check = supervisorServiceChecks.find(c => c.incident_id === incidentId);
  if (!check) {
    alert("Report file data not loaded.");
    return;
  }
  
  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    alert("Please allow popups to download/print the PDF report.");
    return;
  }

  let checksHtml = "";
  if (check.raw_payload?.checks) {
    for (const [key, value] of Object.entries(check.raw_payload.checks)) {
      checksHtml += `
        <div class="checklist-item">
          <span class="status-badge ${value ? 'pass' : 'fail'}">${value ? 'PASS' : 'FAIL'}</span>
          <span class="item-name">${key}</span>
        </div>
      `;
    }
  } else {
    checksHtml = "<p>No checklist items recorded.</p>";
  }

  const htmlContent = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Service Check Report - ${check.vehicle_id || "Vehicle"}</title>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
      <style>
        body {
          font-family: 'Inter', sans-serif;
          color: #1e293b;
          margin: 0;
          padding: 40px;
          line-height: 1.5;
          background-color: #ffffff;
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 2px solid #e2e8f0;
          padding-bottom: 20px;
          margin-bottom: 30px;
        }
        .logo-section h1 {
          margin: 0;
          font-size: 24px;
          font-weight: 800;
          color: #2563eb;
          letter-spacing: -0.5px;
        }
        .logo-section p {
          margin: 4px 0 0 0;
          font-size: 12px;
          color: #64748b;
          text-transform: uppercase;
          font-weight: 600;
        }
        .report-title {
          text-align: right;
        }
        .report-title h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 700;
          color: #0f172a;
        }
        .report-title p {
          margin: 4px 0 0 0;
          font-size: 12px;
          color: #64748b;
        }
        .meta-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 16px;
          margin-bottom: 30px;
          background-color: #f8fafc;
          padding: 20px;
          border-radius: 8px;
          border: 1px solid #e2e8f0;
        }
        .meta-item {
          display: flex;
          flex-direction: column;
        }
        .meta-label {
          font-size: 11px;
          text-transform: uppercase;
          font-weight: 600;
          color: #64748b;
          margin-bottom: 4px;
        }
        .meta-value {
          font-size: 14px;
          font-weight: 600;
          color: #0f172a;
        }
        .rating-badge {
          display: inline-flex;
          align-items: center;
          background-color: #fef9c3;
          color: #854d0e;
          padding: 4px 8px;
          border-radius: 4px;
          font-weight: 700;
          font-size: 12px;
        }
        .section-title {
          font-size: 14px;
          font-weight: 700;
          text-transform: uppercase;
          color: #475569;
          border-bottom: 1px solid #e2e8f0;
          padding-bottom: 8px;
          margin-top: 30px;
          margin-bottom: 16px;
        }
        .checklist {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }
        .checklist-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 12px;
          background-color: #ffffff;
          border: 1px solid #f1f5f9;
          border-radius: 6px;
        }
        .status-badge {
          font-size: 10px;
          font-weight: 700;
          padding: 2px 6px;
          border-radius: 4px;
          text-transform: uppercase;
        }
        .status-badge.pass {
          background-color: #d1fae5;
          color: #065f46;
        }
        .status-badge.fail {
          background-color: #fee2e2;
          color: #991b1b;
        }
        .item-name {
          font-size: 13px;
          font-weight: 500;
        }
        .recommendations {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .rec-item {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
        }
        .rec-bullet {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .rec-bullet.yes {
          background-color: #2563eb;
        }
        .rec-bullet.no {
          background-color: #cbd5e1;
        }
        .notes-content {
          font-size: 13px;
          background-color: #f8fafc;
          padding: 16px;
          border-radius: 8px;
          border: 1px solid #e2e8f0;
          white-space: pre-wrap;
          font-family: inherit;
          margin: 0;
        }
        .footer {
          margin-top: 60px;
          border-top: 1px solid #e2e8f0;
          padding-top: 20px;
          text-align: center;
          font-size: 11px;
          color: #94a3b8;
        }
        @media print {
          body {
            padding: 0;
          }
          .no-print {
            display: none;
          }
        }
        .print-btn-container {
          display: flex;
          justify-content: flex-end;
          margin-bottom: 20px;
        }
        .btn-print {
          background-color: #2563eb;
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          font-family: inherit;
        }
        .btn-print:hover {
          background-color: #1d4ed8;
        }
      </style>
    </head>
    <body>
      <div class="print-btn-container no-print">
        <button class="btn-print" onclick="window.print()">Print / Save as PDF</button>
      </div>
      <div class="header">
        <div class="logo-section">
          <h1>IZEE TRANSIT SYSTEM</h1>
          <p>Field Observation Report</p>
        </div>
        <div class="report-title">
          <h2>REPORT DETAILS</h2>
          <p>ID: ${check.incident_id}</p>
        </div>
      </div>

      <div class="meta-grid">
        <div class="meta-item">
          <span class="meta-label">Vehicle ID</span>
          <span class="meta-value">${check.vehicle_id || "N/A"}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Route ID</span>
          <span class="meta-value">${check.route_id || "N/A"}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Date & Time</span>
          <span class="meta-value">${check.created_at ? new Date(check.created_at).toLocaleString() : "N/A"}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Overall Rating</span>
          <span class="meta-value">
            <span class="rating-badge">${check.raw_payload?.rating || 5} / 5 Stars</span>
          </span>
        </div>
      </div>

      <div class="section-title">Quality Checklist</div>
      <div class="checklist">
        ${checksHtml}
      </div>

      <div class="section-title">Recommendations</div>
      <div class="recommendations">
        <div class="rec-item">
          <span class="rec-bullet ${check.raw_payload?.recommend_driver_training ? 'yes' : 'no'}"></span>
          <span>Recommend Driver Training: <strong>${check.raw_payload?.recommend_driver_training ? 'YES' : 'NO'}</strong></span>
        </div>
        <div class="rec-item">
          <span class="rec-bullet ${check.raw_payload?.recommend_vehicle_maintenance ? 'yes' : 'no'}"></span>
          <span>Suggest Vehicle Maintenance: <strong>${check.raw_payload?.recommend_vehicle_maintenance ? 'YES' : 'NO'}</strong></span>
        </div>
        <div class="rec-item">
          <span class="rec-bullet ${check.raw_payload?.commend_excellent_service ? 'yes' : 'no'}"></span>
          <span>Commend for Excellent Service: <strong>${check.raw_payload?.commend_excellent_service ? 'YES' : 'NO'}</strong></span>
        </div>
      </div>

      <div class="section-title">Supervisor Notes</div>
      <pre class="notes-content">${check.details || "No additional observation notes provided."}</pre>

      <div class="footer">
        © 2026 IZEE Smart Transportation • Confidential Operation Report
      </div>

      <script>
        window.onload = function() {
          setTimeout(function() {
            window.print();
          }, 500);
        }
      </script>
    </body>
    </html>
  `;

  printWindow.document.open();
  printWindow.document.write(htmlContent);
  printWindow.document.close();
};

function renderLogs() {
  return html`
    <div class="grid two-col">
      <section class="card">
        <h3 class="card-title">Generate Reports</h3>
        <div class="form-grid">
          <div class="field span-2"><label>Report Type</label><select><option>Daily Operations Summary</option><option>On-Time Performance</option><option>Incident Summary</option></select></div>
          <div class="field"><label>From Date</label><input type="date"></div>
          <div class="field"><label>To Date</label><input type="date"></div>
          <div class="field span-2"><label>Format</label><div class="filters"><label><input type="radio" checked name="format"> PDF</label><label><input type="radio" name="format"> Excel</label><label><input type="radio" name="format"> CSV</label></div></div>
          <button class="btn primary span-2">Generate Report</button>
        </div>
      </section>
      <section class="card">
        <h3 class="card-title">Available Reports</h3>
        <div class="report-list">
          ${[
            ["Daily Operations Summary", "Complete daily operations report", "Today 6:00 AM", "2.3 MB"],
            ["On-Time Performance Report", "Weekly OTP analysis", "Yesterday", "1.8 MB"],
            ["Incident Summary", "Monthly incident trends", "3 days ago", "890 KB"],
            ["Vehicle Utilization", "Fleet utilization metrics", "Today 6:00 AM", "1.2 MB"],
          ].map(([title, desc, time, size]) => html`
            <div class="report-row"><div class="row-line"><div><strong>${title}</strong><br><span class="meta">${desc}</span></div><button class="btn">Download</button></div><span class="meta">${time} &nbsp; ${size}</span></div>
          `).join("")}
          
          ${supervisorServiceChecks.map((check) => {
            const title = `Service Check - ${check.vehicle_id || "Vehicle"}`;
            const rating = check.raw_payload?.rating || 5;
            const desc = `Rating: ${rating}/5. ${check.details || ""}`;
            const time = check.created_at ? new Date(check.created_at).toLocaleString() : "Recently";
            const size = `${(new Blob([JSON.stringify(check)]).size / 1024).toFixed(1)} KB`;
            return html`
              <div class="report-row">
                <div class="row-line">
                  <div>
                    <strong>${title}</strong><br>
                    <span class="meta">${desc}</span>
                  </div>
                  <button class="btn primary" onclick="downloadServiceCheckFile('${check.incident_id}')">Download File</button>
                </div>
                <span class="meta">${time} &nbsp; ${size}</span>
              </div>
            `;
          }).join("")}
        </div>
      </section>
    </div>
    <section class="card" style="margin-top:24px">
      <h3 class="card-title">System Activity Logs</h3>
      <table class="table">
        <thead><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Type</th></tr></thead>
        <tbody>
          ${[
            ["2024-12-24 10:45:32", "Ahmed Hassan", "Acknowledged incident INC-2024-002", "incident", "red"],
            ["2024-12-24 10:30:15", "System", "Auto-generated maintenance alert for Vehicle #2490", "system", "blue"],
            ["2024-12-24 10:15:08", "Sara Mahmoud", "Sent broadcast message to all drivers", "communication", "green"],
            ["2024-12-24 09:45:22", "Mohamed Ali", "Reported incident INC-2024-001", "incident", "red"],
            ["2024-12-24 09:30:45", "Admin", "Updated route configuration for Route 8", "config", "gray"],
          ].map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${badge(r[3], r[4])}</td></tr>`).join("")}
        </tbody>
      </table>
    </section>
  `;
}

const renderers = {
  dashboard: renderDashboard,
  map: renderMap,
  analytics: renderAnalytics,
  incidents: renderIncidents,
  communications: renderCommunications,
  users: renderUsers,
  regions: renderRegions,
  configuration: renderConfiguration,
  logs: renderLogs,
};

function initSurveyMap() {
  const mapContainer = document.getElementById("survey-map");
  if (!mapContainer) return;

  if (typeof L === "undefined") {
    console.error("Leaflet is not loaded.");
    return;
  }

  if (surveyMap) {
    try {
      surveyMap.remove();
    } catch (e) {
      console.error(e);
    }
    surveyMap = null;
  }

  const survey = window.SURVEY_DATA || { hotspots: [] };

  surveyMap = L.map("survey-map").setView([30.0444, 31.2357], 11);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap contributors"
  }).addTo(surveyMap);

  survey.hotspots.forEach((trip) => {
    const lat1 = trip.origin.lat;
    const lon1 = trip.origin.lon;
    const lat2 = trip.destination.lat;
    const lon2 = trip.destination.lon;
    const originName = trip.origin.name;
    const destName = trip.destination.name;

    // Draw Origin circle
    L.circleMarker([lat1, lon1], {
      radius: 6,
      fillColor: "#12b76a",
      color: "#ffffff",
      weight: 1.5,
      opacity: 1,
      fillOpacity: 0.9
    }).addTo(surveyMap)
      .bindTooltip(`<b>Start (Origin):</b> ${originName}`, { permanent: false, direction: "top" });

    // Draw Destination circle
    L.circleMarker([lat2, lon2], {
      radius: 6,
      fillColor: "#ef4444",
      color: "#ffffff",
      weight: 1.5,
      opacity: 1,
      fillOpacity: 0.9
    }).addTo(surveyMap)
      .bindTooltip(`<b>End (Destination):</b> ${destName}`, { permanent: false, direction: "top" });

    // Draw polyline flow route
    const polyline = L.polyline([[lat1, lon1], [lat2, lon2]], {
      color: "#2f80ed",
      weight: 2,
      opacity: 0.4,
      dashArray: "4, 6"
    }).addTo(surveyMap);

    polyline.on("mouseover", function(e) {
      this.setStyle({
        color: "#8b5cf6",
        weight: 4,
        opacity: 0.9,
        dashArray: null
      });
      const popupContent = `
        <div style="font-family:sans-serif; font-size:12px; line-height:1.4; min-width:160px;">
          <strong style="color:#8b5cf6; font-size:13px;">Trip Profile</strong><br/>
          <b>Route:</b> ${originName} ➔ ${destName}<br/>
          <b>Purpose:</b> ${trip.purpose.charAt(0).toUpperCase() + trip.purpose.slice(1)}<br/>
          <b>Mode:</b> ${trip.mode}
        </div>
      `;
      L.popup()
        .setLatLng(e.latlng)
        .setContent(popupContent)
        .openOn(surveyMap);
    });

    polyline.on("mouseout", function(e) {
      this.setStyle({
        color: "#2f80ed",
        weight: 2,
        opacity: 0.4,
        dashArray: "4, 6"
      });
    });

    // Midpoint arrow for direction
    const midLat = (lat1 + lat2) / 2;
    const midLon = (lon1 + lon2) / 2;
    const dy = lat2 - lat1;
    const dx = lon2 - lon1;
    let angle = Math.atan2(dy, dx) * (180 / Math.PI);
    angle = -angle;

    const arrowIcon = L.divIcon({
      className: "flow-arrow-icon",
      html: `<div style="transform: rotate(${angle}deg); color:#2f80ed; font-size:14px; font-weight:bold; pointer-events:none; opacity:0.8;">➔</div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8]
    });

    L.marker([midLat, midLon], { icon: arrowIcon }).addTo(surveyMap);
  });
}

function initLiveMap() {
  const container = document.getElementById("live-map");
  if (!container || typeof L === "undefined") return;

  if (liveMap) {
    try { liveMap.remove(); } catch (_) { /* map was already detached */ }
    liveMap = null;
  }

  liveMap = L.map(container, { zoomControl: true }).setView([30.0444, 31.2357], 11.5);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(liveMap);

  const selectedVehicle = liveVehicles.find(vehicle => vehicle.id === selectedLiveVehicleId);
  if (!selectedVehicle) return;

  const routePoints = selectedVehicleRouteGeometry;
  if (routePoints.length >= 2) {
    L.polyline(routePoints, { color: "#05A845", weight: 6, opacity: 0.85 }).addTo(liveMap);
  }

  const marker = L.marker([selectedVehicle.lat, selectedVehicle.lon], {
    icon: L.divIcon({
      className: "live-bus-marker",
      html: '<span>🚌</span>',
      iconSize: [38, 38],
      iconAnchor: [19, 19],
    }),
  }).addTo(liveMap);
  marker.bindTooltip(`${escapeHtml(selectedVehicle.id)} — ${escapeHtml(selectedVehicle.route)}`, { direction: "top" }).openTooltip();

  const bounds = routePoints.length >= 2
    ? L.latLngBounds([...routePoints, [selectedVehicle.lat, selectedVehicle.lon]])
    : L.latLngBounds([[selectedVehicle.lat, selectedVehicle.lon]]);
  liveMap.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
}

function render() {
  if (!renderers[state.view]) {
    state.view = "dashboard";
  }
  document.querySelector("#page-title").textContent = pageTitles[state.view];
  document.querySelector("#content").innerHTML = renderers[state.view]() + 
    (state.view === "users" ? renderAssignModal() : "") +
    (state.view === "regions" ? renderRegionModals() : "");
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === state.view);
  });
  const messageForm = document.querySelector("#message-form");
  if (messageForm) {
    messageForm.addEventListener("submit", sendControlMessage);
    messageForm.addEventListener("input", syncMessageDraft);
    messageForm.addEventListener("change", syncMessageDraft);
  }
  if (state.view === "analytics" && (state.analyticsTab || "live") === "survey") {
    setTimeout(initSurveyMap, 100);
  }
  if (state.view === "map") {
    setTimeout(initLiveMap, 0);
  }
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", async () => {
    state.view = button.dataset.view;
    window.history.replaceState(null, "", `?view=${state.view}`);
    if (state.view === "users" || state.view === "communications") {
      await loadCcUsers();
    } else if (state.view === "regions") {
      await loadRegionMeta();
      await loadCcRegions();
    }
    render();
  });
});

function updateClock() {
  const now = new Date();
  document.querySelector("#clock").textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

setInterval(updateClock, 30000);
setInterval(loadLiveVehicles, 10000);
setInterval(loadIncidents, 15000);
setInterval(loadServiceChecks, 15000);
setInterval(loadControlMessages, 15000);
setInterval(loadMessagingStats, 5000);
setInterval(() => {
  if (state.view === "communications" || state.view === "users") loadCcUsers().then(render);
}, 15000);
updateClock();
if (state.view === "users" || state.view === "communications") {
  loadCcUsers().then(render);
} else if (state.view === "regions") {
  Promise.all([loadRegionMeta(), loadCcRegions()]).then(render);
} else {
  render();
}
loadLiveVehicles();
loadIncidents();
loadServiceChecks();
loadControlMessages();
loadMessagingStats();
