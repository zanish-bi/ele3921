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
uv run python manage.py seed           # creates test users, listings, contracts, reviews
uv run python manage.py createsuperuser  # optional — seed already creates admin/admin
uv run python manage.py runserver
```

Or just run `./start.sh` (Linux/Mac), `start.bat` (Windows CMD), or `pwsh start.ps1`.

---

## Running Tests

```bash
uv run pytest core/tests.py -v --cov=core --cov-report=term-missing
```

70 tests, 100% coverage across models, admin, forms, signals, and views.

---

## Data Model Chain

```
User (Django built-in)
 └── UserProfile (role, KYC flag, bio)  ← auto-created by signal on every User save
      └── ServiceListing (student posts this)
           └── Bid (client sends this on a listing)
                └── Contract (created when bid is accepted)
                     ├── Payment (one per contract, tracks escrow state)
                     └── Review (up to two per contract, one from each side)

Category ──── ServiceListing (many listings per category)
```

### Models summary

| Model | Key fields |
|---|---|
| `UserProfile` | user (OneToOne, related_name=`userprofile`), role (`student`/`client`), bio, is_kyc_verified |
| `Category` | name, description |
| `ServiceListing` | owner, category, title, description, price, is_remote, is_active |
| `Bid` | listing, client, proposed_price, message, status (`pending`/`accepted`/`rejected`) |
| `Contract` | bid (OneToOne), student, client, agreed_price, status (`active`/`completed`/`disputed`), completed_at |
| `Payment` | contract (OneToOne), amount, status (`held`/`released`/`refunded`) |
| `Review` | contract, reviewer, reviewee, rating (1–5), comment — **unique per (contract, reviewer)** |

### Pre-loaded Categories (migration 0003)

`Design`, `Programming`, `Tutoring`, `Writing`, `Video & Animation`, `Translation`, `Marketing`, `Data & Research`

---

## URL Reference

| Method | URL | View | Access |
|---|---|---|---|
| GET | `/` | `home` | Public |
| GET | `/listings/` | `listing_list` | Public |
| GET/POST | `/listings/create/` | `listing_create` | Login + student + KYC |
| GET | `/listings/<pk>/` | `listing_detail` | Public (owner also sees bids) |
| GET/POST | `/listings/<pk>/bid/` | `place_bid` | Login + client + KYC |
| POST | `/bids/<pk>/accept/` | `bid_accept` | Login + listing owner |
| POST | `/bids/<pk>/reject/` | `bid_reject` | Login + listing owner |
| GET | `/contracts/` | `contracts` | Login |
| GET | `/contracts/<pk>/` | `contract_detail` | Login + contract party |
| POST | `/contracts/<pk>/complete/` | `contract_complete` | Login + student on contract |
| GET/POST | `/contracts/<pk>/review/` | `review_create` | Login + contract party + completed |
| GET | `/profiles/<user_pk>/` | `profile_detail` | Public |
| POST | `/accounts/kyc-verify/` | `kyc_self_verify` | Login (test-mode only) |
| GET/POST | `/accounts/register/` | `register` | Public |
| GET/POST | `/accounts/login/` | Django built-in | Public |
| POST | `/accounts/logout/` | Django built-in | Login |

---

## Business Logic

### UserProfile Auto-Creation

A `post_save` signal on `User` automatically creates a `UserProfile` with no role when any new user is saved. The registration view then sets the chosen role. Every `User` always has a `UserProfile`.

### KYC Gate

Both students and clients must be KYC-verified before transacting:
- **Students** need `is_kyc_verified = True` to create a listing
- **Clients** need `is_kyc_verified = True` to place a bid

In production, KYC is toggled by an admin in the Django admin panel. For testing, the `kyc_self_verify` view (POST `/accounts/kyc-verify/`) sets `is_kyc_verified = True` for the logged-in user — accessible via the "Simulate KYC Verification" button shown to unverified users.

### Bid Acceptance Flow (`POST /bids/<pk>/accept/`)
When a student accepts a bid, atomically:
1. `bid.status` → `"accepted"`
2. `listing.is_active` → `False`
3. All other pending bids on the same listing → `"rejected"`
4. A `Contract` is created: `status="active"`, `agreed_price` copied from bid
5. A `Payment` is created: `status="held"`, `amount` copied from contract

Redirects to the new contract's detail page.

### Contract Completion Flow (`POST /contracts/<pk>/complete/`)
Only the student can mark a contract complete:
1. `contract.status` → `"completed"`
2. `contract.completed_at` → current timestamp
3. `contract.payment.status` → `"released"`

After completion, both parties see a "Leave a Review" button on the contract detail page.

### Review Constraint

`Review` has `unique_together = [("contract", "reviewer")]`. The `review_create` view enforces this: it returns HTTP 400 if the user has already reviewed the contract.

### Payment States
```
held → released  (contract completed by student)
held → refunded  (dispute resolution — set manually in admin)
```

---

## Admin Panel (`/admin/`)

All models are registered. Key capabilities:

- **UserProfile** — toggle KYC via bulk action "Toggle KYC verified status"
- **Category** — add/edit/remove categories
- **ServiceListing** — view with bids inline
- **Contract** — view with payment inline

Default admin credentials after seeding: `admin` / `admin`

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

## Seed Command

```bash
uv run python manage.py seed
```

Creates test users, listings, an active contract, a completed contract with a review, and an admin superuser. Idempotent — safe to run multiple times.

| Username | Password | Role | KYC |
|---|---|---|---|
| student1 | pass1234 | Student | Verified |
| student2 | pass1234 | Student | Pending |
| client1 | pass1234 | Client | Verified |
| admin | admin | Superuser | — |

---

## Out of Scope

- Real payment processing
- Email notifications
- Real-time messaging
- Document upload for KYC
- Mobile responsiveness
- Automated KYC verification
