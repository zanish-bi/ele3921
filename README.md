# StudentGig

A student freelance marketplace where students offer services and clients hire them. Built with Django 6 as a university project.

---

## Quick Start (Any Platform)

### Prerequisites — install `uv` once

| Platform | Command |
|---|---|
| Linux / macOS | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Windows (PowerShell) | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Any (pip) | `pip install uv` |

`uv` handles Python version management automatically — you do **not** need to install Python 3.13 separately.

### Start the server

```bash
# Clone the repo
git clone https://github.com/zanish-bi/ele3921.git
cd ele3921/studentgig

# Linux / macOS
./start.sh

# Windows (Command Prompt)
start.bat

# Windows (PowerShell) or cross-platform
pwsh start.ps1
```

On first run the script will:
1. Install all Python dependencies into a local `.venv`
2. Apply all database migrations (creates `db.sqlite3`)
3. Seed the database with test users, listings, contracts, and reviews
4. Start the development server at **http://127.0.0.1:8000**

### Manual setup (pip fallback — no uv)

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
python manage.py migrate
python manage.py seed
python manage.py runserver
```

---

## Test Accounts

After running the start script or `python manage.py seed`:

| Username | Password | Role | KYC |
|---|---|---|---|
| `student1` | `pass1234` | Student | Verified — has active listings and contracts |
| `student2` | `pass1234` | Student | **Pending** — demo the KYC test-mode button |
| `client1` | `pass1234` | Client | Verified — has bids and contracts |
| `admin` | `admin` | Superuser | Django admin at `/admin/` |

### KYC Test Mode

Real KYC is set by an admin in the Django admin panel. For testing, every unverified user sees a **"Simulate KYC Verification (Test Mode)"** button on their dashboard and home page — one click and they can post listings or place bids immediately.

---

## Key URLs

| URL | What it does |
|---|---|
| `/` | Home / landing page |
| `/listings/` | Browse all active listings |
| `/listings/create/` | Post a new service (student, KYC required) |
| `/listings/<pk>/` | Listing detail + bid management for owner |
| `/listings/<pk>/bid/` | Place a bid (client, KYC required) |
| `/contracts/` | All your contracts (active + completed) |
| `/contracts/<pk>/` | Contract detail |
| `/contracts/<pk>/review/` | Leave a review (completed contracts only) |
| `/profiles/<user_pk>/` | Public user profile |
| `/dashboard/` | Your dashboard with contract summary |
| `/accounts/register/` | Register as student or client |
| `/accounts/login/` | Login |
| `/admin/` | Django admin panel |

---

## Running Tests

```bash
uv run pytest core/tests.py -v --cov=core --cov-report=term-missing
```

70 tests, 100% coverage across models, admin, forms, signals, and views.

---

## Project Structure

```
studentgig/
├── core/
│   ├── models.py          # All 7 data models
│   ├── views.py           # All views (backend + Member 3 additions)
│   ├── forms.py           # BidForm, ServiceListingForm, UserRegisterForm, ReviewForm
│   ├── urls.py            # URL patterns
│   ├── admin.py           # Admin configuration with KYC bulk action
│   ├── signals.py         # UserProfile auto-creation on User save
│   ├── tests.py           # 70 tests, 100% coverage
│   ├── templates/
│   │   ├── core/          # All page templates (base.html + 10 pages)
│   │   └── registration/  # login.html, register.html
│   └── management/
│       └── commands/
│           └── seed.py    # Test data seed command
├── studentgig/
│   ├── settings.py
│   └── urls.py
├── requirements.txt       # pip-compatible dependency list
├── pyproject.toml         # uv / project metadata
├── start.sh               # Linux/macOS launcher
├── start.bat              # Windows CMD launcher
└── start.ps1              # Windows PowerShell / cross-platform launcher
```

---

## Team

| Member | Responsibility | Status |
|---|---|---|
| Member 1 (Zanish) | Backend — models, views, admin, migrations, 70 tests | Complete |
| Member 2 | Frontend — all HTML templates, CSS, base layout | Complete |
| Member 3 | Auth — profile page, review submission, ReviewForm | Complete |

See `BACKEND_README.md` for the full backend reference.
