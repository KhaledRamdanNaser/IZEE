const state = {
  view: new URLSearchParams(window.location.search).get("view") || "dashboard",
  incidentTab: "active",
};

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

let liveVehicles = vehicles.map(([id, route, speed, pax, tone, x, y]) => ({
  id,
  route,
  speed,
  pax,
  tone,
  x,
  y,
  source: "demo",
}));
let liveVehicleError = "";

const incidents = [
  ["Vehicle Breakdown - Route 8", "Engine failure on vehicle #2488 at Heliopolis", "Heliopolis, Abbas El Akkad St", "Driver - Mohamed Ali", "2024-12-24 09:45", "Field Team Alpha", "In Progress", "INC-2024-001", "critical"],
  ["Traffic Congestion - Route 15", "Heavy traffic causing 12 min delay", "Nasr City, Mustafa El-Nahas St", "Driver - Ahmed Hassan", "2024-12-24 10:12", "Unassigned", "New", "INC-2024-002", "warning"],
  ["Scheduled Maintenance Alert", "Vehicle #2490 due for inspection", "Main Depot", "System Auto-Alert", "2024-12-24 07:00", "Maintenance Team", "In Progress", "INC-2024-004", "warning"],
];
let liveIncidents = incidents;
let incidentError = "";
let controlMessages = [
  ["Weather Alert", "To: All Drivers", "Heavy rain expected 2-4 PM. Drive safely.", "10:30 AM", "Delivered"],
  ["Route Adjustment", "To: Route 8 Drivers", "Temporary detour at Heliopolis due to roadwork.", "09:15 AM", "Delivered"],
  ["Meeting Reminder", "To: Supervisor Team", "Weekly review at 3 PM today in main office.", "Yesterday", "Read"],
];
let messageError = "";
let messageDraft = {
  recipients: "all_drivers",
  subject: "",
  body: "",
};

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
      const realCount = liveVehicles.filter((vehicle) => vehicle.source !== "demo").length;
      return [metric[0], String(realCount || liveVehicles.length), liveVehicleError || "From live vehicle endpoint", metric[3], metric[4]];
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
    liveVehicleError = rows.length ? "" : "No live rows yet";
    if (rows.length) {
      liveVehicles = rows.map((vehicle) => ({
        id: vehicle.vehicle_id || "Unknown",
        route: vehicle.source || "Live vehicle",
        speed: `${Math.round(vehicle.speed_kmh || 0)} km/h`,
        pax: "-",
        tone: statusTone(vehicle.status),
        x: normalize(Number(vehicle.lon), 31.20, 31.45),
        y: normalize(Number(vehicle.lat), 30.18, 29.95),
        source: vehicle.source || "backend",
        area: vehicle.area || `${vehicle.lat}, ${vehicle.lon}`,
        updated: vehicle.timestamp || "",
      }));
    }
  } catch (error) {
    liveVehicleError = `Cannot reach backend at ${API_BASE_URL}`;
  }
  if (state.view === "dashboard" || state.view === "map") render();
}

async function loadIncidents() {
  try {
    const data = await getJson(`${API_BASE_URL}/incidents?limit=100&_=${Date.now()}`);
    const rows = Array.isArray(data.incidents) ? data.incidents : [];
    incidentError = rows.length ? "" : "No incidents stored yet";
    if (rows.length) {
      liveIncidents = rows.map((incident) => {
        const status = incident.status === "new" ? "New" : incident.status || "In Progress";
        const level = incident.severity === "critical" ? "critical" : "warning";
        const title = `${incident.category} - ${incident.vehicle_id || "Vehicle"}`;
        const place = incident.location_label || [incident.lat, incident.lon].filter(Boolean).join(", ") || "Unknown location";
        return [
          title,
          incident.details || "Driver submitted incident report",
          place,
          `Driver - ${incident.vehicle_id || "Unknown"}`,
          incident.created_at || "",
          "Control Center",
          status,
          incident.incident_id || "",
          level,
        ];
      });
    }
  } catch (error) {
    incidentError = `Cannot reach incidents API at ${API_BASE_URL}`;
  }
  if (state.view === "incidents" || state.view === "dashboard") render();
}

async function loadControlMessages() {
  try {
    const data = await getJson(`${API_BASE_URL}/messages?limit=20&_=${Date.now()}`);
    const rows = Array.isArray(data.messages) ? data.messages : [];
    messageError = rows.length ? "" : "No messages sent yet";
    if (rows.length) {
      controlMessages = rows.map((message) => [
        message.subject || "Control Center Message",
        `To: ${message.recipient_type || "all_drivers"}`,
        message.body || "",
        message.created_at || "",
        message.read ? "Read" : "Delivered",
      ]);
    }
  } catch (error) {
    messageError = `Cannot reach messages API at ${API_BASE_URL}`;
  }
  if (state.view === "communications") render();
}

async function sendControlMessage(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const recipient = form.elements.recipients.value;
  const subject = form.elements.subject.value.trim();
  const body = form.elements.body.value.trim();
  if (!subject || !body) return;

  try {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/messages`, true);
    request.setRequestHeader("Content-Type", "application/json");
    await new Promise((resolve, reject) => {
      request.onload = () => request.status >= 200 && request.status < 300 ? resolve() : reject(new Error(`HTTP ${request.status}`));
      request.onerror = () => reject(new Error("Network request failed"));
      request.send(JSON.stringify({
        recipient_type: recipient,
        sender: "Control Center",
        subject,
        body,
        priority: subject.toLowerCase().includes("urgent") ? "urgent" : "normal",
        source: "control_center",
      }));
    });
    form.reset();
    messageDraft = { recipients: "all_drivers", subject: "", body: "" };
    await loadControlMessages();
  } catch (error) {
    messageError = `Could not send message: ${error.message}`;
    render();
  }
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

function renderMap() {
  return html`
    <div class="toolbar">
      <div class="filters">
        <button class="btn primary">All Routes (284)</button>
        <button class="btn">Route 1 (12)</button>
        <button class="btn">Route 8 (8)</button>
        <button class="btn">Route 15 (10)</button>
        <button class="btn">Route 22 (6)</button>
        <button class="btn">More Filters</button>
      </div>
      <div class="actions">
        <label class="meta"><input type="checkbox" checked> Auto-refresh (30s)</label>
        <button class="btn primary">Refresh Now</button>
      </div>
    </div>
    <div class="map-layout">
      <section class="map-canvas" aria-label="Vehicle map preview">
        <div class="zoom"><button>+</button><button>-</button></div>
        ${liveVehicles.map((vehicle) => `<div class="map-marker ${vehicle.tone}" title="${vehicle.id} ${vehicle.area || ""}" style="left:${vehicle.x}%;top:${vehicle.y}%">${icon("icon-bus")}</div>`).join("")}
        <div class="legend">
          <span><span class="dot"></span>On Time</span>
          <span><span class="dot orange"></span>Delayed</span>
          <span><span class="dot gray"></span>Stopped</span>
          <span><span class="dot red"></span>Incident</span>
        </div>
      </section>
      <section class="card">
        <h3 class="card-title">Active Vehicles</h3>
        ${liveVehicleError ? `<p class="meta">${liveVehicleError}</p>` : ""}
        <div class="vehicle-list">
          ${liveVehicles.map((vehicle) => html`
            <div class="vehicle-row">
              <div class="row-line"><strong><span class="dot ${vehicle.tone}"></span>Vehicle ${vehicle.id}</strong><span class="meta">${vehicle.route}</span></div>
              <div class="row-line"><span class="meta">Speed: ${vehicle.speed}</span><span class="meta">${vehicle.area || ""}</span></div>
            </div>
          `).join("")}
        </div>
      </section>
    </div>
  `;
}

function renderAnalytics() {
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

function renderIncidents() {
  const activeIncidents = liveIncidents.filter((incident) => incident[6] !== "resolved");
  return html`
    <div class="grid four-metrics kpi-grid">
      ${[
        ["Critical", "1", "", "icon-alert", "red"],
        ["Warning", "2", "", "icon-alert", "orange"],
        ["Resolved Today", "3", "", "OK", "green"],
        ["Avg Response Time", "8m", "", "TIME", "blue"],
      ].map(metricCard).join("")}
    </div>
    <section class="card" style="margin-top:24px">
      <div class="toolbar">
        <div class="filters">
          <button class="btn primary">Active Incidents (${activeIncidents.length})</button>
          <button class="btn">Resolved (1)</button>
          <button class="btn">All (4)</button>
        </div>
        <button class="btn primary">Create New Incident</button>
      </div>
      ${incidentError ? `<p class="meta">${incidentError}</p>` : ""}
      <div class="alert-list">
        ${liveIncidents.map(([title, desc, place, driver, time, team, status, id, level]) => html`
          <article class="incident-card ${level === "warning" ? "warning" : ""}">
            <div class="incident-title">${title} ${badge(status, status === "New" ? "blue" : "orange")} <span class="meta">${id}</span></div>
            <div>${desc}</div>
            <div class="incident-meta">
              <span>Loc: ${place}</span><span>${driver}</span><span>${time}</span><span>${team}</span>
            </div>
            <div class="filters"><button class="btn primary">${status === "New" ? "Acknowledge" : "Mark Resolved"}</button><button class="btn">View Details</button><button class="btn">Assign</button></div>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderCommunications() {
  return html`
    <div class="grid three-col">
      ${[
        ["Messages Sent Today", "24", "", "icon-message", "green"],
        ["Active Recipients", "156", "", "icon-users", "blue"],
        ["Broadcast Messages", "3", "", "ALL", "orange"],
      ].map(metricCard).join("")}
    </div>
    <div class="grid two-col" style="margin-top:24px">
      <section class="card">
        <h3 class="card-title">Send New Message</h3>
        <form class="form-grid" id="message-form">
          <div class="field span-2"><label>Recipients</label><select name="recipients"><option value="all_drivers" ${messageDraft.recipients === "all_drivers" ? "selected" : ""}>All Drivers</option><option value="route_8_drivers" ${messageDraft.recipients === "route_8_drivers" ? "selected" : ""}>Route 8 Drivers</option><option value="supervisors" ${messageDraft.recipients === "supervisors" ? "selected" : ""}>Supervisors</option></select></div>
          <div class="field span-2"><label>Subject</label><input name="subject" value="${escapeHtml(messageDraft.subject)}" placeholder="Enter subject"></div>
          <div class="field span-2"><label>Message</label><textarea name="body" placeholder="Type your message here...">${escapeHtml(messageDraft.body)}</textarea></div>
          <div class="filters span-2"><button class="btn primary" type="submit">Send Message</button><button class="btn" type="button">Save Draft</button></div>
        </form>
      </section>
      <section class="card">
        <h3 class="card-title">Recent Messages</h3>
        ${messageError ? `<p class="meta">${messageError}</p>` : ""}
        <div class="message-list">
          ${controlMessages.map(([title,to,msg,time,status]) => html`
            <div class="message-row"><div class="row-line"><strong>${title}</strong><span class="meta">${time}</span></div><span class="meta">${to}</span><p>${msg}</p>${badge(status)}</div>
          `).join("")}
        </div>
      </section>
    </div>
  `;
}

let ccUsers = [];
let ccUsersError = "";
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
              <option value="A-12 Express" ${assignRouteId === "A-12 Express" ? "selected" : ""}>A-12 Express</option>
              <option value="B-20 Local" ${assignRouteId === "B-20 Local" ? "selected" : ""}>B-20 Local</option>
              <option value="C-05 Shuttle" ${assignRouteId === "C-05 Shuttle" ? "selected" : ""}>C-05 Shuttle</option>
              <option value="M2" ${assignRouteId === "M2" ? "selected" : ""}>M2 (Cairo Metro Line 2)</option>
              <option value="Route 8" ${assignRouteId === "Route 8" ? "selected" : ""}>Route 8</option>
              <option value="Route 15" ${assignRouteId === "Route 15" ? "selected" : ""}>Route 15</option>
              <option value="Route 22" ${assignRouteId === "Route 22" ? "selected" : ""}>Route 22</option>
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
  return html`
    <div class="grid three-col">
      ${[
        ["Total Users", "248", "", "icon-users", "green"],
        ["Active Now", "156", "", "ON", "blue"],
        ["New This Week", "5", "", "+", "orange"],
      ].map(metricCard).join("")}
    </div>
    <section class="card" style="margin-top:24px">
      ${ccUsersError ? `<p style="color:#C5221F;font-weight:600;margin-bottom:12px;">${ccUsersError}</p>` : ""}
      <div class="search-row"><input placeholder="Search users..."><button class="btn primary">Add New User</button></div>
      <table class="table">
        <thead><tr><th>Name</th><th>Role</th><th>Assignment</th><th>Status</th><th>Last Active</th><th>Actions</th></tr></thead>
        <tbody>${displayUsers.map(([name, role, assignment, status, last, driver_id]) => html`
          <tr>
            <td><span class="avatar" style="display:inline-grid;width:32px;height:32px;margin-right:10px;align-items:center;justify-content:center;border-radius:50%;background:#e2e8f0;font-weight:bold;font-size:12px;color:#475569;">${name.split(" ").map(n => n[0]).join("")}</span>${name}</td>
            <td>${role}</td>
            <td>${assignment}</td>
            <td>${badge(status, status === "active" ? "green" : "gray")}</td>
            <td class="meta">${last}</td>
            <td>
              ${role === "Driver" ? 
                html`<button class="btn" onclick="alert('Assignments are read-only in the Control Center. Creating and updating duties must be done by the Supervisor.')">View Assignments</button> ` : 
                html`<button class="btn">Edit</button> `
              }
              <button class="btn">Suspend</button>
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
  })).filter((route) => route.id);
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
    messageForm.addEventListener("input", () => {
      messageDraft = {
        recipients: messageForm.elements.recipients.value,
        subject: messageForm.elements.subject.value,
        body: messageForm.elements.body.value,
      };
    });
    messageForm.addEventListener("change", () => {
      messageDraft = {
        recipients: messageForm.elements.recipients.value,
        subject: messageForm.elements.subject.value,
        body: messageForm.elements.body.value,
      };
    });
  }
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", async () => {
    state.view = button.dataset.view;
    window.history.replaceState(null, "", `?view=${state.view}`);
    if (state.view === "users") {
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
setInterval(loadControlMessages, 15000);
updateClock();
if (state.view === "users") {
  loadCcUsers().then(render);
} else if (state.view === "regions") {
  Promise.all([loadRegionMeta(), loadCcRegions()]).then(render);
} else {
  render();
}
loadLiveVehicles();
loadIncidents();
loadControlMessages();
