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
- Four roles: **admin** (everything), **ceo** (edits order details, read-only tracker, sees the
  audit trail), **shipping_manager** (edits operational tracker data), **merchant** (uploads +
  views orders, no tracker). Every field change is recorded in a per-field audit trail.

## Run with Docker (recommended)

Everything (Postgres + backend + frontend) via `docker compose`:
```bash
cp .env.example .env      # edit secrets: JWT_SECRET, ADMIN_PASSWORD, POSTGRES_PASSWORD
docker compose up --build
```
Then open http://localhost:3000 (API on http://localhost:8000). The admin user is created on
first boot from `.env`; set `SEED_DEMO_USERS=true` to also add the ceo/shipping/merchant demo users.

Data lives in the `pgdata` volume; uploaded workbooks are scratch (parsed into Postgres on import,
never read again) and kept in the `uploads` volume.

**Behind a domain / reverse proxy:** point `NEXT_PUBLIC_API_URL` at the API's public URL and set
`CORS_ORIGINS` to the frontend's URL, then rebuild the frontend image (the API URL is baked in at
build time). Put nginx/Caddy in front for TLS.

## Run locally without Docker

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
