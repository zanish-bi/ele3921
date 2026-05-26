# StudentGig — Backend Reference

## Tech Stack

- **Framework:** Django 6
- **Database:** SQLite (development)
- **Package manager:** uv
- **Test runner:** pytest + pytest-django + pytest-cov

---

## Setup

```bash
cd studentgig
uv sync
uv run python manage.py migrate        # applies all migrations and loads 8 initial categories
uv run python manage.py seed           # creates test users, listings, job request, contracts, reviews
uv run python manage.py runserver
```

Or just run `./start.sh` (Linux/Mac), `start.bat` (Windows CMD), or `pwsh start.ps1`.

---

## Running Tests

```bash
uv run pytest core/tests.py -v --tb=short
```

284 tests — models, admin, forms, views, role guards, and 13 workflow scenarios.

---

## Data Models

### How Django's built-in User is extended

Django's `User` model handles authentication only. Every `User` automatically gets a `UserProfile` created by a `post_save` signal on first save. The `UserProfile` holds all application-level data (`role`, `bio`, `is_kyc_verified`).

```
Django built-in:
  User  ─── auth_user table (id, username, password, is_staff, is_superuser, ...)

Extended:
  UserProfile  ─── core_userprofile table
                   user_id (OneToOne → auth_user.id)
                   role  ('student' | 'client')
                   bio
                   is_kyc_verified
```

### Full model chain

```
User (Django auth_user)
 └── UserProfile (role, KYC, bio)  ← auto-created by post_save signal

Two parallel market sides:
  ── Gig market ─────────────────────────────────────────────────────
  UserProfile (student)
    └── ServiceListing  ← student posts this
          └── Bid        ← client sends this
                └── Contract (bid=this, job_bid=None)
                      ├── Payment   (escrow simulation)
                      ├── Review    (up to 2 per contract)
                      └── ContractMessage[]

  ── Job market ─────────────────────────────────────────────────────
  UserProfile (client)
    └── JobRequest   ← client posts this
          └── JobBid  ← student sends this
                └── Contract (bid=None, job_bid=this)
                      ├── Payment
                      ├── Review
                      └── ContractMessage[]

  ── Inbox ──────────────────────────────────────────────────────────
  Notification  ← recipient (UserProfile), message, url, is_read

Category ──── ServiceListing  (many listings per category)
Category ──── JobRequest      (many jobs per category)
```

### Models summary

| Model | Key fields |
|---|---|
| `UserProfile` | user (OneToOne→User), role (`student`/`client`), bio, is_kyc_verified |
| `Category` | name, description |
| `ServiceListing` | owner (FK→UserProfile), category, title, description, price, is_remote, is_active |
| `Bid` | listing, client (FK→UserProfile), proposed_price, message, status |
| `JobRequest` | client (FK→UserProfile), category, title, description, budget, is_active |
| `JobBid` | job_request, student (FK→UserProfile), proposed_price, message, status |
| `Contract` | bid (nullable OneToOne), job_bid (nullable OneToOne), student, client, agreed_price, status, admin_note, completed_at |
| `Payment` | contract (OneToOne), amount, status (`held`/`released`/`refunded`) |
| `Review` | contract, reviewer, reviewee (both FK→UserProfile), rating (1–5), comment — **unique per (contract, reviewer)** |
| `ContractMessage` | contract, sender (FK→UserProfile), body, created_at |
| `Notification` | recipient (FK→UserProfile), message, url, is_read, created_at |

### Pre-loaded Categories (migration 0003)

`Design`, `Programming`, `Tutoring`, `Writing`, `Video & Animation`, `Translation`, `Marketing`, `Data & Research`

---

## URL Reference

### Service Listings

| Method | URL | View name | Access |
|---|---|---|---|
| GET | `/listings/` | `listing_list` | Public |
| GET/POST | `/listings/create/` | `listing_create` | Login + student + KYC |
| GET | `/listings/<pk>/` | `listing_detail` | Public |
| GET/POST | `/listings/<pk>/edit/` | `listing_edit` | Login + owner |
| GET/POST | `/listings/<pk>/bid/` | `place_bid` | Login + client + KYC |
| POST | `/bids/<pk>/accept/` | `bid_accept` | Login + listing owner |
| POST | `/bids/<pk>/reject/` | `bid_reject` | Login + listing owner |
| GET/POST | `/bids/<pk>/edit/` | `bid_edit` | Login + bid owner + pending |
| POST | `/bids/<pk>/delete/` | `bid_delete` | Login + bid owner + pending |

### Job Requests

| Method | URL | View name | Access |
|---|---|---|---|
| GET | `/jobs/` | `job_request_list` | Public |
| GET/POST | `/jobs/create/` | `job_request_create` | Login + client + KYC |
| GET | `/jobs/<pk>/` | `job_request_detail` | Public |
| GET/POST | `/jobs/<pk>/bid/` | `job_bid_create` | Login + student + KYC |
| POST | `/job-bids/<pk>/accept/` | `job_bid_accept` | Login + job owner (client) |
| POST | `/job-bids/<pk>/reject/` | `job_bid_reject` | Login + job owner (client) |

### Contracts

| Method | URL | View name | Access |
|---|---|---|---|
| GET | `/contracts/` | `contracts` | Login |
| GET | `/contracts/<pk>/` | `contract_detail` | Login + contract party |
| POST | `/contracts/<pk>/complete/` | `contract_complete` | Login + student on contract |
| POST | `/contracts/<pk>/accept/` | `contract_accept` | Login + client on contract |
| POST | `/contracts/<pk>/reject/` | `contract_reject` | Login + client on contract |
| GET/POST | `/contracts/<pk>/review/` | `review_create` | Login + contract party + completed |
| POST | `/contracts/<pk>/message/` | `contract_message_create` | Login + contract party |

### Other

| Method | URL | View name | Access |
|---|---|---|---|
| GET | `/` | `home` | Public |
| GET | `/profiles/<user_pk>/` | `profile_detail` | Public |
| GET | `/dashboard/` | `dashboard` | Login |
| GET | `/notifications/` | `notifications_list` | Login |
| POST | `/notifications/mark-read/` | `notifications_mark_read` | Login |
| POST | `/accounts/kyc-verify/` | `kyc_self_verify` | Login (test mode) |
| GET/POST | `/accounts/register/` | `register` | Public |
| GET/POST | `/accounts/login/` | Django built-in | Public |
| POST | `/accounts/logout/` | Django built-in | Login |

---

## Business Logic

### UserProfile Auto-Creation

A `post_save` signal on `User` (in `core/signals.py`) automatically creates a `UserProfile` whenever a new user is saved. The registration view then sets the chosen role. Every `User` always has a `UserProfile`.

### KYC Gate

Both students and clients must be KYC-verified before transacting:
- **Students** need `is_kyc_verified = True` to create a listing or bid on a job
- **Clients** need `is_kyc_verified = True` to place a bid on a listing or post a job request

In production, KYC is toggled by an admin. For testing, `kyc_self_verify` (POST `/accounts/kyc-verify/`) sets it True immediately — accessible via the "Simulate KYC Verification" button shown to unverified users.

### Gig Bid Acceptance Flow (`POST /bids/<pk>/accept/`)

When a student accepts a bid, atomically:
1. `bid.status` → `"accepted"`
2. `listing.is_active` → `False`
3. All other pending bids on the same listing → `"rejected"`
4. `Contract` created: `status="active"`, `agreed_price` from bid, `bid=<this bid>`, `job_bid=None`
5. `Payment` created: `status="held"`, `amount` from contract

### Job Bid Acceptance Flow (`POST /job-bids/<pk>/accept/`)

Mirrors the gig flow:
1. `job_bid.status` → `"accepted"`
2. `job_request.is_active` → `False`
3. All other pending bids on the same job → `"rejected"`
4. `Contract` created: `status="active"`, `bid=None`, `job_bid=<this bid>`
5. `Payment` created: `status="held"`

### Delivery Flow

```
Student: POST /contracts/<pk>/complete/
  contract.status → "delivered"   (payment stays "held")

Client: POST /contracts/<pk>/accept/
  contract.status → "completed"
  contract.completed_at → now()
  payment.status → "released"     (Payment.save() auto-sync)

Client: POST /contracts/<pk>/reject/
  contract.status → "disputed"
  payment.status stays "held"
```

### Payment / Contract Sync (`Payment.save()` override)

`Payment.save()` in `models.py` watches for status changes and syncs the parent contract:
- `payment.status = "released"` → `contract.status = "completed"`
- `payment.status = "refunded"` → `contract.status = "disputed"` (only if not already completed)

This ensures that when an admin changes a payment directly (e.g., via the admin inline), the contract status updates automatically.

`ContractAdmin.save_model()` in `admin.py` syncs the payment when an admin directly changes `contract.status`:
- `contract.status = "completed"` → `payment.status = "released"`
- `contract.status = "disputed"` → `payment.status = "refunded"`

### Dual Contract Type Abstraction

`Contract` has two nullable foreign keys:
- `bid` (OneToOne → `Bid`) — set for gig contracts, None for job contracts
- `job_bid` (OneToOne → `JobBid`) — set for job contracts, None for gig contracts

Two properties abstract this for templates:
- `contract.listing_title` → `bid.listing.title` or `job_bid.job_request.title`
- `contract.bid_message` → `bid.message` or `job_bid.message`

### Notification Helper

`_notify(recipient, message, url)` in `views.py` creates a `Notification` object. Called on:
- Bid placed → listing owner notified
- Bid accepted/rejected → bidder notified
- Work submitted → client notified
- Delivery accepted/disputed → student notified
- Contract message sent → other party notified

The context processor `core.context_processors.notifications` injects `unread_notifications_count` into every template context (used by the navbar bell).

### Review Constraint

`Review` has `unique_together = [("contract", "reviewer")]`. The `review_create` view returns HTTP 400 if the reviewer already reviewed that contract.

---

## Admin Panel (`/admin/`)

Default credentials after seeding: **`admin` / `admin`**

| Model | Key admin capabilities |
|---|---|
| `UserProfile` | Bulk action: "Toggle KYC verified status" |
| `Contract` | Bulk actions: "Release payment (resolve dispute)" and "Refund payment (resolve dispute)"; payment inline; filter by status |
| `ServiceListing` | Bids inline |
| `JobRequest` | Browsable with client info |
| `Category` | Add/edit/remove categories |
| All other models | Standard CRUD |

### Resolving Disputes via Admin

1. Go to `/admin/core/contract/`
2. Filter by `status = disputed` using the right sidebar
3. Select the contract(s)
4. Choose action: **Release payment** (in favour of student) or **Refund payment** (in favour of client)
5. Optionally open the contract and set `admin_note` — this text appears on the contract detail page for both parties

---

## Seed Command

```bash
uv run python manage.py seed
```

Creates test users, listings, an active contract, a completed contract with review, one open job request, and a superuser. Idempotent — safe to run multiple times.

| Username | Password | Role | KYC |
|---|---|---|---|
| student1 | pass1234 | Student | Verified |
| student2 | pass1234 | Student | Pending |
| client1 | pass1234 | Client | Verified |
| admin | admin | Superuser | — |

---

## Authentication

| Feature | Status |
|---|---|
| `/accounts/login/` | Django built-in + styled `registration/login.html` |
| `/accounts/logout/` | Django built-in |
| `/accounts/register/` | Custom view + `UserRegisterForm` with role selection |
| UserProfile auto-created on registration | Signal in `core/signals.py` |
| `LOGIN_REDIRECT_URL` | `/` |
| `LOGOUT_REDIRECT_URL` | `/accounts/login/` |

---

## Out of Scope / Simplifications

| Item | Decision |
|---|---|
| Real payment processing | Simulated escrow via `Payment.status` field only |
| Email notifications | In-app `Notification` objects only — no SMTP |
| Real-time messaging | Page-refresh message thread — no WebSockets |
| Document upload for KYC | Admin toggle + test-mode button only |
| Rating-based listing/job filtering | Not implemented |
| Mobile-first responsive design | Basic responsive layout only |
| Password reset / change | Not implemented |
| OAuth / social login | Not implemented |
| File attachment for work delivery | Status toggle only — no file upload |
| Automated KYC verification | Manual admin action only |
