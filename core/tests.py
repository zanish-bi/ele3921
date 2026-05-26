from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError

from core.models import UserProfile, Category, ServiceListing, Bid, Contract, Payment, Review
from core.forms import BidForm, ServiceListingForm
from core.admin import UserProfileAdmin, ContractAdmin


def make_admin_request():
    """Return a minimal request with messages middleware for admin action tests."""
    factory = RequestFactory()
    request = factory.get("/")
    request.session = {}
    messages = FallbackStorage(request)
    request._messages = messages
    return request


# ── Helpers ─────────────────────────────────────────────────────────────────

def make_user(username, role, kyc=False):
    user = User.objects.create_user(username=username, password="pass")
    profile = user.userprofile
    profile.role = role
    profile.is_kyc_verified = kyc
    profile.save()
    return user, profile


def make_category(name="Design"):
    return Category.objects.create(name=name, description="A test category")


def make_listing(owner, category, title="Logo Design", active=True):
    return ServiceListing.objects.create(
        owner=owner,
        category=category,
        title=title,
        description="Professional logo design service.",
        price=Decimal("80.00"),
        is_remote=True,
        is_active=active,
    )


def make_bid(listing, client_profile, price="60.00", status="pending"):
    return Bid.objects.create(
        listing=listing,
        client=client_profile,
        proposed_price=Decimal(price),
        message="I would like to take this on.",
        status=status,
    )


def make_contract(bid, student, client_profile, status="active"):
    contract = Contract.objects.create(
        bid=bid,
        student=student,
        client=client_profile,
        agreed_price=bid.proposed_price,
        status=status,
    )
    Payment.objects.create(contract=contract, amount=contract.agreed_price, status="held")
    return contract


# ── Model __str__ tests ──────────────────────────────────────────────────────

class ModelStrTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client")
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)

    def test_userprofile_str(self):
        self.assertEqual(str(self.student), "alice (student)")

    def test_category_str(self):
        self.assertEqual(str(self.category), "Design")

    def test_servicelisting_str(self):
        self.assertEqual(str(self.listing), "Logo Design")

    def test_bid_str(self):
        result = str(self.bid)
        self.assertIn("bob (client)", result)
        self.assertIn("Logo Design", result)

    def test_contract_str(self):
        contract = make_contract(self.bid, self.student, self.client_profile)
        result = str(contract)
        self.assertIn("Contract #", result)
        self.assertIn("active", result)

    def test_payment_str(self):
        contract = make_contract(self.bid, self.student, self.client_profile)
        result = str(contract.payment)
        self.assertIn("Contract #", result)
        self.assertIn("held", result)

    def test_review_str(self):
        contract = make_contract(self.bid, self.student, self.client_profile)
        review = Review.objects.create(
            contract=contract,
            reviewer=self.student,
            reviewee=self.client_profile,
            rating=5,
            comment="Great client!",
        )
        result = str(review)
        self.assertIn("alice (student)", result)
        self.assertIn("bob (client)", result)
        self.assertIn("5/5", result)


class ReviewValidatorTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client")
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)
        self.contract = make_contract(self.bid, self.student, self.client_profile)

    def test_rating_below_minimum_raises_error(self):
        review = Review(
            contract=self.contract,
            reviewer=self.student,
            reviewee=self.client_profile,
            rating=0,
        )
        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_rating_above_maximum_raises_error(self):
        review = Review(
            contract=self.contract,
            reviewer=self.student,
            reviewee=self.client_profile,
            rating=6,
        )
        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_valid_rating_does_not_raise(self):
        review = Review(
            contract=self.contract,
            reviewer=self.student,
            reviewee=self.client_profile,
            rating=4,
        )
        review.full_clean()


# ── Form tests ───────────────────────────────────────────────────────────────

class FormTests(TestCase):
    def setUp(self):
        self.category = make_category()

    def test_bid_form_valid(self):
        form = BidForm(data={"proposed_price": "50.00", "message": "I can help."})
        self.assertTrue(form.is_valid())

    def test_bid_form_missing_message(self):
        form = BidForm(data={"proposed_price": "50.00", "message": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("message", form.errors)

    def test_bid_form_missing_price(self):
        form = BidForm(data={"proposed_price": "", "message": "I can help."})
        self.assertFalse(form.is_valid())
        self.assertIn("proposed_price", form.errors)

    def test_service_listing_form_valid(self):
        form = ServiceListingForm(data={
            "category": self.category.pk,
            "title": "Web Dev",
            "description": "I build sites.",
            "price": "100.00",
            "is_remote": True,
        })
        self.assertTrue(form.is_valid())

    def test_service_listing_form_missing_title(self):
        form = ServiceListingForm(data={
            "category": self.category.pk,
            "title": "",
            "description": "I build sites.",
            "price": "100.00",
            "is_remote": True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)


# ── Admin action tests ───────────────────────────────────────────────────────

class AdminActionTests(TestCase):
    def setUp(self):
        _, self.profile = make_user("testuser", "student", kyc=False)
        self.admin = UserProfileAdmin(UserProfile, AdminSite())

    def test_toggle_kyc_false_to_true(self):
        qs = UserProfile.objects.filter(pk=self.profile.pk)
        self.admin.toggle_kyc(None, qs)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_kyc_verified)

    def test_toggle_kyc_true_to_false(self):
        self.profile.is_kyc_verified = True
        self.profile.save()
        qs = UserProfile.objects.filter(pk=self.profile.pk)
        self.admin.toggle_kyc(None, qs)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_kyc_verified)


class ContractAdminActionTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student")
        _, self.client_profile = make_user("bob", "client", kyc=True)
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)
        self.contract = make_contract(self.bid, self.student, self.client_profile, status="disputed")
        self.admin_obj = ContractAdmin(Contract, AdminSite())

    def test_release_payment_action(self):
        req = make_admin_request()
        qs = Contract.objects.filter(pk=self.contract.pk)
        self.admin_obj.release_payment(req, qs)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "completed")
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "released")

    def test_refund_payment_action(self):
        req = make_admin_request()
        qs = Contract.objects.filter(pk=self.contract.pk)
        self.admin_obj.refund_payment(req, qs)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "disputed")
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "refunded")

    def test_release_skips_non_disputed_contracts(self):
        self.contract.status = "active"
        self.contract.save()
        req = make_admin_request()
        qs = Contract.objects.filter(pk=self.contract.pk)
        self.admin_obj.release_payment(req, qs)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "active")


# ── Listing list view ────────────────────────────────────────────────────────

class ListingListViewTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student")
        self.category = make_category("Design")
        self.category2 = make_category("Tutoring")
        make_listing(self.student, self.category, title="Logo Design")
        make_listing(self.student, self.category2, title="Math Tutoring")
        self.url = reverse("listing_list")

    def test_anonymous_can_browse(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Logo Design")
        self.assertContains(response, "Math Tutoring")

    def test_filter_by_category_shows_only_matching(self):
        response = self.client.get(self.url, {"category": self.category.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Logo Design")
        self.assertNotContains(response, "Math Tutoring")

    def test_filter_by_nonexistent_category_returns_empty(self):
        response = self.client.get(self.url, {"category": 9999})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No listings found.")

    def test_inactive_listings_excluded(self):
        make_listing(self.student, self.category, title="Inactive Service", active=False)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Inactive Service")


# ── Listing detail view ──────────────────────────────────────────────────────

class ListingDetailViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        _, self.other_profile = make_user("carol", "client")
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.url = reverse("listing_detail", args=[self.listing.pk])

    def test_anonymous_sees_listing(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.listing.title)

    def test_anonymous_does_not_see_bids_section(self):
        make_bid(self.listing, self.client_profile)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Bids (")

    def test_owner_sees_bids_section(self):
        make_bid(self.listing, self.client_profile)
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bids (")

    def test_non_owner_does_not_see_bids_section(self):
        make_bid(self.listing, self.client_profile)
        self.client.login(username="carol", password="pass")
        response = self.client.get(self.url)
        self.assertNotContains(response, "Bids (")

    def test_user_without_profile_does_not_see_bids_section(self):
        ghost_user = User.objects.create_user(username="ghost", password="pass")
        UserProfile.objects.filter(user=ghost_user).delete()
        self.client.login(username="ghost", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Bids (")

    def test_listing_not_found_returns_404(self):
        response = self.client.get(reverse("listing_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_client_sees_own_bid_status(self):
        make_bid(self.listing, self.client_profile)
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Your Bid")

    def test_client_without_bid_sees_place_bid_button(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Place a Bid")

    def test_client_with_pending_bid_does_not_see_place_bid_button(self):
        make_bid(self.listing, self.client_profile)
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertNotContains(response, "Place a Bid")

    def test_owner_sees_edit_listing_button(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Edit Listing")


# ── Listing create view ──────────────────────────────────────────────────────

class ListingCreateViewTests(TestCase):
    def setUp(self):
        self.student_user, _ = make_user("alice", "student", kyc=True)
        self.unverified_user, _ = make_user("dave", "student", kyc=False)
        self.client_user, _ = make_user("bob", "client")
        self.category = make_category()
        self.url = reverse("listing_create")

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_verified_student_sees_form(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form")

    def test_unverified_student_is_forbidden(self):
        self.client.login(username="dave", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_client_is_forbidden(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_student_creates_listing_and_redirects(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url, {
            "category": self.category.pk,
            "title": "Graphic Design",
            "description": "I design logos.",
            "price": "75.00",
            "is_remote": True,
        })
        self.assertEqual(response.status_code, 302)
        listing = ServiceListing.objects.get(title="Graphic Design")
        self.assertRedirects(response, reverse("listing_detail", args=[listing.pk]))

    def test_student_invalid_form_rerenders(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url, {
            "category": self.category.pk,
            "title": "",
            "description": "I design logos.",
            "price": "75.00",
            "is_remote": True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ServiceListing.objects.exists())


# ── Listing edit view ────────────────────────────────────────────────────────

class ListingEditViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student", kyc=True)
        self.other_user, _ = make_user("bob", "client")
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.url = reverse("listing_edit", args=[self.listing.pk])

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_owner_can_access_edit_form(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Listing")

    def test_non_owner_is_forbidden(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_owner_can_update_listing(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url, {
            "category": self.category.pk,
            "title": "Updated Title",
            "description": "Updated desc.",
            "price": "99.00",
            "is_remote": True,
        })
        self.assertEqual(response.status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, "Updated Title")

    def test_invalid_form_rerenders(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url, {
            "category": self.category.pk,
            "title": "",
            "description": "x",
            "price": "10.00",
        })
        self.assertEqual(response.status_code, 200)


# ── Bid create view ──────────────────────────────────────────────────────────

class BidCreateViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        self.unverified_user, _ = make_user("charlie", "client", kyc=False)
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.inactive = make_listing(self.student, self.category, title="Old Service", active=False)
        self.url = reverse("place_bid", args=[self.listing.pk])

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_student_is_forbidden(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_unverified_client_is_forbidden(self):
        self.client.login(username="charlie", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_verified_client_sees_form(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Place a Bid")

    def test_inactive_listing_returns_404(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(reverse("place_bid", args=[self.inactive.pk]))
        self.assertEqual(response.status_code, 404)

    def test_verified_client_submits_valid_bid(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url, {
            "proposed_price": "60.00",
            "message": "I can do this.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Bid.objects.filter(listing=self.listing, client=self.client_profile).exists())
        self.assertRedirects(response, reverse("listing_detail", args=[self.listing.pk]))

    def test_verified_client_invalid_bid_rerenders(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url, {
            "proposed_price": "",
            "message": "I can do this.",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Bid.objects.filter(listing=self.listing).exists())

    def test_duplicate_pending_bid_redirects_with_error(self):
        make_bid(self.listing, self.client_profile)
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url, {
            "proposed_price": "55.00",
            "message": "Another try.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Bid.objects.filter(listing=self.listing, client=self.client_profile).count(), 1)


# ── Bid edit / delete views ──────────────────────────────────────────────────

class BidEditViewTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        _, self.other_profile = make_user("carol", "client", kyc=True)
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)
        self.url = reverse("bid_edit", args=[self.bid.pk])

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_non_owner_is_forbidden(self):
        self.client.login(username="carol", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_owner_can_edit_pending_bid(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url, {
            "proposed_price": "70.00",
            "message": "Updated message.",
        })
        self.assertEqual(response.status_code, 302)
        self.bid.refresh_from_db()
        self.assertEqual(self.bid.proposed_price, Decimal("70.00"))

    def test_cannot_edit_non_pending_bid(self):
        self.bid.status = "rejected"
        self.bid.save()
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)


class BidDeleteViewTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        _, self.other_profile = make_user("carol", "client", kyc=True)
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)
        self.url = reverse("bid_delete", args=[self.bid.pk])

    def test_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_get_not_allowed(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_non_owner_is_forbidden(self):
        self.client.login(username="carol", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_owner_can_withdraw_pending_bid(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Bid.objects.filter(pk=self.bid.pk).exists())

    def test_cannot_withdraw_non_pending_bid(self):
        self.bid.status = "accepted"
        self.bid.save()
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)


# ── Bid accept view ──────────────────────────────────────────────────────────

class BidAcceptViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        self.other_user, self.other_profile = make_user("carol", "client", kyc=True)
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)

    def _url(self):
        return reverse("bid_accept", args=[self.bid.pk])

    def test_requires_login(self):
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_get_request_returns_405(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 405)

    def test_non_owner_is_forbidden(self):
        self.client.login(username="carol", password="pass")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 403)

    def test_non_pending_bid_returns_400(self):
        self.bid.status = "rejected"
        self.bid.save()
        self.client.login(username="alice", password="pass")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 400)

    def test_accepting_bid_creates_contract_and_payment(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 302)
        self.bid.refresh_from_db()
        self.assertEqual(self.bid.status, "accepted")
        contract = Contract.objects.get(bid=self.bid)
        self.assertEqual(contract.student, self.student)
        self.assertEqual(contract.client, self.client_profile)
        self.assertEqual(contract.agreed_price, self.bid.proposed_price)
        self.assertEqual(contract.status, "active")
        self.assertEqual(contract.payment.status, "held")
        self.assertEqual(contract.payment.amount, self.bid.proposed_price)
        self.assertRedirects(response, reverse("contract_detail", args=[contract.pk]))

    def test_accepting_bid_deactivates_listing(self):
        self.client.login(username="alice", password="pass")
        self.client.post(self._url())
        self.listing.refresh_from_db()
        self.assertFalse(self.listing.is_active)

    def test_accepting_bid_rejects_other_pending_bids(self):
        other_bid = make_bid(self.listing, self.other_profile)
        self.client.login(username="alice", password="pass")
        self.client.post(self._url())
        other_bid.refresh_from_db()
        self.assertEqual(other_bid.status, "rejected")


# ── Bid reject view ──────────────────────────────────────────────────────────

class BidRejectViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        _, self.other_profile = make_user("carol", "client")
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)

    def _url(self):
        return reverse("bid_reject", args=[self.bid.pk])

    def test_requires_login(self):
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_get_request_returns_405(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 405)

    def test_non_owner_is_forbidden(self):
        self.client.login(username="carol", password="pass")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 403)

    def test_non_pending_bid_returns_400(self):
        self.bid.status = "accepted"
        self.bid.save()
        self.client.login(username="alice", password="pass")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 400)

    def test_owner_rejects_bid_and_redirects(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 302)
        self.bid.refresh_from_db()
        self.assertEqual(self.bid.status, "rejected")
        self.assertRedirects(response, reverse("listing_detail", args=[self.listing.pk]))


# ── Contract detail view ─────────────────────────────────────────────────────

class ContractDetailViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        _, self.other_profile = make_user("carol", "student")
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)
        self.contract = make_contract(self.bid, self.student, self.client_profile)
        self.url = reverse("contract_detail", args=[self.contract.pk])

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_student_can_view_contract(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Contract #{self.contract.pk}")

    def test_client_can_view_contract(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_unrelated_user_is_forbidden(self):
        self.client.login(username="carol", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_contract_not_found_returns_404(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(reverse("contract_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_admin_note_shown_when_set(self):
        self.contract.admin_note = "Admin decision: payment released."
        self.contract.save()
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Admin decision: payment released.")


# ── Contract deliver / accept / reject views ─────────────────────────────────

class ContractDeliverViewTests(TestCase):
    """contract_complete now sets status → delivered (student submits work)."""

    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)
        self.contract = make_contract(self.bid, self.student, self.client_profile)
        self.url = reverse("contract_complete", args=[self.contract.pk])

    def test_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_get_request_returns_405(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_client_cannot_submit_work(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_non_active_contract_returns_400(self):
        self.contract.status = "completed"
        self.contract.save()
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_student_submits_work_sets_delivered(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "delivered")
        # Payment still held until client accepts
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "held")
        self.assertRedirects(response, reverse("contract_detail", args=[self.contract.pk]))


class ContractAcceptViewTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        _, self.other = make_user("carol", "student")
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)
        self.contract = make_contract(self.bid, self.student, self.client_profile, status="delivered")
        self.url = reverse("contract_accept", args=[self.contract.pk])

    def test_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_get_returns_405(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_student_cannot_accept_own_delivery(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_non_delivered_returns_400(self):
        self.contract.status = "active"
        self.contract.save()
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_client_accepts_delivery(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "completed")
        self.assertIsNotNone(self.contract.completed_at)
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "released")
        self.assertRedirects(response, reverse("contract_detail", args=[self.contract.pk]))


class ContractRejectViewTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)
        self.contract = make_contract(self.bid, self.student, self.client_profile, status="delivered")
        self.url = reverse("contract_reject", args=[self.contract.pk])

    def test_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_get_returns_405(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_student_cannot_reject_own_delivery(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_non_delivered_returns_400(self):
        self.contract.status = "active"
        self.contract.save()
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_client_rejects_delivery_raises_dispute(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "disputed")
        # Payment still held pending admin resolution
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "held")
        self.assertRedirects(response, reverse("contract_detail", args=[self.contract.pk]))


# ── Dashboard view ───────────────────────────────────────────────────────────

class DashboardViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        self.category = make_category()
        self.listing = make_listing(self.student, self.category)
        self.bid = make_bid(self.listing, self.client_profile)
        self.contract = make_contract(self.bid, self.student, self.client_profile)
        self.url = reverse("dashboard")

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_student_sees_their_contract(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Contract #{self.contract.pk}")

    def test_client_sees_their_contract(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Contract #{self.contract.pk}")

    def test_empty_student_dashboard_shows_student_message(self):
        dan_user = User.objects.create_user(username="dan", password="pass")
        dan_user.userprofile.role = "student"
        dan_user.userprofile.save()
        self.client.login(username="dan", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No contracts as student.")
        self.assertNotContains(response, "No contracts as client.")

    def test_empty_client_dashboard_shows_client_message(self):
        eve_user = User.objects.create_user(username="eve", password="pass")
        eve_user.userprofile.role = "client"
        eve_user.userprofile.save()
        self.client.login(username="eve", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No contracts as client.")
        self.assertNotContains(response, "No contracts as student.")

    def test_student_sees_pending_received_bids(self):
        # Fresh listing, fresh bid that hasn't been accepted
        listing2 = make_listing(self.student, self.category, title="New Service")
        _, c2 = make_user("client2", "client", kyc=True)
        make_bid(listing2, c2)
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Bids Received")

    def test_client_sees_submitted_bids_section(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Your Submitted Bids")

    def test_student_does_not_see_your_hires(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertNotContains(response, "Your Hires (as Client)")

    def test_client_does_not_see_your_work(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertNotContains(response, "Your Work (as Student)")


# ── Home and register views ──────────────────────────────────────────────────

class HomeViewTests(TestCase):
    def test_home_renders(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)


class RegisterViewTests(TestCase):
    def test_register_get_renders_form(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form")

    def test_register_valid_post_creates_user_and_redirects(self):
        response = self.client.post(reverse("register"), {
            "username": "newstudent",
            "password": "testpass123",
            "role": "student",
        })
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="newstudent")
        self.assertEqual(user.userprofile.role, "student")

    def test_register_invalid_post_rerenders_form(self):
        response = self.client.post(reverse("register"), {
            "username": "",
            "password": "testpass123",
            "role": "student",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="").exists())
