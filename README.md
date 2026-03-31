# StudentGig

A web-based marketplace where students offer their skills and services to clients. Built with Django for a university project.

## Quick Start

```bash
uv sync
uv run python manage.py migrate        # also loads 8 initial categories automatically
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Visit `http://127.0.0.1:8000/` to see the homepage.
Visit `http://127.0.0.1:8000/admin/` for the admin panel.

## Register a User

Go to `/accounts/register/`, pick a role (Student or Client), and submit. After registering you are logged in automatically.

To transact (post a listing or place a bid), your account must be KYC-verified by an admin first.

## Run Tests

```bash
uv run pytest core/tests.py -v --cov=core --cov-report=term-missing
```

70 tests, 100% coverage.

## Team

| Member | Responsibility |
|---|---|
| Member 1 (Zanish) | Backend — models, views, admin, migrations, tests |
| Member 2 | Frontend — templates and styling |
| Member 3 | Auth — registration, profile page, review submission |

See `BACKEND_README.md` for full backend reference and `Member_2_3_instructions.md` for what Members 2 and 3 still need to build.
