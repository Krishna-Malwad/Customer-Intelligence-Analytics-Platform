# Premium Customer Intelligence Frontend

This frontend is the redesigned presentation layer for the existing Customer Intelligence Platform.

## Design goals
- Business-first language instead of ML/engineering jargon
- Executive overview as the default landing page
- Customer 360 as a guided customer story
- AI Business Assistant as a first-class product feature
- Operations view for delivery, products and satisfaction
- Technical health isolated into System Health
- Responsive layout for desktop, tablet and mobile
- All displayed business metrics are fetched from the existing FastAPI endpoints; no demo business values are hardcoded.

## Run
From this folder:
```powershell
npm install
npm start
```

The backend should be running at `http://localhost:8000`.

Optional frontend environment variable:
`REACT_APP_API_URL=http://localhost:8000`

## Pages
1. Overview
2. Customers
3. Customer 360
4. Operations
5. AI Assistant
6. System Health

The existing backend, ML models, GenAI layer and database are unchanged.
