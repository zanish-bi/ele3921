from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError

from core.models import (
    UserProfile, Category, ServiceListing, Bid, Contract, Payment, Review,
    JobRequest, JobBid, ContractMessage, Notification,
)
from core.forms import BidForm, ServiceListingForm, JobRequestForm, JobBidForm, ContractMessageForm
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


# ── Helpers for new features ─────────────────────────────────────────────────

def make_job_request(client_profile, category, title="Build a Website", budget="200.00", active=True):
    return JobRequest.objects.create(
        client=client_profile,
        category=category,
        title=title,
        description="I need a website built.",
        budget=Decimal(budget),
        is_active=active,
    )


def make_job_bid(job, student_profile, price="150.00", status="pending"):
    return JobBid.objects.create(
        job_request=job,
        student=student_profile,
        proposed_price=Decimal(price),
        message="I can build it.",
        status=status,
    )


def make_job_contract(job_bid, student, client_profile, status="active"):
    contract = Contract.objects.create(
        job_bid=job_bid,
        student=student,
        client=client_profile,
        agreed_price=job_bid.proposed_price,
        status=status,
    )
    Payment.objects.create(contract=contract, amount=contract.agreed_price, status="held")
    return contract


# ── Listing advanced filters ─────────────────────────────────────────────────

class ListingFilterTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student")
        self.cat = make_category("Tech")
        ServiceListing.objects.create(
            owner=self.student, category=self.cat,
            title="Cheap Task", description="Cheap", price=Decimal("10.00"),
            is_remote=True, is_active=True,
        )
        ServiceListing.objects.create(
            owner=self.student, category=self.cat,
            title="Expensive Task", description="Expensive", price=Decimal("500.00"),
            is_remote=False, is_active=True,
        )
        self.url = reverse("listing_list")

    def test_min_price_filter(self):
        response = self.client.get(self.url, {"min_price": "100"})
        self.assertContains(response, "Expensive Task")
        self.assertNotContains(response, "Cheap Task")

    def test_max_price_filter(self):
        response = self.client.get(self.url, {"max_price": "50"})
        self.assertContains(response, "Cheap Task")
        self.assertNotContains(response, "Expensive Task")

    def test_remote_true_filter(self):
        response = self.client.get(self.url, {"remote": "true"})
        self.assertContains(response, "Cheap Task")
        self.assertNotContains(response, "Expensive Task")

    def test_remote_false_filter(self):
        response = self.client.get(self.url, {"remote": "false"})
        self.assertContains(response, "Expensive Task")
        self.assertNotContains(response, "Cheap Task")

    def test_sort_price_asc(self):
        response = self.client.get(self.url, {"sort": "price_asc"})
        content = response.content.decode()
        self.assertLess(content.index("Cheap Task"), content.index("Expensive Task"))

    def test_sort_price_desc(self):
        response = self.client.get(self.url, {"sort": "price_desc"})
        content = response.content.decode()
        self.assertLess(content.index("Expensive Task"), content.index("Cheap Task"))

    def test_invalid_min_price_ignored(self):
        response = self.client.get(self.url, {"min_price": "notanumber"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cheap Task")


# ── JobRequest CRUD ──────────────────────────────────────────────────────────

class JobRequestListViewTests(TestCase):
    def setUp(self):
        _, self.client_profile = make_user("bob", "client", kyc=True)
        self.cat = make_category("Tech")
        make_job_request(self.client_profile, self.cat, title="Website Project")
        self.url = reverse("job_request_list")

    def test_anonymous_can_browse(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Website Project")

    def test_inactive_jobs_excluded(self):
        make_job_request(self.client_profile, self.cat, title="Closed Job", active=False)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Closed Job")

    def test_budget_max_filter(self):
        make_job_request(self.client_profile, self.cat, title="Big Job", budget="1000.00")
        response = self.client.get(self.url, {"budget_max": "500"})
        self.assertContains(response, "Website Project")
        self.assertNotContains(response, "Big Job")

    def test_sort_budget_desc(self):
        make_job_request(self.client_profile, self.cat, title="Big Job", budget="1000.00")
        response = self.client.get(self.url, {"sort": "budget_desc"})
        content = response.content.decode()
        self.assertLess(content.index("Big Job"), content.index("Website Project"))


class JobRequestCreateViewTests(TestCase):
    def setUp(self):
        self.student_user, _ = make_user("alice", "student", kyc=True)
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        self.unverified_user, _ = make_user("charlie", "client", kyc=False)
        self.cat = make_category()
        self.url = reverse("job_request_create")

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
        self.assertContains(response, "<form")

    def test_valid_post_creates_job_and_redirects(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url, {
            "category": self.cat.pk,
            "title": "Build a Logo",
            "description": "Need a logo made.",
            "budget": "120.00",
        })
        self.assertEqual(response.status_code, 302)
        job = JobRequest.objects.get(title="Build a Logo")
        self.assertRedirects(response, reverse("job_request_detail", args=[job.pk]))
        self.assertEqual(job.client, self.client_profile)

    def test_invalid_post_rerenders(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url, {
            "category": self.cat.pk, "title": "", "description": "x", "budget": "50.00",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(JobRequest.objects.exists())


class JobRequestDetailViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student", kyc=True)
        _, self.client_profile = make_user("bob", "client", kyc=True)
        self.cat = make_category()
        self.job = make_job_request(self.client_profile, self.cat)
        self.url = reverse("job_request_detail", args=[self.job.pk])

    def test_anonymous_can_view(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.job.title)

    def test_owner_sees_bids_section(self):
        make_job_bid(self.job, self.student)
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Bids Received")

    def test_student_without_bid_sees_apply_button(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Apply / Bid")

    def test_student_with_bid_sees_their_bid(self):
        make_job_bid(self.job, self.student)
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertContains(response, "Your Bid")


# ── JobBid create / accept / reject ─────────────────────────────────────────

class JobBidCreateViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student", kyc=True)
        _, self.client_profile = make_user("bob", "client", kyc=True)
        self.unverified_student_user, _ = make_user("dave", "student", kyc=False)
        self.cat = make_category()
        self.job = make_job_request(self.client_profile, self.cat)
        self.url = reverse("job_bid_create", args=[self.job.pk])

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_client_is_forbidden(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_unverified_student_is_forbidden(self):
        self.client.login(username="dave", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_valid_bid_submitted_successfully(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url, {
            "proposed_price": "150.00",
            "message": "I'll do it.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JobBid.objects.filter(job_request=self.job, student=self.student).exists())

    def test_duplicate_bid_redirects_with_error(self):
        make_job_bid(self.job, self.student)
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url, {
            "proposed_price": "120.00", "message": "Another try.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(JobBid.objects.filter(job_request=self.job, student=self.student).count(), 1)

    def test_invalid_post_rerenders(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url, {"proposed_price": "", "message": "x"})
        self.assertEqual(response.status_code, 200)

    def test_inactive_job_returns_404(self):
        self.job.is_active = False
        self.job.save()
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)


class JobBidAcceptViewTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student", kyc=True)
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        _, self.other_student = make_user("dave", "student", kyc=True)
        self.cat = make_category()
        self.job = make_job_request(self.client_profile, self.cat)
        self.job_bid = make_job_bid(self.job, self.student)
        self.url = reverse("job_bid_accept", args=[self.job_bid.pk])

    def test_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_get_returns_405(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_student_cannot_accept_bid(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_non_pending_bid_returns_400(self):
        self.job_bid.status = "rejected"
        self.job_bid.save()
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_accepting_bid_creates_contract(self):
        other_bid = make_job_bid(self.job, self.other_student, price="130.00")
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.job_bid.refresh_from_db()
        self.assertEqual(self.job_bid.status, "accepted")
        contract = Contract.objects.get(job_bid=self.job_bid)
        self.assertEqual(contract.student, self.student)
        self.assertEqual(contract.client, self.client_profile)
        self.assertEqual(contract.status, "active")
        self.assertEqual(contract.payment.status, "held")
        self.assertRedirects(response, reverse("contract_detail", args=[contract.pk]))
        other_bid.refresh_from_db()
        self.assertEqual(other_bid.status, "rejected")

    def test_accepting_bid_closes_job(self):
        self.client.login(username="bob", password="pass")
        self.client.post(self.url)
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_active)


class JobBidRejectViewTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student", kyc=True)
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        self.cat = make_category()
        self.job = make_job_request(self.client_profile, self.cat)
        self.job_bid = make_job_bid(self.job, self.student)
        self.url = reverse("job_bid_reject", args=[self.job_bid.pk])

    def test_requires_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_get_returns_405(self):
        self.client.login(username="bob", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_student_cannot_reject(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_non_pending_bid_returns_400(self):
        self.job_bid.status = "accepted"
        self.job_bid.save()
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_client_rejects_bid(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.job_bid.refresh_from_db()
        self.assertEqual(self.job_bid.status, "rejected")
        self.assertRedirects(response, reverse("job_request_detail", args=[self.job.pk]))


# ── ContractMessage ──────────────────────────────────────────────────────────

class ContractMessageTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        _, self.outsider = make_user("carol", "student")
        self.cat = make_category()
        listing = make_listing(self.student, self.cat)
        bid = make_bid(listing, self.client_profile)
        self.contract = make_contract(bid, self.student, self.client_profile)
        self.url = reverse("contract_message_create", args=[self.contract.pk])

    def test_requires_login(self):
        response = self.client.post(self.url, {"body": "Hi"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_outsider_is_forbidden(self):
        self.client.login(username="carol", password="pass")
        response = self.client.post(self.url, {"body": "Hi"})
        self.assertEqual(response.status_code, 403)

    def test_student_can_send_message(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.url, {"body": "Work is in progress."})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContractMessage.objects.filter(contract=self.contract).count(), 1)
        msg = ContractMessage.objects.get(contract=self.contract)
        self.assertEqual(msg.sender, self.student)
        self.assertEqual(msg.body, "Work is in progress.")

    def test_client_can_send_message(self):
        self.client.login(username="bob", password="pass")
        response = self.client.post(self.url, {"body": "Looks good!"})
        self.assertEqual(response.status_code, 302)
        msg = ContractMessage.objects.get(contract=self.contract)
        self.assertEqual(msg.sender, self.client_profile)

    def test_message_shown_in_contract_detail(self):
        ContractMessage.objects.create(
            contract=self.contract, sender=self.student, body="Hello client!"
        )
        self.client.login(username="alice", password="pass")
        response = self.client.get(reverse("contract_detail", args=[self.contract.pk]))
        self.assertContains(response, "Hello client!")

    def test_empty_message_does_not_save(self):
        self.client.login(username="alice", password="pass")
        self.client.post(self.url, {"body": ""})
        self.assertEqual(ContractMessage.objects.filter(contract=self.contract).count(), 0)

    def test_message_notifies_other_party(self):
        self.client.login(username="alice", password="pass")
        self.client.post(self.url, {"body": "Ready!"})
        notif = Notification.objects.filter(recipient=self.client_profile).first()
        self.assertIsNotNone(notif)
        self.assertIn(str(self.contract.pk), notif.message)

    def test_contract_message_str(self):
        msg = ContractMessage.objects.create(
            contract=self.contract, sender=self.student, body="Hello"
        )
        self.assertIn("alice", str(msg))
        self.assertIn(str(self.contract.pk), str(msg))


# ── Notifications ────────────────────────────────────────────────────────────

class NotificationTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        Notification.objects.create(recipient=self.student, message="Test notif 1", is_read=False)
        Notification.objects.create(recipient=self.student, message="Test notif 2", is_read=True)
        self.list_url = reverse("notifications_list")
        self.mark_url = reverse("notifications_mark_read")

    def test_requires_login(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)

    def test_user_sees_their_notifications(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test notif 1")
        self.assertContains(response, "Test notif 2")

    def test_unread_count_in_context(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.list_url)
        self.assertEqual(response.context["unread_notifications_count"], 1)

    def test_mark_all_read_requires_post(self):
        self.client.login(username="alice", password="pass")
        response = self.client.get(self.mark_url)
        self.assertEqual(response.status_code, 405)

    def test_mark_all_read_sets_all_read(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.mark_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notification.objects.filter(recipient=self.student, is_read=False).count(), 0)

    def test_mark_all_read_redirects_to_list(self):
        self.client.login(username="alice", password="pass")
        response = self.client.post(self.mark_url)
        self.assertRedirects(response, self.list_url)

    def test_notification_str(self):
        notif = Notification.objects.filter(recipient=self.student).first()
        self.assertIn("alice", str(notif))


# ── Notification creation on key actions ────────────────────────────────────

class NotificationCreationTests(TestCase):
    def setUp(self):
        self.student_user, self.student = make_user("alice", "student")
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        self.cat = make_category()
        self.listing = make_listing(self.student, self.cat)

    def test_placing_bid_notifies_listing_owner(self):
        self.client.login(username="bob", password="pass")
        self.client.post(reverse("place_bid", args=[self.listing.pk]), {
            "proposed_price": "60.00", "message": "I can do this.",
        })
        notif = Notification.objects.filter(recipient=self.student).first()
        self.assertIsNotNone(notif)
        self.assertIn("60.00", notif.message)

    def test_bid_accept_notifies_client(self):
        bid = make_bid(self.listing, self.client_profile)
        self.client.login(username="alice", password="pass")
        self.client.post(reverse("bid_accept", args=[bid.pk]))
        notif = Notification.objects.filter(recipient=self.client_profile).last()
        self.assertIsNotNone(notif)
        self.assertIn("accepted", notif.message.lower())

    def test_bid_reject_notifies_client(self):
        bid = make_bid(self.listing, self.client_profile)
        self.client.login(username="alice", password="pass")
        self.client.post(reverse("bid_reject", args=[bid.pk]))
        notif = Notification.objects.filter(recipient=self.client_profile).last()
        self.assertIsNotNone(notif)
        self.assertIn("rejected", notif.message.lower())

    def test_submit_work_notifies_client(self):
        bid = make_bid(self.listing, self.client_profile)
        contract = make_contract(bid, self.student, self.client_profile)
        self.client.login(username="alice", password="pass")
        self.client.post(reverse("contract_complete", args=[contract.pk]))
        notif = Notification.objects.filter(recipient=self.client_profile).last()
        self.assertIsNotNone(notif)
        self.assertIn(str(contract.pk), notif.message)

    def test_accept_delivery_notifies_student(self):
        bid = make_bid(self.listing, self.client_profile)
        contract = make_contract(bid, self.student, self.client_profile, status="delivered")
        self.client.login(username="bob", password="pass")
        self.client.post(reverse("contract_accept", args=[contract.pk]))
        notif = Notification.objects.filter(recipient=self.student).last()
        self.assertIsNotNone(notif)
        self.assertIn(str(contract.pk), notif.message)

    def test_reject_delivery_notifies_student(self):
        bid = make_bid(self.listing, self.client_profile)
        contract = make_contract(bid, self.student, self.client_profile, status="delivered")
        self.client.login(username="bob", password="pass")
        self.client.post(reverse("contract_reject", args=[contract.pk]))
        notif = Notification.objects.filter(recipient=self.student).last()
        self.assertIsNotNone(notif)
        self.assertIn("dispute", notif.message.lower())


# ── Job contract via JobBid ──────────────────────────────────────────────────

class JobContractTests(TestCase):
    """End-to-end: job request → bid → contract → deliver → accept."""

    def setUp(self):
        self.student_user, self.student = make_user("alice", "student", kyc=True)
        self.client_user, self.client_profile = make_user("bob", "client", kyc=True)
        self.cat = make_category()
        self.job = make_job_request(self.client_profile, self.cat)
        self.job_bid = make_job_bid(self.job, self.student)

    def _accept_job_bid(self):
        self.client.login(username="bob", password="pass")
        resp = self.client.post(reverse("job_bid_accept", args=[self.job_bid.pk]))
        self.client.logout()
        return Contract.objects.get(job_bid=self.job_bid)

    def test_job_contract_listing_title_property(self):
        contract = self._accept_job_bid()
        self.assertEqual(contract.listing_title, self.job.title)

    def test_job_contract_bid_message_property(self):
        contract = self._accept_job_bid()
        self.assertEqual(contract.bid_message, self.job_bid.message)

    def test_job_contract_full_lifecycle(self):
        contract = self._accept_job_bid()

        # Student delivers
        self.client.login(username="alice", password="pass")
        self.client.post(reverse("contract_complete", args=[contract.pk]))
        contract.refresh_from_db()
        self.assertEqual(contract.status, "delivered")
        self.client.logout()

        # Client accepts
        self.client.login(username="bob", password="pass")
        self.client.post(reverse("contract_accept", args=[contract.pk]))
        contract.refresh_from_db()
        self.assertEqual(contract.status, "completed")
        contract.payment.refresh_from_db()
        self.assertEqual(contract.payment.status, "released")

    def test_job_contract_shown_in_contracts_page(self):
        contract = self._accept_job_bid()
        self.client.login(username="alice", password="pass")
        response = self.client.get(reverse("contracts"))
        self.assertContains(response, f"Contract #{contract.pk}")
        self.assertContains(response, self.job.title)

    def test_job_contract_shown_in_dashboard(self):
        contract = self._accept_job_bid()
        self.client.login(username="alice", password="pass")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, f"Contract #{contract.pk}")


# ── Payment sync (admin edit) ────────────────────────────────────────────────

class PaymentSyncTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student")
        _, self.client_profile = make_user("bob", "client", kyc=True)
        self.cat = make_category()
        listing = make_listing(self.student, self.cat)
        bid = make_bid(listing, self.client_profile)
        self.contract = make_contract(bid, self.student, self.client_profile)

    def test_releasing_payment_completes_contract(self):
        self.contract.status = "delivered"
        self.contract.save()
        payment = self.contract.payment
        payment.status = "released"
        payment.save()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "completed")

    def test_refunding_payment_sets_contract_disputed(self):
        self.contract.status = "delivered"
        self.contract.save()
        payment = self.contract.payment
        payment.status = "refunded"
        payment.save()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "disputed")

    def test_already_completed_contract_not_overwritten_on_refund_after_complete(self):
        self.contract.status = "completed"
        self.contract.save()
        payment = self.contract.payment
        payment.status = "refunded"
        payment.save()
        self.contract.refresh_from_db()
        # Payment.save() guard: refund only affects non-completed contracts
        self.assertEqual(self.contract.status, "completed")


# ── JobRequest / JobBid model str ────────────────────────────────────────────

class NewModelStrTests(TestCase):
    def setUp(self):
        _, self.student = make_user("alice", "student")
        _, self.client_profile = make_user("bob", "client")
        self.cat = make_category()
        self.job = make_job_request(self.client_profile, self.cat)
        self.jb = make_job_bid(self.job, self.student)

    def test_job_request_str(self):
        self.assertEqual(str(self.job), "Build a Website")

    def test_job_bid_str(self):
        result = str(self.jb)
        self.assertIn("alice", result)
        self.assertIn("Build a Website", result)

    def test_notification_str(self):
        notif = Notification.objects.create(
            recipient=self.student, message="Hello!", url="/dashboard/"
        )
        self.assertIn("alice", str(notif))
        self.assertIn("Hello!", str(notif))


# ── JobRequestForm and JobBidForm ────────────────────────────────────────────

class JobFormTests(TestCase):
    def setUp(self):
        self.cat = make_category()

    def test_job_request_form_valid(self):
        form = JobRequestForm(data={
            "category": self.cat.pk, "title": "Build App",
            "description": "Need an app.", "budget": "250.00",
        })
        self.assertTrue(form.is_valid())

    def test_job_request_form_missing_title(self):
        form = JobRequestForm(data={
            "category": self.cat.pk, "title": "",
            "description": "x", "budget": "100.00",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_job_bid_form_valid(self):
        form = JobBidForm(data={"proposed_price": "100.00", "message": "I'll do it."})
        self.assertTrue(form.is_valid())

    def test_job_bid_form_missing_message(self):
        form = JobBidForm(data={"proposed_price": "100.00", "message": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("message", form.errors)

    def test_contract_message_form_valid(self):
        form = ContractMessageForm(data={"body": "Hello there."})
        self.assertTrue(form.is_valid())

    def test_contract_message_form_empty_body(self):
        form = ContractMessageForm(data={"body": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("body", form.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW TESTS — end-to-end use-case simulations
# These mirror real user journeys through the browser, catching integration
# bugs that unit tests miss (template crashes, wrong redirects, missing guards).
# ═══════════════════════════════════════════════════════════════════════════════


# ── WF-1: Complete gig lifecycle (happy path) ────────────────────────────────

class WorkflowGigHappyPath(TestCase):
    """
    Student registers → KYC → posts listing →
    Client registers → KYC → places bid →
    Student accepts bid → contract created, payment held →
    Student submits work → client accepts → payment released →
    Both parties leave reviews → reviews visible on profiles.
    """

    def _register(self, username, role):
        self.client.post(reverse("register"), {
            "username": username, "password": "pass1234", "role": role,
        })
        self.client.logout()
        return User.objects.get(username=username)

    def _kyc(self, username):
        self.client.login(username=username, password="pass1234")
        self.client.post(reverse("kyc_self_verify"))
        self.client.logout()

    def setUp(self):
        self.cat = make_category("Programming")
        self.student_user = self._register("wf_student", "student")
        self.client_user = self._register("wf_client", "client")
        self._kyc("wf_student")
        self._kyc("wf_client")
        self.student = self.student_user.userprofile
        self.client_profile = self.client_user.userprofile

    def test_full_gig_lifecycle(self):
        # 1. Student posts a service listing
        self.client.login(username="wf_student", password="pass1234")
        resp = self.client.post(reverse("listing_create"), {
            "category": self.cat.pk,
            "title": "WF Gig: Build a site",
            "description": "I build sites.",
            "price": "100.00",
            "is_remote": True,
        })
        self.assertEqual(resp.status_code, 302)
        listing = ServiceListing.objects.get(title="WF Gig: Build a site")
        self.client.logout()

        # 2. Client browses listings and sees the new listing
        resp = self.client.get(reverse("listing_list"))
        self.assertContains(resp, "WF Gig: Build a site")

        # 3. Client places a bid
        self.client.login(username="wf_client", password="pass1234")
        resp = self.client.post(reverse("place_bid", args=[listing.pk]), {
            "proposed_price": "90.00",
            "message": "I need this done.",
        })
        self.assertEqual(resp.status_code, 302)
        bid = Bid.objects.get(listing=listing, client=self.client_profile)
        self.assertEqual(bid.status, "pending")
        self.client.logout()

        # 4. Student sees the bid on the dashboard
        self.client.login(username="wf_student", password="pass1234")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "Bids Received")
        self.assertContains(resp, "wf_client")

        # 5. Student accepts the bid
        resp = self.client.post(reverse("bid_accept", args=[bid.pk]))
        self.assertEqual(resp.status_code, 302)
        bid.refresh_from_db()
        self.assertEqual(bid.status, "accepted")
        contract = Contract.objects.get(bid=bid)
        self.assertEqual(contract.status, "active")
        self.assertEqual(contract.payment.status, "held")
        self.assertEqual(contract.listing_title, "WF Gig: Build a site")

        # 6. Student submits work
        resp = self.client.post(reverse("contract_complete", args=[contract.pk]))
        self.assertEqual(resp.status_code, 302)
        contract.refresh_from_db()
        self.assertEqual(contract.status, "delivered")
        self.assertEqual(contract.payment.status, "held")
        self.client.logout()

        # 7. Client sees "Review Delivery" on contract detail
        self.client.login(username="wf_client", password="pass1234")
        resp = self.client.get(reverse("contract_detail", args=[contract.pk]))
        self.assertContains(resp, "Review Delivery")

        # 8. Client accepts delivery
        resp = self.client.post(reverse("contract_accept", args=[contract.pk]))
        self.assertEqual(resp.status_code, 302)
        contract.refresh_from_db()
        self.assertEqual(contract.status, "completed")
        contract.payment.refresh_from_db()
        self.assertEqual(contract.payment.status, "released")

        # 9. Client leaves a review for student
        resp = self.client.post(reverse("review_create", args=[contract.pk]), {
            "rating": "5",
            "comment": "Great work!",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Review.objects.filter(
            contract=contract, reviewer=self.client_profile, rating=5
        ).exists())
        self.client.logout()

        # 10. Student leaves a review for client
        self.client.login(username="wf_student", password="pass1234")
        resp = self.client.post(reverse("review_create", args=[contract.pk]), {
            "rating": "4",
            "comment": "Good client.",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Review.objects.filter(contract=contract).count(), 2)
        self.client.logout()

        # 11. Reviews are visible on student's public profile
        resp = self.client.get(reverse("profile_detail", args=[self.student_user.pk]))
        self.assertContains(resp, "Great work!")

        # 12. Reviews are visible on client's public profile
        resp = self.client.get(reverse("profile_detail", args=[self.client_user.pk]))
        self.assertContains(resp, "Good client.")

    def test_listing_closed_after_bid_accepted(self):
        listing = make_listing(self.student, self.cat, title="WF Closed Test")
        bid = make_bid(listing, self.client_profile)
        self.client.login(username="wf_student", password="pass1234")
        self.client.post(reverse("bid_accept", args=[bid.pk]))
        listing.refresh_from_db()
        self.assertFalse(listing.is_active)
        # Listing no longer appears in public browse
        resp = self.client.get(reverse("listing_list"))
        self.assertNotContains(resp, "WF Closed Test")

    def test_other_bids_rejected_when_one_accepted(self):
        listing = make_listing(self.student, self.cat, title="WF Multi-Bid")
        bid1 = make_bid(listing, self.client_profile)
        _, client2 = make_user("wf_client2", "client", kyc=True)
        bid2 = make_bid(listing, client2)
        self.client.login(username="wf_student", password="pass1234")
        self.client.post(reverse("bid_accept", args=[bid1.pk]))
        bid2.refresh_from_db()
        self.assertEqual(bid2.status, "rejected")

    def test_cannot_double_review(self):
        listing = make_listing(self.student, self.cat)
        bid = make_bid(listing, self.client_profile)
        contract = make_contract(bid, self.student, self.client_profile, status="completed")
        self.client.login(username="wf_client", password="pass1234")
        self.client.post(reverse("review_create", args=[contract.pk]), {"rating": "5"})
        resp = self.client.post(reverse("review_create", args=[contract.pk]), {"rating": "4"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Review.objects.filter(contract=contract, reviewer=self.client_profile).count(), 1)

    def test_cannot_review_incomplete_contract(self):
        listing = make_listing(self.student, self.cat)
        bid = make_bid(listing, self.client_profile)
        contract = make_contract(bid, self.student, self.client_profile, status="active")
        self.client.login(username="wf_client", password="pass1234")
        resp = self.client.get(reverse("review_create", args=[contract.pk]))
        self.assertEqual(resp.status_code, 400)

    def test_third_party_cannot_review(self):
        listing = make_listing(self.student, self.cat)
        bid = make_bid(listing, self.client_profile)
        contract = make_contract(bid, self.student, self.client_profile, status="completed")
        _, outsider = make_user("wf_outsider", "client", kyc=True)
        self.client.login(username="wf_outsider", password="pass")
        resp = self.client.post(reverse("review_create", args=[contract.pk]), {"rating": "5"})
        self.assertEqual(resp.status_code, 403)


# ── WF-2: Gig dispute workflow ───────────────────────────────────────────────

class WorkflowGigDispute(TestCase):
    """
    Student delivers → client raises dispute →
    Contract moves to 'disputed' → payment stays held →
    Admin releases payment → contract becomes 'completed', visible to both →
    Admin refunds payment → contract stays 'disputed', payment 'refunded'.
    """

    def setUp(self):
        _, self.student = make_user("dis_student", "student", kyc=True)
        _, self.client_profile = make_user("dis_client", "client", kyc=True)
        self.cat = make_category("Design")
        listing = make_listing(self.student, self.cat, title="WF Dispute Service")
        bid = make_bid(listing, self.client_profile)
        self.contract = make_contract(bid, self.student, self.client_profile, status="delivered")

    def test_client_raises_dispute(self):
        self.client.login(username="dis_client", password="pass")
        resp = self.client.post(reverse("contract_reject", args=[self.contract.pk]))
        self.assertEqual(resp.status_code, 302)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "disputed")
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "held")

    def test_disputed_contract_visible_to_both_parties(self):
        self.contract.status = "disputed"
        self.contract.save()
        for username in ("dis_student", "dis_client"):
            self.client.login(username=username, password="pass")
            resp = self.client.get(reverse("contract_detail", args=[self.contract.pk]))
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Disputed")
            self.client.logout()

    def test_admin_release_resolves_dispute(self):
        self.contract.status = "disputed"
        self.contract.save()
        admin_obj = ContractAdmin(Contract, AdminSite())
        req = make_admin_request()
        admin_obj.release_payment(req, Contract.objects.filter(pk=self.contract.pk))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "completed")
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "released")

    def test_admin_refund_keeps_dispute_status(self):
        self.contract.status = "disputed"
        self.contract.save()
        admin_obj = ContractAdmin(Contract, AdminSite())
        req = make_admin_request()
        admin_obj.refund_payment(req, Contract.objects.filter(pk=self.contract.pk))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "disputed")
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "refunded")

    def test_after_admin_release_both_parties_see_completed(self):
        """Critical: admin action must reflect to users via Payment.save() sync."""
        self.contract.status = "disputed"
        self.contract.save()
        payment = self.contract.payment
        payment.status = "released"
        payment.save()
        # Both users must now see "completed" on their contract detail
        for username in ("dis_student", "dis_client"):
            self.client.login(username=username, password="pass")
            resp = self.client.get(reverse("contract_detail", args=[self.contract.pk]))
            self.assertContains(resp, "Completed")
            self.assertNotContains(resp, "Disputed")
            self.client.logout()

    def test_admin_note_visible_after_dispute_resolution(self):
        self.contract.status = "disputed"
        self.contract.admin_note = "Admin ruled in favour of student — payment released."
        self.contract.save()
        for username in ("dis_student", "dis_client"):
            self.client.login(username=username, password="pass")
            resp = self.client.get(reverse("contract_detail", args=[self.contract.pk]))
            self.assertContains(resp, "Admin ruled in favour of student")
            self.client.logout()

    def test_student_cannot_submit_work_on_disputed_contract(self):
        self.contract.status = "disputed"
        self.contract.save()
        self.client.login(username="dis_student", password="pass")
        resp = self.client.post(reverse("contract_complete", args=[self.contract.pk]))
        self.assertEqual(resp.status_code, 400)

    def test_client_cannot_accept_disputed_contract(self):
        self.contract.status = "disputed"
        self.contract.save()
        self.client.login(username="dis_client", password="pass")
        resp = self.client.post(reverse("contract_accept", args=[self.contract.pk]))
        self.assertEqual(resp.status_code, 400)


# ── WF-3: Complete job request lifecycle (happy path) ────────────────────────

class WorkflowJobHappyPath(TestCase):
    """
    Client posts job request → student browses jobs →
    Student places bid → client accepts bid →
    Contract created → student delivers → client accepts →
    Payment released → both leave reviews.
    """

    def setUp(self):
        _, self.student = make_user("job_student", "student", kyc=True)
        _, self.client_profile = make_user("job_client", "client", kyc=True)
        self.cat = make_category("Tutoring")

    def test_full_job_lifecycle(self):
        # 1. Client posts job
        self.client.login(username="job_client", password="pass")
        resp = self.client.post(reverse("job_request_create"), {
            "category": self.cat.pk,
            "title": "WF Job: Need a tutor",
            "description": "Help me with maths.",
            "budget": "80.00",
        })
        self.assertEqual(resp.status_code, 302)
        job = JobRequest.objects.get(title="WF Job: Need a tutor")
        self.client.logout()

        # 2. Student browses jobs and sees it
        resp = self.client.get(reverse("job_request_list"))
        self.assertContains(resp, "WF Job: Need a tutor")

        # 3. Student places a bid
        self.client.login(username="job_student", password="pass")
        resp = self.client.post(reverse("job_bid_create", args=[job.pk]), {
            "proposed_price": "70.00",
            "message": "I'm a maths grad.",
        })
        self.assertEqual(resp.status_code, 302)
        jb = JobBid.objects.get(job_request=job, student=self.student)
        self.assertEqual(jb.status, "pending")
        self.client.logout()

        # 4. Client sees the bid on job detail page
        self.client.login(username="job_client", password="pass")
        resp = self.client.get(reverse("job_request_detail", args=[job.pk]))
        self.assertContains(resp, "Bids Received")
        self.assertContains(resp, "job_student")

        # 5. Client accepts the bid
        resp = self.client.post(reverse("job_bid_accept", args=[jb.pk]))
        self.assertEqual(resp.status_code, 302)
        jb.refresh_from_db()
        self.assertEqual(jb.status, "accepted")
        contract = Contract.objects.get(job_bid=jb)
        self.assertEqual(contract.status, "active")
        self.assertEqual(contract.payment.status, "held")
        self.assertEqual(contract.listing_title, "WF Job: Need a tutor")
        self.client.logout()

        # 6. Job is now closed
        job.refresh_from_db()
        self.assertFalse(job.is_active)
        resp = self.client.get(reverse("job_request_list"))
        self.assertNotContains(resp, "WF Job: Need a tutor")

        # 7. Student submits work
        self.client.login(username="job_student", password="pass")
        self.client.post(reverse("contract_complete", args=[contract.pk]))
        contract.refresh_from_db()
        self.assertEqual(contract.status, "delivered")
        self.client.logout()

        # 8. Client accepts delivery
        self.client.login(username="job_client", password="pass")
        self.client.post(reverse("contract_accept", args=[contract.pk]))
        contract.refresh_from_db()
        self.assertEqual(contract.status, "completed")
        contract.payment.refresh_from_db()
        self.assertEqual(contract.payment.status, "released")

        # 9. Client reviews student
        resp = self.client.post(reverse("review_create", args=[contract.pk]), {
            "rating": "5", "comment": "Excellent tutor!",
        })
        self.assertEqual(resp.status_code, 302)
        self.client.logout()

        # 10. Student reviews client
        self.client.login(username="job_student", password="pass")
        resp = self.client.post(reverse("review_create", args=[contract.pk]), {
            "rating": "5", "comment": "Clear instructions.",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Review.objects.filter(contract=contract).count(), 2)

    def test_job_contract_shown_in_contracts_page_with_job_title(self):
        job = make_job_request(self.client_profile, self.cat, title="Test Job Title")
        jb = make_job_bid(job, self.student)
        self.client.login(username="job_client", password="pass")
        self.client.post(reverse("job_bid_accept", args=[jb.pk]))
        contract = Contract.objects.get(job_bid=jb)
        self.client.logout()
        for username in ("job_student", "job_client"):
            self.client.login(username=username, password="pass")
            resp = self.client.get(reverse("contracts"))
            self.assertContains(resp, "Test Job Title")
            self.client.logout()

    def test_review_form_renders_job_title_not_crash(self):
        """review_form.html must use contract.listing_title not contract.bid.listing.title."""
        job = make_job_request(self.client_profile, self.cat)
        jb = make_job_bid(job, self.student)
        contract = make_job_contract(jb, self.student, self.client_profile, status="completed")
        self.client.login(username="job_client", password="pass")
        resp = self.client.get(reverse("review_create", args=[contract.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, job.title)


# ── WF-4: Job request dispute workflow ───────────────────────────────────────

class WorkflowJobDispute(TestCase):
    def setUp(self):
        _, self.student = make_user("jd_student", "student", kyc=True)
        _, self.client_profile = make_user("jd_client", "client", kyc=True)
        self.cat = make_category()
        job = make_job_request(self.client_profile, self.cat)
        jb = make_job_bid(job, self.student)
        self.contract = make_job_contract(jb, self.student, self.client_profile, status="delivered")

    def test_client_raises_dispute_on_job_contract(self):
        self.client.login(username="jd_client", password="pass")
        resp = self.client.post(reverse("contract_reject", args=[self.contract.pk]))
        self.assertEqual(resp.status_code, 302)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "disputed")

    def test_admin_releases_payment_on_job_dispute(self):
        self.contract.status = "disputed"
        self.contract.save()
        payment = self.contract.payment
        payment.status = "released"
        payment.save()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "completed")

    def test_both_parties_see_resolved_status(self):
        self.contract.status = "disputed"
        self.contract.save()
        payment = self.contract.payment
        payment.status = "released"
        payment.save()
        for username in ("jd_student", "jd_client"):
            self.client.login(username=username, password="pass")
            resp = self.client.get(reverse("contract_detail", args=[self.contract.pk]))
            self.assertContains(resp, "Completed")
            self.client.logout()


# ── WF-5: Role guard workflow ────────────────────────────────────────────────

class WorkflowRoleGuards(TestCase):
    """Comprehensive role separation — no user should be able to access
    actions that belong to the other role."""

    def setUp(self):
        _, self.student = make_user("rg_student", "student", kyc=True)
        _, self.client_profile = make_user("rg_client", "client", kyc=True)
        _, self.unverified_student = make_user("rg_unverified_s", "student", kyc=False)
        _, self.unverified_client = make_user("rg_unverified_c", "client", kyc=False)
        self.cat = make_category()
        self.listing = make_listing(self.student, self.cat)
        self.job = make_job_request(self.client_profile, self.cat)

    # Students cannot create job requests
    def test_student_cannot_create_job_request_get(self):
        self.client.login(username="rg_student", password="pass")
        resp = self.client.get(reverse("job_request_create"))
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_create_job_request_post(self):
        self.client.login(username="rg_student", password="pass")
        resp = self.client.post(reverse("job_request_create"), {
            "category": self.cat.pk, "title": "x", "description": "x", "budget": "10.00",
        })
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(JobRequest.objects.filter(title="x").exists())

    # Clients cannot create service listings
    def test_client_cannot_create_listing_get(self):
        self.client.login(username="rg_client", password="pass")
        resp = self.client.get(reverse("listing_create"))
        self.assertEqual(resp.status_code, 403)

    def test_client_cannot_create_listing_post(self):
        self.client.login(username="rg_client", password="pass")
        resp = self.client.post(reverse("listing_create"), {
            "category": self.cat.pk, "title": "x", "description": "x",
            "price": "10.00", "is_remote": True,
        })
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(ServiceListing.objects.filter(title="x").exists())

    # Students cannot bid on service listings (only clients can)
    def test_student_cannot_bid_on_service_listing(self):
        self.client.login(username="rg_student", password="pass")
        resp = self.client.post(reverse("place_bid", args=[self.listing.pk]), {
            "proposed_price": "50.00", "message": "hi",
        })
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access_bid_form_for_listing(self):
        self.client.login(username="rg_student", password="pass")
        resp = self.client.get(reverse("place_bid", args=[self.listing.pk]))
        self.assertEqual(resp.status_code, 403)

    # Clients cannot bid on job requests (only students can)
    def test_client_cannot_bid_on_job_request(self):
        self.client.login(username="rg_client", password="pass")
        resp = self.client.post(reverse("job_bid_create", args=[self.job.pk]), {
            "proposed_price": "50.00", "message": "hi",
        })
        self.assertEqual(resp.status_code, 403)

    def test_client_cannot_access_job_bid_form(self):
        self.client.login(username="rg_client", password="pass")
        resp = self.client.get(reverse("job_bid_create", args=[self.job.pk]))
        self.assertEqual(resp.status_code, 403)

    # Unverified users cannot transact
    def test_unverified_student_cannot_post_listing(self):
        self.client.login(username="rg_unverified_s", password="pass")
        resp = self.client.get(reverse("listing_create"))
        self.assertEqual(resp.status_code, 403)

    def test_unverified_student_cannot_bid_on_job(self):
        self.client.login(username="rg_unverified_s", password="pass")
        resp = self.client.get(reverse("job_bid_create", args=[self.job.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_unverified_client_cannot_bid_on_listing(self):
        self.client.login(username="rg_unverified_c", password="pass")
        resp = self.client.get(reverse("place_bid", args=[self.listing.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_unverified_client_cannot_post_job_request(self):
        self.client.login(username="rg_unverified_c", password="pass")
        resp = self.client.get(reverse("job_request_create"))
        self.assertEqual(resp.status_code, 403)

    # Only the listing owner (student) can accept/reject service bids
    def test_client_cannot_accept_their_own_bid(self):
        bid = make_bid(self.listing, self.client_profile)
        self.client.login(username="rg_client", password="pass")
        resp = self.client.post(reverse("bid_accept", args=[bid.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_accept_job_bid_on_their_own_bid(self):
        jb = make_job_bid(self.job, self.student)
        self.client.login(username="rg_student", password="pass")
        resp = self.client.post(reverse("job_bid_accept", args=[jb.pk]))
        self.assertEqual(resp.status_code, 403)

    # Only student on a contract can submit work
    def test_client_cannot_submit_work(self):
        bid = make_bid(self.listing, self.client_profile)
        contract = make_contract(bid, self.student, self.client_profile)
        self.client.login(username="rg_client", password="pass")
        resp = self.client.post(reverse("contract_complete", args=[contract.pk]))
        self.assertEqual(resp.status_code, 403)

    # Only client on a contract can accept/reject delivery
    def test_student_cannot_accept_their_own_delivery(self):
        bid = make_bid(self.listing, self.client_profile)
        contract = make_contract(bid, self.student, self.client_profile, status="delivered")
        self.client.login(username="rg_student", password="pass")
        resp = self.client.post(reverse("contract_accept", args=[contract.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_reject_their_own_delivery(self):
        bid = make_bid(self.listing, self.client_profile)
        contract = make_contract(bid, self.student, self.client_profile, status="delivered")
        self.client.login(username="rg_student", password="pass")
        resp = self.client.post(reverse("contract_reject", args=[contract.pk]))
        self.assertEqual(resp.status_code, 403)


# ── WF-6: Dashboard role separation ─────────────────────────────────────────

class WorkflowDashboardSeparation(TestCase):
    """Verify that student and client dashboards show only role-appropriate
    content and do not leak cross-role data."""

    def setUp(self):
        _, self.student = make_user("dd_student", "student", kyc=True)
        _, self.client_profile = make_user("dd_client", "client", kyc=True)
        self.cat = make_category()
        listing = make_listing(self.student, self.cat)
        bid = make_bid(listing, self.client_profile)
        self.contract = make_contract(bid, self.student, self.client_profile)
        self.job = make_job_request(self.client_profile, self.cat, title="DD Job")

    def test_student_dashboard_shows_work_section(self):
        self.client.login(username="dd_student", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "Your Work (as Student)")

    def test_student_dashboard_does_not_show_hires(self):
        self.client.login(username="dd_student", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertNotContains(resp, "Your Hires (as Client)")

    def test_student_dashboard_shows_received_bids(self):
        listing2 = make_listing(self.student, self.cat, title="Student Listing 2")
        _, c2 = make_user("dd_c2", "client", kyc=True)
        make_bid(listing2, c2)
        self.client.login(username="dd_student", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "Bids Received")

    def test_student_dashboard_has_browse_jobs_link(self):
        self.client.login(username="dd_student", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, reverse("job_request_list"))

    def test_client_dashboard_shows_hires_section(self):
        self.client.login(username="dd_client", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "Your Hires (as Client)")

    def test_client_dashboard_does_not_show_work_section(self):
        self.client.login(username="dd_client", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertNotContains(resp, "Your Work (as Student)")

    def test_client_dashboard_shows_submitted_bids(self):
        self.client.login(username="dd_client", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "Your Submitted Bids")

    def test_client_dashboard_shows_job_requests(self):
        self.client.login(username="dd_client", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "DD Job")

    def test_client_dashboard_has_post_job_link(self):
        self.client.login(username="dd_client", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, reverse("job_request_create"))

    def test_navbar_shows_post_service_for_student(self):
        self.client.login(username="dd_student", password="pass")
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "Post a Service")
        self.assertNotContains(resp, "Post a Job")

    def test_navbar_shows_post_job_for_client(self):
        self.client.login(username="dd_client", password="pass")
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "Post a Job")
        self.assertNotContains(resp, "Post a Service")

    def test_student_only_sees_own_contracts(self):
        _, student2 = make_user("dd_student2", "student", kyc=True)
        _, client2 = make_user("dd_client2", "client", kyc=True)
        listing2 = make_listing(student2, self.cat, title="Other Student Listing")
        bid2 = make_bid(listing2, client2)
        contract2 = make_contract(bid2, student2, client2)
        self.client.login(username="dd_student", password="pass")
        resp = self.client.get(reverse("dashboard"))
        # Should see own contract, not the other student's
        self.assertContains(resp, f"Contract #{self.contract.pk}")
        self.assertNotContains(resp, f"Contract #{contract2.pk}")


# ── WF-7: Messaging workflow ─────────────────────────────────────────────────

class WorkflowMessaging(TestCase):
    def setUp(self):
        _, self.student = make_user("msg_student", "student", kyc=True)
        _, self.client_profile = make_user("msg_client", "client", kyc=True)
        _, self.outsider = make_user("msg_outsider", "client", kyc=True)
        self.cat = make_category()
        listing = make_listing(self.student, self.cat)
        bid = make_bid(listing, self.client_profile)
        self.contract = make_contract(bid, self.student, self.client_profile)

    def test_student_sends_message_visible_to_client(self):
        self.client.login(username="msg_student", password="pass")
        self.client.post(reverse("contract_message_create", args=[self.contract.pk]),
                         {"body": "Work started!"})
        self.client.logout()
        self.client.login(username="msg_client", password="pass")
        resp = self.client.get(reverse("contract_detail", args=[self.contract.pk]))
        self.assertContains(resp, "Work started!")

    def test_client_sends_message_visible_to_student(self):
        self.client.login(username="msg_client", password="pass")
        self.client.post(reverse("contract_message_create", args=[self.contract.pk]),
                         {"body": "Please update me."})
        self.client.logout()
        self.client.login(username="msg_student", password="pass")
        resp = self.client.get(reverse("contract_detail", args=[self.contract.pk]))
        self.assertContains(resp, "Please update me.")

    def test_outsider_cannot_message(self):
        self.client.login(username="msg_outsider", password="pass")
        resp = self.client.post(reverse("contract_message_create", args=[self.contract.pk]),
                                {"body": "Intruding."})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(ContractMessage.objects.filter(body="Intruding.").exists())

    def test_messages_ordered_chronologically(self):
        ContractMessage.objects.create(contract=self.contract, sender=self.student, body="First")
        ContractMessage.objects.create(contract=self.contract, sender=self.client_profile, body="Second")
        self.client.login(username="msg_student", password="pass")
        resp = self.client.get(reverse("contract_detail", args=[self.contract.pk]))
        content = resp.content.decode()
        self.assertLess(content.index("First"), content.index("Second"))

    def test_message_creates_notification_for_other_party(self):
        self.client.login(username="msg_student", password="pass")
        self.client.post(reverse("contract_message_create", args=[self.contract.pk]),
                         {"body": "Ping!"})
        notif = Notification.objects.filter(recipient=self.client_profile).last()
        self.assertIsNotNone(notif)
        self.assertIn(str(self.contract.pk), notif.message)

    def test_message_does_not_notify_sender(self):
        initial = Notification.objects.filter(recipient=self.student).count()
        self.client.login(username="msg_student", password="pass")
        self.client.post(reverse("contract_message_create", args=[self.contract.pk]),
                         {"body": "Self-message test."})
        self.assertEqual(
            Notification.objects.filter(recipient=self.student).count(), initial
        )


# ── WF-8: Bid management workflow ────────────────────────────────────────────

class WorkflowBidManagement(TestCase):
    def setUp(self):
        _, self.student = make_user("bm_student", "student", kyc=True)
        _, self.client_profile = make_user("bm_client", "client", kyc=True)
        _, self.client2 = make_user("bm_client2", "client", kyc=True)
        self.cat = make_category()
        self.listing = make_listing(self.student, self.cat, title="BM Listing")

    def test_client_can_edit_pending_bid(self):
        bid = make_bid(self.listing, self.client_profile, price="50.00")
        self.client.login(username="bm_client", password="pass")
        resp = self.client.post(reverse("bid_edit", args=[bid.pk]), {
            "proposed_price": "65.00", "message": "Revised offer.",
        })
        self.assertEqual(resp.status_code, 302)
        bid.refresh_from_db()
        self.assertEqual(bid.proposed_price, Decimal("65.00"))

    def test_client_can_withdraw_pending_bid(self):
        bid = make_bid(self.listing, self.client_profile)
        self.client.login(username="bm_client", password="pass")
        resp = self.client.post(reverse("bid_delete", args=[bid.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Bid.objects.filter(pk=bid.pk).exists())

    def test_cannot_place_duplicate_bid(self):
        make_bid(self.listing, self.client_profile)
        self.client.login(username="bm_client", password="pass")
        resp = self.client.post(reverse("place_bid", args=[self.listing.pk]), {
            "proposed_price": "55.00", "message": "Second try.",
        })
        # Redirected with error — only 1 bid exists
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Bid.objects.filter(listing=self.listing, client=self.client_profile).count(), 1)

    def test_student_sees_all_bids_on_their_listing(self):
        make_bid(self.listing, self.client_profile, price="50.00")
        make_bid(self.listing, self.client2, price="60.00")
        self.client.login(username="bm_student", password="pass")
        resp = self.client.get(reverse("listing_detail", args=[self.listing.pk]))
        self.assertContains(resp, "bm_client")
        self.assertContains(resp, "bm_client2")

    def test_rejected_bid_still_visible_to_client(self):
        bid = make_bid(self.listing, self.client_profile)
        self.client.login(username="bm_student", password="pass")
        self.client.post(reverse("bid_reject", args=[bid.pk]))
        self.client.logout()
        self.client.login(username="bm_client", password="pass")
        resp = self.client.get(reverse("listing_detail", args=[self.listing.pk]))
        self.assertContains(resp, "Rejected")

    def test_accepted_bid_cannot_be_withdrawn(self):
        bid = make_bid(self.listing, self.client_profile, status="accepted")
        self.client.login(username="bm_client", password="pass")
        resp = self.client.post(reverse("bid_delete", args=[bid.pk]))
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(Bid.objects.filter(pk=bid.pk).exists())

    def test_rejected_bid_cannot_be_edited(self):
        bid = make_bid(self.listing, self.client_profile, status="rejected")
        self.client.login(username="bm_client", password="pass")
        resp = self.client.get(reverse("bid_edit", args=[bid.pk]))
        self.assertEqual(resp.status_code, 400)


# ── WF-9: Admin workflow ─────────────────────────────────────────────────────

class WorkflowAdmin(TestCase):
    def setUp(self):
        _, self.student = make_user("adm_student", "student", kyc=False)
        _, self.client_profile = make_user("adm_client", "client", kyc=True)
        self.cat = make_category()
        listing = make_listing(self.student, self.cat)
        # Override KYC guard for setup only
        self.student.is_kyc_verified = True
        self.student.save()
        bid = make_bid(listing, self.client_profile)
        self.student.is_kyc_verified = False
        self.student.save()
        self.contract = make_contract(bid, self.student, self.client_profile, status="delivered")
        self.admin_obj = ContractAdmin(Contract, AdminSite())

    def test_admin_kyc_toggle_on_unverified_profile(self):
        admin_obj = UserProfileAdmin(UserProfile, AdminSite())
        qs = UserProfile.objects.filter(pk=self.student.pk)
        admin_obj.toggle_kyc(None, qs)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_kyc_verified)

    def test_admin_kyc_toggle_off_on_verified_profile(self):
        self.student.is_kyc_verified = True
        self.student.save()
        admin_obj = UserProfileAdmin(UserProfile, AdminSite())
        qs = UserProfile.objects.filter(pk=self.student.pk)
        admin_obj.toggle_kyc(None, qs)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_kyc_verified)

    def test_admin_release_payment_bulk_action(self):
        req = make_admin_request()
        self.admin_obj.release_payment(req, Contract.objects.filter(pk=self.contract.pk))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "completed")
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "released")

    def test_admin_refund_payment_bulk_action(self):
        req = make_admin_request()
        self.admin_obj.refund_payment(req, Contract.objects.filter(pk=self.contract.pk))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "disputed")
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "refunded")

    def test_admin_release_via_payment_model_save(self):
        """Admin editing the payment inline directly must also update contract."""
        self.contract.status = "disputed"
        self.contract.save()
        payment = self.contract.payment
        payment.status = "released"
        payment.save()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "completed")

    def test_admin_save_model_syncs_payment_on_status_change(self):
        """ContractAdmin.save_model must sync payment when status is directly changed."""
        from django.test import RequestFactory
        from core.admin import ContractAdmin
        from core.forms import ServiceListingForm

        self.contract.status = "delivered"
        self.contract.save()

        # Simulate admin changing contract status to completed via save_model
        admin_obj = ContractAdmin(Contract, AdminSite())
        factory = RequestFactory()
        request = factory.post("/admin/")
        request.session = {}
        request._messages = FallbackStorage(request)

        # Create a minimal mock form with changed_data
        class MockForm:
            changed_data = ["status"]

        self.contract.status = "completed"
        admin_obj.save_model(request, self.contract, MockForm(), change=True)
        self.contract.payment.refresh_from_db()
        self.assertEqual(self.contract.payment.status, "released")

    def test_admin_bulk_release_skips_active_contracts(self):
        self.contract.status = "active"
        self.contract.save()
        req = make_admin_request()
        self.admin_obj.release_payment(req, Contract.objects.filter(pk=self.contract.pk))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "active")

    def test_admin_note_visible_to_both_parties_after_set(self):
        self.contract.admin_note = "Resolved: payment released by admin."
        self.contract.save()
        for username in ("adm_student", "adm_client"):
            self.client.login(username=username, password="pass")
            resp = self.client.get(reverse("contract_detail", args=[self.contract.pk]))
            self.assertContains(resp, "Resolved: payment released by admin.")
            self.client.logout()


# ── WF-10: Filtering and browsing workflow ───────────────────────────────────

class WorkflowFiltering(TestCase):
    def setUp(self):
        _, self.student = make_user("flt_student", "student", kyc=True)
        _, self.client_profile = make_user("flt_client", "client", kyc=True)
        self.cat_design = make_category("Filter Design")
        self.cat_writing = make_category("Filter Writing")
        make_listing(self.student, self.cat_design, title="Design Gig", active=True)
        ServiceListing.objects.filter(title="Design Gig").update(price=Decimal("200.00"))
        make_listing(self.student, self.cat_writing, title="Writing Gig", active=True)
        ServiceListing.objects.filter(title="Writing Gig").update(
            price=Decimal("50.00"), is_remote=False
        )
        make_job_request(self.client_profile, self.cat_design, title="Design Job", budget="300.00")
        make_job_request(self.client_profile, self.cat_writing, title="Writing Job", budget="80.00")

    def test_listing_filter_by_category(self):
        resp = self.client.get(reverse("listing_list"), {"category": self.cat_design.pk})
        self.assertContains(resp, "Design Gig")
        self.assertNotContains(resp, "Writing Gig")

    def test_listing_filter_min_price(self):
        resp = self.client.get(reverse("listing_list"), {"min_price": "100"})
        self.assertContains(resp, "Design Gig")
        self.assertNotContains(resp, "Writing Gig")

    def test_listing_filter_max_price(self):
        resp = self.client.get(reverse("listing_list"), {"max_price": "100"})
        self.assertContains(resp, "Writing Gig")
        self.assertNotContains(resp, "Design Gig")

    def test_listing_filter_remote_only(self):
        resp = self.client.get(reverse("listing_list"), {"remote": "true"})
        self.assertContains(resp, "Design Gig")
        self.assertNotContains(resp, "Writing Gig")

    def test_listing_filter_in_person_only(self):
        resp = self.client.get(reverse("listing_list"), {"remote": "false"})
        self.assertContains(resp, "Writing Gig")
        self.assertNotContains(resp, "Design Gig")

    def test_listing_sort_price_low_to_high(self):
        resp = self.client.get(reverse("listing_list"), {"sort": "price_asc"})
        content = resp.content.decode()
        self.assertLess(content.index("Writing Gig"), content.index("Design Gig"))

    def test_listing_sort_price_high_to_low(self):
        resp = self.client.get(reverse("listing_list"), {"sort": "price_desc"})
        content = resp.content.decode()
        self.assertLess(content.index("Design Gig"), content.index("Writing Gig"))

    def test_job_filter_by_category(self):
        resp = self.client.get(reverse("job_request_list"), {"category": self.cat_design.pk})
        self.assertContains(resp, "Design Job")
        self.assertNotContains(resp, "Writing Job")

    def test_job_filter_budget_max(self):
        resp = self.client.get(reverse("job_request_list"), {"budget_max": "100"})
        self.assertContains(resp, "Writing Job")
        self.assertNotContains(resp, "Design Job")

    def test_job_sort_budget_desc(self):
        resp = self.client.get(reverse("job_request_list"), {"sort": "budget_desc"})
        content = resp.content.decode()
        self.assertLess(content.index("Design Job"), content.index("Writing Job"))

    def test_anonymous_can_browse_both_markets(self):
        resp = self.client.get(reverse("listing_list"))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(reverse("job_request_list"))
        self.assertEqual(resp.status_code, 200)


# ── WF-11: KYC workflow ──────────────────────────────────────────────────────

class WorkflowKYC(TestCase):
    def setUp(self):
        _, self.student = make_user("kyc_student", "student", kyc=False)
        _, self.client_profile = make_user("kyc_client", "client", kyc=False)
        self.cat = make_category()
        # Pre-create a listing by overriding KYC for setup
        self.student.is_kyc_verified = True
        self.student.save()
        self.listing = make_listing(self.student, self.cat)
        self.job = make_job_request(self.client_profile, self.cat)
        self.student.is_kyc_verified = False
        self.student.save()

    def test_unverified_student_dashboard_shows_kyc_banner(self):
        self.client.login(username="kyc_student", password="pass")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "KYC")

    def test_simulate_kyc_verifies_student(self):
        self.client.login(username="kyc_student", password="pass")
        resp = self.client.post(reverse("kyc_self_verify"))
        self.assertEqual(resp.status_code, 302)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_kyc_verified)

    def test_simulate_kyc_verifies_client(self):
        self.client.login(username="kyc_client", password="pass")
        self.client.post(reverse("kyc_self_verify"))
        self.client_profile.refresh_from_db()
        self.assertTrue(self.client_profile.is_kyc_verified)

    def test_after_kyc_student_can_post_listing(self):
        self.client.login(username="kyc_student", password="pass")
        self.client.post(reverse("kyc_self_verify"))
        resp = self.client.get(reverse("listing_create"))
        self.assertEqual(resp.status_code, 200)

    def test_after_kyc_client_can_bid_on_listing(self):
        self.client.login(username="kyc_client", password="pass")
        self.client.post(reverse("kyc_self_verify"))
        resp = self.client.get(reverse("place_bid", args=[self.listing.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_after_kyc_student_can_bid_on_job(self):
        self.client.login(username="kyc_student", password="pass")
        self.client.post(reverse("kyc_self_verify"))
        resp = self.client.get(reverse("job_bid_create", args=[self.job.pk]))
        self.assertEqual(resp.status_code, 200)


# ── WF-12: Notification inbox workflow ──────────────────────────────────────

class WorkflowNotificationInbox(TestCase):
    def setUp(self):
        _, self.student = make_user("ni_student", "student", kyc=True)
        _, self.client_profile = make_user("ni_client", "client", kyc=True)
        self.cat = make_category()
        self.listing = make_listing(self.student, self.cat, title="NI Listing")

    def test_notification_bell_count_reflects_unread(self):
        Notification.objects.create(recipient=self.student, message="Test 1", is_read=False)
        Notification.objects.create(recipient=self.student, message="Test 2", is_read=False)
        self.client.login(username="ni_student", password="pass")
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "2")

    def test_mark_all_read_clears_bell_count(self):
        Notification.objects.create(recipient=self.student, message="Test", is_read=False)
        self.client.login(username="ni_student", password="pass")
        self.client.post(reverse("notifications_mark_read"))
        resp = self.client.get(reverse("home"))
        # After marking read, count should be 0 — badge should not appear
        self.assertEqual(
            Notification.objects.filter(recipient=self.student, is_read=False).count(), 0
        )

    def test_full_notification_flow_from_bid_to_completion(self):
        """All key events generate the correct notifications end-to-end."""
        # Bid placed → student gets notified
        self.client.login(username="ni_client", password="pass")
        self.client.post(reverse("place_bid", args=[self.listing.pk]), {
            "proposed_price": "80.00", "message": "I need this.",
        })
        self.client.logout()
        self.assertGreater(
            Notification.objects.filter(recipient=self.student, is_read=False).count(), 0
        )

        # Bid accepted → client gets notified
        self.client.login(username="ni_student", password="pass")
        bid2 = Bid.objects.filter(listing=self.listing, status="pending").first()
        if bid2:
            self.client.post(reverse("bid_accept", args=[bid2.pk]))
        self.client.logout()
        self.assertGreater(
            Notification.objects.filter(recipient=self.client_profile, is_read=False).count(), 0
        )

    def test_notifications_page_shows_all_for_user(self):
        Notification.objects.create(recipient=self.student, message="Notif A")
        Notification.objects.create(recipient=self.student, message="Notif B")
        Notification.objects.create(recipient=self.client_profile, message="Client Notif")
        self.client.login(username="ni_student", password="pass")
        resp = self.client.get(reverse("notifications_list"))
        self.assertContains(resp, "Notif A")
        self.assertContains(resp, "Notif B")
        self.assertNotContains(resp, "Client Notif")

    def test_unauthenticated_cannot_access_notifications(self):
        resp = self.client.get(reverse("notifications_list"))
        self.assertEqual(resp.status_code, 302)


# ── WF-13: Public profile and review visibility ──────────────────────────────

class WorkflowProfileReviews(TestCase):
    def setUp(self):
        _, self.student = make_user("pr_student", "student", kyc=True)
        _, self.client_profile = make_user("pr_client", "client", kyc=True)
        self.cat = make_category()
        listing = make_listing(self.student, self.cat, title="PR Service")
        bid = make_bid(listing, self.client_profile)
        self.contract = make_contract(bid, self.student, self.client_profile, status="completed")

    def test_student_profile_shows_active_listings(self):
        make_listing(self.student, self.cat, title="Active PR Service")
        resp = self.client.get(reverse("profile_detail", args=[self.student.user.pk]))
        self.assertContains(resp, "Active PR Service")

    def test_student_profile_does_not_show_inactive_listings(self):
        make_listing(self.student, self.cat, title="Inactive PR", active=False)
        resp = self.client.get(reverse("profile_detail", args=[self.student.user.pk]))
        self.assertNotContains(resp, "Inactive PR")

    def test_client_profile_shows_no_listings_section(self):
        resp = self.client.get(reverse("profile_detail", args=[self.client_profile.user.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_reviews_visible_on_profile_after_submission(self):
        Review.objects.create(
            contract=self.contract, reviewer=self.client_profile,
            reviewee=self.student, rating=5, comment="Outstanding work!"
        )
        resp = self.client.get(reverse("profile_detail", args=[self.student.user.pk]))
        self.assertContains(resp, "Outstanding work!")

    def test_review_shows_star_rating_indicator(self):
        Review.objects.create(
            contract=self.contract, reviewer=self.client_profile,
            reviewee=self.student, rating=4, comment=""
        )
        resp = self.client.get(reverse("profile_detail", args=[self.student.user.pk]))
        # Profile template renders stars — check rating value appears
        self.assertContains(resp, "4")

    def test_anonymous_can_view_profile(self):
        resp = self.client.get(reverse("profile_detail", args=[self.student.user.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "pr_student")

    def test_profile_not_found_returns_404(self):
        resp = self.client.get(reverse("profile_detail", args=[9999]))
        self.assertEqual(resp.status_code, 404)
