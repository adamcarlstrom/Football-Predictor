# Frontend: React & TypeScript UI

The frontend of this application serves as an interactive dashboard, taking inspiration from modern sports analytics platforms to present complex tournament data clearly.

## Tech Stack

* Framework: React 18 (via Vite for HMR)

* Language: TypeScript (for strict typing of API payloads and bracket arrays)

* Styling: Inline CSS and native CSS Grid

## Core Mechanics & Features

### Tabbed State Management

The application is divided into two primary views managed by React state:

* Daily Games Feed: A date-based browser that queries the backend for specific historical, live, or upcoming fixtures.

* Tournament Predictor: A macro-view that renders the entire 48-team Group Stage and the subsequent Knockout Bracket.

### The Daily Feed & Dynamic Timezones



The UI allows users to navigate through the tournament day-by-day.

* Utilizes the native HTML5 ```<input type="date">``` component.

* Leverages React's useEffect dependency array so that changing the date automatically triggers a re-fetch of the data without requiring a manual submit action.

* Processes ISO-8601 timestamps dynamically, utilizing toLocaleTimeString() to convert UTC kickoff times into the user's localized browser timezone natively.

### Responsive CSS Grid Layout

To handle dense data arrays without overwhelming the viewport with vertical scrolling, the Match Cards utilize grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)). This ensures the dashboard stacks single columns on mobile devices and expands to multiple columns on larger displays.

### Interactive API Syncing

Because the backend operates on a Cache-First architecture, the frontend features a "Force API Sync" button. This sends a strict command bypassing local browser caches (cache: 'no-store') to trigger the backend's data-reconciliation scripts, reflecting newly finished scorelines on the UI.
