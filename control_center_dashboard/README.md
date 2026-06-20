# IZEE Control Center Dashboard

This folder contains a standalone web prototype for the IZEE Control Center dashboard.

It is intentionally dependency-free for now:

- `index.html` defines the dashboard shell.
- `styles.css` contains the responsive visual system.
- `app.js` renders the Dashboard, Live Map, Analytics, Incidents, Communications, Users, Configuration, and Logs & Reports screens.

Open `index.html` directly in a browser to preview it. The current data is static UI data and should later be replaced with real REST/WebSocket calls when the backend dashboard endpoints are implemented.
