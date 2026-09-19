# Order & Shipment Tracker (Shipping_software_Z)

Ingests **Roman Originals** order paperwork, maintains a central **Shipment Tracker**, and reports
on it by season, customer and vendor.

- **Customer Order / Order Confirmation** sheets → buyer-side data (order qty, buyer price, style,
  colour, description, size ratio, garment spec).
- **Vendor Order** sheets → factory-side data (factory name, factory price, vendor terms, that
  factory's payment terms). One vendor workbook may stack several factory blocks.
- Uploads are reconciled into **tracker rows** keyed by *Buyer PO# + Style No. (+TopUp) + Colour*.
  Operational columns (ETD, BL, container, booking…) are filled in-app and are never overwritten by
  a re-import.
- Whatever a sheet carries is stored, whether the tracker has a column for it or not — the size
  ratio (UK size / alpha size / range), the garment spec, and a raw capture of every cell. The
  tracker stays the shipping team's fixed 56-column view; the reporting runs off the fuller store.

## Two views of the same data
- **Purchase Orders** — a PO (`D579`) the way the business talks about it: all its style/colour
  lines together, its season, its buyer and factory terms, its size ratios. Grouped into *Buyer*,
  *Vendor*, *Product* and *Shipping* details.
- **Shipment Tracker** — the shipping team's flat 56-column sheet, one row per line, with the
  spreadsheet-style Excel view and `.xlsx` export in the original layout.

## Features
- Multi-file drag & drop upload. Buyer vs vendor is decided by the sheet's **layout**, not its
  filename, and the detection is shown so it can be corrected.
- **Seasons**: every PO belongs to one. On upload we suggest it from the PO's delivery date
  (March–August = Spring/Summer, otherwise Autumn/Winter) and the merchant confirms.
- **Paste PO details**: the shipping team pastes a booking or invoice table straight out of an
  e-mail; headings are fuzzy-matched to tracker columns and previewed before anything is written.
  Works pinned to one PO or across many.
- **Customer and Vendor masters**, both self-populating from uploads.
- **Reports** by season / customer / vendor with charts, margins, shipping delays and `.xlsx` export.
- Manual tracker-row entry, and a browsable database view at `/admin` for admins.

## Who can get in

Accounts are gated three ways, all enforced server-side:

- **Email domain.** Set `ALLOWED_EMAIL_DOMAINS=auverastudio.com` and only those
  addresses may register *or* sign in — turning it on shuts out accounts that
  already exist, not just new ones. Exact domain match, so subdomains need
  listing separately. `ADMIN_EMAIL` is always allowed through, so a typo in the
  list cannot lock out the only administrator. Empty (the default) means no
  restriction, which is what local development and the tests run with.
- **Admin approval.** Registering grants nothing: new accounts land on the
  waitlist with no role until an admin assigns one.
- **Passwords** are at least 12 characters, and a handful of obvious ones are
  refused. Existing passwords are not re-checked at sign-in, so raising the rule
  locks nobody out. Five failed attempts holds the account shut for 15 minutes.

### Sessions

Signing in opens a **session**: a short-lived access token (15 minutes, renewed
silently by the frontend) plus a refresh token that the server can revoke. So
signing out actually ends the session rather than only clearing the browser, and
*Sign out everywhere* ends every session that account has open. Disabling an
account in the admin panel ends its sessions immediately.

CEO and admin see **Sign-in Activity** in the sidebar: who signed in and out and
when. It records sign-ins and deliberate sign-outs only — not failed attempts,
not IP addresses, and a session that merely expired is not an event.

## Roles

Everyone who can edit, edits everything — *except* the price columns, which are the CEO's and
admin's alone. A sheet upload still writes prices for whoever uploads it: that is the sheet's own
figure, not a hand edit.

| | Tracker | Purchase Orders | Edit prices | Upload | Paste | Seasons | Reports |
|---|---|---|---|---|---|---|---|
| **admin** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **ceo** | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ |
| **shipping_manager** | ✓ | ✓ | | | ✓ | | |
| **merchant** | | ✓ | | ✓ | | ✓ | |

Merchants can also **create** a tracker row by hand (*Manual PO Line*), which
sets its Buyer PO / Style / Colour. Creating is a separate right from editing:
having set that identity once, a merchant can never change it again, and still
cannot browse or edit the rest of the tracker. Shipping managers are the mirror
image — they edit rows but do not originate them.

A row's Buyer PO / Style / Colour is CEO+admin only too — changing it re-keys the row and would
break re-import matching. Every field change is recorded in a per-field audit trail, whether it
arrives by upload, by hand or by paste.

## Run with Docker (recommended)

Everything (Postgres + backend + frontend) via `docker compose`:
```bash
cp .env.example .env      # edit secrets: JWT_SECRET, ADMIN_PASSWORD, POSTGRES_PASSWORD
docker compose up --build
```
Then open http://localhost:3000 (API on http://localhost:8000). The admin (`ADMIN_EMAIL`) is created
on first boot, and its password is kept in sync with `ADMIN_PASSWORD` on every boot — so to change it,
edit `.env` and run `docker compose up -d --build backend`. Set `SEED_DEMO_USERS=true` to also add the
ceo/shipping/merchant demo users (their passwords are seed-only, not synced).

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

### Schema changes

There are no migrations yet. `create_all` on startup only ever **adds** tables — it never alters an
existing one — so after a model gains a column the old table stays the old shape and every query
against it 500s. In the browser that surfaces as a *CORS* error, because a 500 escapes past the CORS
middleware; `GET /api/health/schema` says plainly whether the live database matches the models.

While the data is still throwaway, rebuild it:

```bash
cd backend
uv run python -m app.rebuild_schema --yes    # DROPS every table, users included, then re-seeds
```

On a host with no shell (Render, Fly), set `REBUILD_SCHEMA=true`, redeploy once, then **unset it** —
otherwise every future deploy wipes the database.

Once there is data worth keeping this stops being acceptable and the project needs real migrations;
Alembic is already a declared dependency.
