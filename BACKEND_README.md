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
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

The superuser account is used to access the Django admin panel at `/admin/`.

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
 └── UserProfile (role, KYC flag)  ← auto-created by signal on every User save
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

### Pre-loaded Categories

The following 8 categories are loaded automatically when `migrate` is first run (migration 0003):

| Category | Description |
|---|---|
| Design | Graphic design, UI/UX, branding, and visual assets |
| Programming | Web development, apps, scripts, and software |
| Tutoring | Academic subjects, test prep, and skill coaching |
| Writing | Essays, copywriting, technical writing, and editing |
| Video & Animation | Video editing, motion graphics, and animation |
| Translation | Document translation and multilingual content |
| Marketing | Social media, SEO, and digital marketing |
| Data & Research | Data analysis, surveys, and research assistance |

Additional categories can be added at any time via the admin panel at `/admin/core/category/`.

---

## URL Reference

| Method | URL | View | Access |
|---|---|---|---|
| GET | `/` | `home` | Public — landing page |
| GET | `/listings/` | `listing_list` | Public |
| GET | `/listings/create/` | `listing_create` | Login + student role + KYC |
| GET | `/listings/<pk>/` | `listing_detail` | Public (owner also sees bids) |
| GET/POST | `/listings/<pk>/bid/` | `bid_create` | Login + client role + KYC |
| POST | `/bids/<pk>/accept/` | `bid_accept` | Login + listing owner |
| POST | `/bids/<pk>/reject/` | `bid_reject` | Login + listing owner |
| GET | `/contracts/<pk>/` | `contract_detail` | Login + contract party |
| POST | `/contracts/<pk>/complete/` | `contract_complete` | Login + student on contract |
| GET | `/dashboard/` | `dashboard` | Login |
| GET/POST | `/accounts/register/` | `register` | Public |
| GET/POST | `/accounts/login/` | Django built-in | Public |
| POST | `/accounts/logout/` | Django built-in | Login |

---

## Business Logic

### UserProfile Auto-Creation

A `post_save` signal on `User` automatically creates a `UserProfile` with no role when any new user is saved. The registration view then updates the profile with the chosen role. This means every `User` in the system always has a `UserProfile`.

### KYC Gate

Both students and clients must be KYC-verified before transacting:
- **Students** need `is_kyc_verified = True` to create a listing
- **Clients** need `is_kyc_verified = True` to place a bid

KYC is set manually by an admin in the Django admin panel. There is no self-service verification — this is a boolean flag that only admins can flip.

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

### Review Constraint
A reviewer can only submit one review per contract (`unique_together` on `contract` + `reviewer`). Member 3 must enforce this check in the review submission view before saving.

---

## Admin Panel (`/admin/`)

All models are registered. Key admin capabilities:

- **UserProfile** — toggle KYC verified status via bulk action ("Toggle KYC verified status"). This is the only way to approve a user's KYC.
- **Category** — add, edit, or remove categories at any time
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

Auth URLs are fully wired. The following are all working:

| Feature | Status |
|---|---|
| `/accounts/login/` | Working (Django built-in view + `registration/login.html`) |
| `/accounts/logout/` | Working (Django built-in view) |
| `/accounts/register/` | Working (`register` view + `registration/register.html`) |
| UserProfile auto-created on registration | Working (signal in `core/signals.py`) |
| `LOGIN_REDIRECT_URL` | `/` (homepage) |
| `LOGOUT_REDIRECT_URL` | `/accounts/login/` |

**Still needed from Member 3:** profile page view, review submission view. See `Member_2_3_instructions.md`.

---

## What Is Out of Scope

- Real payment processing
- Email notifications
- Real-time messaging
- Document upload for KYC (replaced by boolean flag)
- Mobile responsiveness
- Automated KYC verification
