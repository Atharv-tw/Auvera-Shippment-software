# Order & Shipment Tracker (Shipping_software_Z)

Ingests **Roman Originals** order paperwork and maintains a central **Shipment Tracker**.

- **Customer Order / Order Confirmation** sheets → buyer-side data (order qty, buyer price, style, colour, description).
- **Vendor Order** sheets → factory-side data (factory name, factory price, vendor terms). One vendor
  workbook may stack several factory blocks.
- Uploads are reconciled into **tracker rows** keyed by *Buyer PO# + Style No. (+TopUp) + Colour*.
  Operational columns (ETD, BL, container, booking…) are filled in-app and are never overwritten by
  a re-import.

## Features
- Multi-file drag & drop upload (customer vs vendor auto-detected).
- Dashboard: orders, vendor orders, tracker summary.
- Shipment Tracker: editable AG-Grid **Excel view** + per-row **Field view**; `.xlsx` export in the
  original tracker layout.
- Manual tracker-row entry.
- Login with admin / vendor roles (admin uploads & deletes; vendors view & edit).

## Run

Backend (FastAPI, SQLite via `uv`):
```bash
cd backend
uv sync
uv run python -m app.seed        # creates admin@example.com / admin12345
uv run uvicorn app.main:app --port 8000
```

Frontend (Next.js):
```bash
cd frontend
npm install
cp .env.example .env.local       # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                       # http://localhost:3000
```

Backend tests: `cd backend && uv run pytest`

Reset just the order / vendor / tracker data (keeps user logins & roles):
```bash
cd backend
uv run python -m app.reset_data          # prompts first; add --yes to skip
```
