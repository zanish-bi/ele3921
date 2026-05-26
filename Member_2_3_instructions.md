# Member 2 & 3 Integration Instructions

This document describes what each member built and how it plugs into the backend. Member 1's backend (models, views, URLs, admin) is complete and tested. Do not modify `core/models.py`, `core/admin.py`, or `core/signals.py`. New views go at the bottom of `core/views.py`; new URL patterns at the bottom of `core/urls.py`.

---

## Status Summary

| Task | Member | Status |
|---|---|---|
| All 6 core page templates | 2 | **Done** |
| `registration/login.html` | 2 | **Done** |
| `registration/register.html` | 2 | **Done** |
| Shared `base.html` | 2 | **Done** |
| Profile page view + template | 3 | **Done** |
| Review submission view + template | 3 | **Done** |
| `ReviewForm` in `core/forms.py` | 3 | **Done** |

---

## What Is Already Done (Do Not Rebuild)

| Feature | Status |
|---|---|
| All 7 data models | Done |
| Django admin panel | Done |
| Listing browse / detail / create views | Done |
| Bid accept / reject views | Done |
| Contract detail / complete / list views | Done |
| Dashboard view | Done |
| `/accounts/login/` and `/accounts/logout/` | Done — Django built-in auth |
| `/accounts/register/` | Done — `register` view in `core/views.py` |
| `/accounts/kyc-verify/` | Done — `kyc_self_verify` view (test mode) |
| `/contracts/<pk>/review/` | Done — `review_create` view |
| `/profiles/<user_pk>/` | Done — `profile_detail` view |
| `UserProfile` auto-created on every new `User` | Done — signal in `core/signals.py` |
| `UserRegisterForm`, `ReviewForm` | Done — in `core/forms.py` |
| 8 initial categories loaded on first migrate | Done — migration 0003 |
| All 10 page templates + 2 auth templates | Done — styled with base.html |
| `base.html` with shared CSS and navbar | Done |

---

## Member 2 — Frontend Templates

### What Was Built

All templates live in `core/templates/core/` and extend `core/base.html`.

**`base.html`** — Shared layout providing:
- Sticky navbar with role-aware links (Browse, Dashboard, Contracts, Post a Service)
- Flash message display (auto-dismiss after 4 s)
- CSS utility classes: `.card`, `.btn`, `.btn-primary/.secondary/.success/.danger/.sm`, `.badge`, `.badge-success/.warning/.danger/.info`, `.table`, `.section-title`, `.empty-state`, `.page-header`, `.form-wrap`, `.form-group`, `.form-errors`, `.form-actions`, `.listing-card`, `.listing-price`, `.dash-grid`

**Page templates:**

| Template | Key behaviour |
|---|---|
| `index.html` | Landing page; shows KYC status + test-mode verify button when logged in |
| `listing_list.html` | Category filter, card grid, "No listings found." empty state |
| `listing_detail.html` | Listing detail; "Bids (N)" table visible to owner only; "Place a Bid" for KYC-verified clients |
| `listing_create.html` | Service listing form |
| `place_bid.html` | Two-column: listing context + bid form |
| `contract_detail.html` | Contract summary, payment panel, "Mark as Complete" for student, "Leave a Review" for completed contracts, profile links |
| `contracts.html` | Active + completed contracts list with role-aware "other party" display |
| `dashboard.html` | Two-column grid: "Your Work (as Student)" and "Your Hires (as Client)" tables with exact empty-state text required by tests |

**Auth templates (`registration/`):**
- `login.html` — Centred form card, link to register
- `register.html` — Centred form card, link to login

### Rules Still Apply
- Keep the same template file names
- Use `{% url 'name' %}` for all links
- All `<form method="post">` tags must include `{% csrf_token %}`
- Do not hardcode paths

---

## Member 3 — User Auth and Profiles

### What Was Built

#### `ReviewForm` — `core/forms.py`

```python
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
```

#### `profile_detail` view — `core/views.py`

Public profile page. URL: `profiles/<int:user_pk>/` → name `profile_detail`.

Context passed to template:
- `profile` — `UserProfile` object
- `listings` — active listings if student, `None` if client
- `reviews` — `reviews_received` queryset with reviewer pre-fetched

#### `review_create` view — `core/views.py`

Protected review submission. URL: `contracts/<int:contract_pk>/review/` → name `review_create`.

Guards enforced:
1. User must be a party to the contract (`student` or `client`)
2. Contract must be `"completed"`
3. User must not have already reviewed this contract (`unique_together` enforced)

#### Templates

- `core/templates/core/profile_detail.html` — Editorial portfolio layout: circular initial avatar, bio, active listings with animated hover border, reviews with `★/☆` star display. CSS-only animations.
- `core/templates/core/review_form.html` — Centred form card with contract receipt context, JS star picker (5 clickable stars, keyboard arrow support, degrades gracefully to `<select>` with no JS).

---

## KYC Test Mode

The `kyc_self_verify` view (POST `/accounts/kyc-verify/`) sets `is_kyc_verified = True` for the logged-in user. A yellow "Simulate KYC Verification (Test Mode)" button is shown on the dashboard and home page when a user's account is unverified. This is only for testing — in production, KYC is set by an admin in `/admin/`.

---

## URL Quick Reference

| URL | Name | Notes |
|---|---|---|
| `/listings/` | `listing_list` | |
| `/listings/<pk>/bid/` | `place_bid` | **(renamed from `bid_create`)** |
| `/contracts/<pk>/review/` | `review_create` | Member 3 |
| `/profiles/<user_pk>/` | `profile_detail` | Member 3 |
| `/accounts/kyc-verify/` | `kyc_self_verify` | POST only, test mode |
