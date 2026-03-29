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
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

The superuser account is used to access the Django admin panel at `/admin/`.

---

## Running Tests

```bash
uv run pytest core/tests.py -v --cov=core --cov-report=term-missing
```

66 tests, 100% coverage across models, admin, forms, and views.

---

## Data Model Chain

```
User (Django built-in)
 └── UserProfile (role, KYC flag)
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
| `UserProfile` | user (OneToOne), role (`student`/`client`), bio, is_kyc_verified |
| `Category` | name, description |
| `ServiceListing` | owner, category, title, description, price, is_remote, is_active |
| `Bid` | listing, client, proposed_price, message, status (`pending`/`accepted`/`rejected`) |
| `Contract` | bid (OneToOne), student, client, agreed_price, status (`active`/`completed`/`disputed`), completed_at |
| `Payment` | contract (OneToOne), amount, status (`held`/`released`/`refunded`) |
| `Review` | contract, reviewer, reviewee, rating (1–5), comment |

---

## URL Reference

All core URLs are prefixed with the project root (no sub-prefix). Add auth URLs separately (see below).

| Method | URL | View | Access |
|---|---|---|---|
| GET | `/listings/` | `listing_list` | Public |
| GET | `/listings/create/` | `listing_create` | Login + student role + KYC |
| GET | `/listings/<pk>/` | `listing_detail` | Public (owner also sees bids) |
| GET/POST | `/listings/<pk>/bid/` | `bid_create` | Login + client role + KYC |
| POST | `/bids/<pk>/accept/` | `bid_accept` | Login + listing owner |
| POST | `/bids/<pk>/reject/` | `bid_reject` | Login + listing owner |
| GET | `/contracts/<pk>/` | `contract_detail` | Login + contract party |
| POST | `/contracts/<pk>/complete/` | `contract_complete` | Login + student on contract |
| GET | `/dashboard/` | `dashboard` | Login |

---

## Business Logic

### KYC Gate
Both students and clients must be KYC-verified before transacting:
- **Students** need `is_kyc_verified = True` to create a listing
- **Clients** need `is_kyc_verified = True` to place a bid

KYC is set manually by an admin in the Django admin panel. There is no document upload — this is a boolean flag simulating the verification step.

### Bid Acceptance Flow (`POST /bids/<pk>/accept/`)
When a student accepts a bid, the following happens atomically in the view:
1. `bid.status` → `"accepted"`
2. `listing.is_active` → `False` (prevents new bids)
3. All other pending bids on the same listing → `"rejected"` (bulk update)
4. A `Contract` is created: `status="active"`, `agreed_price` copied from bid
5. A `Payment` is created: `status="held"`, `amount` copied from contract

Redirects to the new contract's detail page.

### Contract Completion Flow (`POST /contracts/<pk>/complete/`)
Only the student can mark a contract complete:
1. `contract.status` → `"completed"`
2. `contract.completed_at` → current timestamp
3. `contract.payment.status` → `"released"`

Redirects back to the contract detail page.

### Payment States
```
held → released  (contract completed normally)
held → refunded  (dispute resolution — set manually in admin for now)
```

---

## Admin Panel (`/admin/`)

All models are registered. Key admin capabilities:

- **UserProfile** — toggle KYC verified status via bulk action ("Toggle KYC verified status"). This is how users get approved.
- **ServiceListing** — view/edit listings with bids inline
- **Contract** — view contracts with payment inline
- All models have `list_filter` and `list_display` configured for quick navigation

To approve a user's KYC:
1. Go to `/admin/core/userprofile/`
2. Select the profile(s)
3. Choose "Toggle KYC verified status" from the Actions dropdown
4. Click Go

---

## Authentication

`@login_required` is applied to all write views. Unauthenticated requests are redirected to `/accounts/login/`.

**Login/register/logout are NOT implemented in this backend.** These are Member 3's responsibility. Member 3 must register auth URLs so that the redirect from `@login_required` resolves. See `Member_2_3_instructions.md` for details.

---

## What Is Out of Scope

- Real payment processing
- Email notifications
- Real-time messaging
- Document upload for KYC (replaced by boolean flag)
- Mobile responsiveness
- Automated KYC verification
