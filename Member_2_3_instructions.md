# Member 2 & 3 Integration Instructions

This document tells you exactly what each member needs to build and how to plug into the existing backend. Member 1's backend (models, views, URLs, admin) is complete and tested. Do not modify `core/models.py`, `core/views.py`, `core/urls.py`, or `core/admin.py` unless coordinating with Member 1 (Zanish).

---

## Member 2 — Frontend Templates

### What's already done
All views exist and work. Minimal skeleton templates are in `core/templates/core/`. Your job is to replace those skeletons with properly styled HTML. The backend will pass the same context variables regardless of how the template looks.

### Rules
- Keep the same file names — the views reference these paths exactly
- Do not rename URLs or add new URL patterns (talk to Member 1 if you need a new route)
- You can add a `base.html` and use `{% extends "core/base.html" %}` in each template
- Use `{% url 'name' %}` for all links — never hardcode paths
- All forms must include `{% csrf_token %}` inside `<form method="post">` tags

### Template file locations

All templates live in `core/templates/core/`. The six files you need to style are:

---

#### `listing_list.html`
**Context variables:**
- `listings` — QuerySet of active `ServiceListing` objects. Each has: `.title`, `.description`, `.price`, `.category.name`, `.owner`, `.is_remote`, `.pk`
- `categories` — QuerySet of all `Category` objects. Each has: `.name`, `.pk`

**What to build:**
- A grid or list of listing cards
- A category filter form (`GET` to the same URL with `?category=<pk>`)
- A "Post a Service" link to `{% url 'listing_create' %}` (show only if `user.is_authenticated`)
- A "Dashboard" link to `{% url 'dashboard' %}` (show only if `user.is_authenticated`)

---

#### `listing_detail.html`
**Context variables:**
- `listing` — a `ServiceListing` object with: `.title`, `.description`, `.price`, `.is_remote`, `.category.name`, `.owner`, `.is_active`, `.pk`
- `bids` — either `None` (if viewer is not the listing owner) or a QuerySet of `Bid` objects. Each bid has: `.client`, `.proposed_price`, `.message`, `.status`, `.pk`

**What to build:**
- Full listing details
- A "Place a Bid" link to `{% url 'bid_create' listing.pk %}` — show only if `listing.is_active and user.is_authenticated`
- If `bids is not None`: show the bids table with Accept/Reject buttons (POST forms to `{% url 'bid_accept' bid.pk %}` and `{% url 'bid_reject' bid.pk %}`)
  - Only show Accept/Reject buttons for bids where `bid.status == "pending"`

---

#### `listing_create.html`
**Context variables:**
- `form` — a `ServiceListingForm` (renders category dropdown, title, description, price, is_remote)

**What to build:**
- A form page with `{{ form.as_p }}` or manual field rendering
- Submit button, cancel link back to `{% url 'listing_list' %}`

---

#### `bid_form.html`
**Context variables:**
- `form` — a `BidForm` (fields: proposed_price, message)
- `listing` — the `ServiceListing` being bid on (`.title`, `.price`, `.pk`)

**What to build:**
- Show the listing title and listed price for context
- Render the bid form
- Submit button, cancel link back to `{% url 'listing_detail' listing.pk %}`

---

#### `contract_detail.html`
**Context variables:**
- `contract` — a `Contract` object with:
  - `.pk`, `.status`, `.agreed_price`, `.created_at`, `.completed_at`
  - `.student` — the student's `UserProfile`
  - `.client` — the client's `UserProfile`
  - `.payment.status`, `.payment.amount`
  - `.bid.listing.title`, `.bid.message`

**What to build:**
- Contract summary: parties, price, status, dates
- Payment status section
- "Mark as Complete" button — a POST form to `{% url 'contract_complete' contract.pk %}`, shown only if `contract.status == "active"`
- Link back to `{% url 'dashboard' %}`

---

#### `dashboard.html`
**Context variables:**
- `student_contracts` — QuerySet of `Contract` objects where the logged-in user is the student. Each has: `.pk`, `.status`, `.agreed_price`, `.bid.listing.title`, `.client`
- `client_contracts` — QuerySet of `Contract` objects where the logged-in user is the client. Each has: `.pk`, `.status`, `.agreed_price`, `.bid.listing.title`, `.student`

**What to build:**
- Two sections: "Your Work (as Student)" and "Your Hires (as Client)"
- Each contract as a row with a link to `{% url 'contract_detail' contract.pk %}`
- Empty state messages for when either list is empty

---

### Templates Member 3 will provide
Member 2 does not build these — they're Member 3's responsibility:
- `registration/login.html` (or equivalent)
- `registration/logout.html`
- A registration/signup page
- A user profile page

You may want to coordinate on a shared `base.html` for consistent navigation.

---

## Member 3 — User Auth and Profiles

### What's already done
The `UserProfile` model exists and is linked to Django's `User` via `OneToOneField`. The views use `@login_required` which redirects to `/accounts/login/` when a user is not logged in. That URL must resolve — it's your first priority.

### What you need to build

#### 1. Wire up auth URLs in `studentgig/urls.py`

Open `studentgig/urls.py` and add Django's built-in auth views:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),  # adds login, logout, password views
    path("", include("core.urls")),
]
```

This gives you `/accounts/login/`, `/accounts/logout/`, and password reset URLs for free.

You then need to create the templates Django expects at these paths. By default Django looks for `registration/login.html`.

#### 2. Registration view

Django's built-in auth does not include a registration view. You need to write one.

It must:
- Create a `User` with username and password
- Create a `UserProfile` for that user with the chosen `role` (`"student"` or `"client"`)
- Log the user in and redirect to `listing_list`

Recommended approach — create `core/views.py` additions (or a separate `accounts/` app):

```python
# Example registration view skeleton — implement in full
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django import forms as django_forms
from core.models import UserProfile

class RegisterForm(UserCreationForm):
    ROLE_CHOICES = [("student", "Student"), ("client", "Client")]
    role = django_forms.ChoiceField(choices=ROLE_CHOICES)

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user, role=form.cleaned_data["role"])
            login(request, user)
            return redirect("listing_list")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})
```

Add the URL:
```python
path("accounts/register/", views.register, name="register"),
```

#### 3. Profile page

Build a view that shows:
- The user's profile info (username, role, bio, KYC status)
- Their listings (if student)
- Reviews they've received

Context you have available from the model:
```python
profile = UserProfile.objects.get(user=request.user)
listings = profile.listings.filter(is_active=True)          # student's listings
reviews = profile.reviews_received.select_related("reviewer")  # all received reviews
```

#### 4. Review submission view

After a contract is completed, both parties should be able to leave a review.

The `Review` model already exists with these fields: `contract`, `reviewer`, `reviewee`, `rating` (1–5), `comment`.

Build a view that:
- Is protected by `@login_required`
- Takes a `contract_pk` URL argument
- Verifies the request user is a party to the contract
- Verifies the contract is `"completed"`
- Prevents duplicate reviews (one reviewer per contract)
- Saves a `Review` and redirects to the contract detail page

```python
# URL pattern to add
path("contracts/<int:contract_pk>/review/", views.review_create, name="review_create"),
```

#### 5. Login redirect setting

Add this to `studentgig/settings.py` so users land on the listing browse page after login:

```python
LOGIN_REDIRECT_URL = "listing_list"
LOGOUT_REDIRECT_URL = "listing_list"
```

---

### Important: do not modify these files
- `core/models.py` — all models are final
- `core/views.py` — all existing views are tested at 100% coverage
- `core/urls.py` — existing URL patterns must not change
- `core/admin.py` — admin is configured

If you need to add views (register, profile, review), add them in `core/views.py` at the bottom, or create a new file (e.g. `core/auth_views.py`) and import from it in `core/urls.py`.

---

## Summary of who owns what

| Feature | Member |
|---|---|
| Models, migrations | 1 (done) |
| Admin panel | 1 (done) |
| Listing browse/detail/create views | 1 (done) |
| Bid lifecycle views | 1 (done) |
| Contract/payment views | 1 (done) |
| Dashboard view | 1 (done) |
| All templates (`.html` files) | 2 |
| CSS and styling | 2 |
| Login/logout URL wiring | 3 |
| Registration view + form | 3 |
| Profile page view | 3 |
| Review submission view | 3 |
