# Member 2 & 3 Integration Instructions

This document tells you exactly what each member needs to build and how to plug into the existing backend. Member 1's backend (models, views, URLs, admin) is complete and tested. Do not modify `core/models.py`, `core/views.py`, `core/urls.py`, or `core/admin.py` unless coordinating with Member 1 (Zanish).

---

## What Is Already Done (Do Not Rebuild)

| Feature | Status |
|---|---|
| All 7 data models | Done |
| Django admin panel | Done |
| Listing browse / detail / create views | Done |
| Bid accept / reject views | Done |
| Contract detail / complete views | Done |
| Dashboard view | Done |
| `/accounts/login/` and `/accounts/logout/` | Done — Django built-in auth wired up |
| `/accounts/register/` | Done — `register` view in `core/views.py` |
| `UserProfile` auto-created on every new `User` | Done — signal in `core/signals.py` |
| `UserRegisterForm` with role selection | Done — in `core/forms.py` |
| 8 initial categories loaded on first migrate | Done — migration 0003 |
| `registration/login.html` template | Done |
| `registration/register.html` template | Done |

---

## Member 2 — Frontend Templates

### What's already done
All views exist and work. Minimal skeleton templates are in `core/templates/core/`. Your job is to replace those skeletons with properly styled HTML. The backend will pass the same context variables regardless of how the template looks.

### Rules
- Keep the same file names — the views reference these paths exactly
- Do not rename URLs or add new URL patterns (coordinate with Member 1 if you need a new route)
- You can add a `base.html` and use `{% extends "core/base.html" %}` in each template
- Use `{% url 'name' %}` for all links — never hardcode paths
- All forms must include `{% csrf_token %}` inside `<form method="post">` tags

### Available Categories

8 categories are pre-loaded and ready to use in the listing creation form:
`Design`, `Programming`, `Tutoring`, `Writing`, `Video & Animation`, `Translation`, `Marketing`, `Data & Research`

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
- A "Place a Bid" link to `{% url 'place_bid' listing.pk %}` — show only if `listing.is_active and user.is_authenticated and request.user.userprofile.role == "client"`
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
- KYC pending notice when `not request.user.userprofile.is_kyc_verified`
- Logout button: `<form method="post" action="{% url 'logout' %}">{% csrf_token %}<button>Logout</button></form>`

---

### Templates already built by Member 3 (do not duplicate)
- `registration/login.html`
- `registration/register.html`

You may want to coordinate on a shared `base.html` for consistent navigation across all pages.

---

## Member 3 — User Auth and Profiles

### What is already done

The following were completed by Member 3 or by Member 1 during integration:

| Task | Status |
|---|---|
| `path("accounts/", include("django.contrib.auth.urls"))` in root `urls.py` | Done |
| `registration/login.html` template | Done |
| `registration/register.html` template | Done |
| `register` view — creates User + sets role on UserProfile | Done (`core/views.py`) |
| `UserRegisterForm` with username, password, role fields | Done (`core/forms.py`) |
| `UserProfile` auto-created by signal on every new `User` | Done (`core/signals.py`) |
| `LOGIN_REDIRECT_URL = '/'` and `LOGOUT_REDIRECT_URL = '/accounts/login/'` | Done (`settings.py`) |

### What you still need to build

#### 1. Profile page view

Build a view that shows a user's public profile:
- Username, role, bio, KYC status
- Their active listings (if student): `profile.listings.filter(is_active=True)`
- Reviews they have received: `profile.reviews_received.select_related("reviewer")`

Suggested URL to add to `core/urls.py`:
```python
path("profiles/<int:user_pk>/", views.profile_detail, name="profile_detail"),
```

#### 2. Review submission view

After a contract is completed, both the student and the client should be able to leave one review each.

The `Review` model already exists with fields: `contract`, `reviewer`, `reviewee`, `rating` (1–5), `comment`.

**Important constraint:** `Review` has `unique_together = [("contract", "reviewer")]`. Your view must check that the logged-in user has not already reviewed this contract before saving, otherwise Django will raise an `IntegrityError`.

Build a view that:
- Is protected by `@login_required`
- Takes a `contract_pk` URL argument
- Verifies the request user is a party to the contract (`contract.student` or `contract.client`)
- Verifies the contract status is `"completed"`
- Checks no review by this user on this contract already exists
- Saves a `Review` and redirects to the contract detail page

Suggested URL to add to `core/urls.py`:
```python
path("contracts/<int:contract_pk>/review/", views.review_create, name="review_create"),
```

Suggested view sketch:
```python
@login_required
def review_create(request, contract_pk):
    contract = get_object_or_404(Contract, pk=contract_pk)
    profile = get_object_or_404(UserProfile, user=request.user)

    if contract.student != profile and contract.client != profile:
        return HttpResponseForbidden("You are not a party to this contract.")
    if contract.status != "completed":
        return HttpResponseBadRequest("Contract is not completed yet.")
    if Review.objects.filter(contract=contract, reviewer=profile).exists():
        return HttpResponseBadRequest("You have already reviewed this contract.")

    reviewee = contract.client if profile == contract.student else contract.student

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.contract = contract
            review.reviewer = profile
            review.reviewee = reviewee
            review.save()
            return redirect("contract_detail", pk=contract.pk)
    else:
        form = ReviewForm()
    return render(request, "core/review_form.html", {"form": form, "contract": contract})
```

You will also need to create `ReviewForm` in `core/forms.py`:
```python
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
```

And the template `core/templates/core/review_form.html`.

---

### Important: do not modify these files
- `core/models.py`
- `core/views.py` (add new views at the bottom only)
- `core/admin.py`
- `core/signals.py`
- `core/migrations/` (never edit existing migration files)

If you add new views, add them to the **bottom** of `core/views.py` and add their URL patterns to `core/urls.py`.

---

## Summary of remaining work

| Task | Member | Status |
|---|---|---|
| Style all 6 core templates | 2 | Pending |
| Style `registration/login.html` | 2 | Pending |
| Style `registration/register.html` | 2 | Pending |
| Shared `base.html` | 2 | Pending |
| Profile page view + template | 3 | Pending |
| Review submission view + template | 3 | Pending |
| `ReviewForm` in `core/forms.py` | 3 | Pending |
