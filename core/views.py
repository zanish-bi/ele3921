from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.auth import login
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages

from .models import (
    UserProfile, Category, ServiceListing, Bid, Contract, Payment, Review,
    JobRequest, JobBid, ContractMessage, Notification,
)
from .forms import (
    BidForm, ServiceListingForm, UserRegisterForm, ReviewForm,
    JobRequestForm, JobBidForm, ContractMessageForm,
)


# ── Notification helper ───────────────────────────────────────────────────────

def _notify(recipient, message, url=""):
    Notification.objects.create(recipient=recipient, message=message, url=url)


# ── Public pages ──────────────────────────────────────────────────────────────

def home(request):
    return render(request, "core/index.html")


# ── Service listings ──────────────────────────────────────────────────────────

def listing_list(request):
    listings = ServiceListing.objects.filter(is_active=True).select_related("owner", "category")
    categories = Category.objects.all()

    category_id = request.GET.get("category")
    if category_id:
        listings = listings.filter(category_id=category_id)

    min_price = request.GET.get("min_price")
    if min_price:
        try:
            listings = listings.filter(price__gte=float(min_price))
        except ValueError:
            pass

    max_price = request.GET.get("max_price")
    if max_price:
        try:
            listings = listings.filter(price__lte=float(max_price))
        except ValueError:
            pass

    remote = request.GET.get("remote")
    if remote in ("true", "false"):
        listings = listings.filter(is_remote=(remote == "true"))

    sort = request.GET.get("sort", "newest")
    if sort == "price_asc":
        listings = listings.order_by("price")
    elif sort == "price_desc":
        listings = listings.order_by("-price")
    else:
        listings = listings.order_by("-created_at")

    return render(request, "core/listing_list.html", {
        "listings": listings,
        "categories": categories,
        "sort": sort,
    })


def listing_detail(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk)
    bids = None
    my_bid = None
    can_bid = False
    is_owner = False
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile:
            if profile == listing.owner:
                is_owner = True
                bids = listing.bids.select_related("client").all()
            elif profile.role == "client":
                my_bid = listing.bids.filter(client=profile).first()
                can_bid = listing.is_active and profile.is_kyc_verified and my_bid is None
    return render(request, "core/listing_detail.html", {
        "listing": listing,
        "bids": bids,
        "my_bid": my_bid,
        "can_bid": can_bid,
        "is_owner": is_owner,
    })


@login_required
def listing_create(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != "student":
        return HttpResponseForbidden("Only students can create listings.")
    if not profile.is_kyc_verified:
        messages.error(request, "KYC verification is required to post a service. Use the 'Simulate KYC Verification' button on your dashboard.")
        return redirect("dashboard")
    if request.method == "POST":
        form = ServiceListingForm(request.POST)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.owner = profile
            listing.save()
            messages.success(request, "Listing created successfully")
            return redirect("listing_detail", pk=listing.pk)
    else:
        form = ServiceListingForm()
    return render(request, "core/listing_create.html", {"form": form, "editing": False})


@login_required
def listing_edit(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if listing.owner != profile:
        return HttpResponseForbidden("You can only edit your own listings.")
    if request.method == "POST":
        form = ServiceListingForm(request.POST, instance=listing)
        if form.is_valid():
            form.save()
            messages.success(request, "Listing updated.")
            return redirect("listing_detail", pk=listing.pk)
    else:
        form = ServiceListingForm(instance=listing)
    return render(request, "core/listing_create.html", {"form": form, "editing": True, "listing": listing})


# ── Service listing bids ──────────────────────────────────────────────────────

@login_required
def place_bid(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk, is_active=True)
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != "client":
        return HttpResponseForbidden("Only clients can place bids.")
    if not profile.is_kyc_verified:
        messages.error(request, "KYC verification is required to place a bid. Use the 'Simulate KYC Verification' button on your dashboard.")
        return redirect("listing_detail", pk=listing.pk)
    if Bid.objects.filter(listing=listing, client=profile, status="pending").exists():
        messages.error(request, "You already have a pending bid on this listing.")
        return redirect("listing_detail", pk=listing.pk)
    if request.method == "POST":
        form = BidForm(request.POST)
        if form.is_valid():
            bid = form.save(commit=False)
            bid.listing = listing
            bid.client = profile
            bid.save()
            _notify(
                listing.owner,
                f"New bid of ${bid.proposed_price} from {profile.user.username} on '{listing.title}'",
                f"/listings/{listing.pk}/",
            )
            messages.success(request, "Bid submitted. The service provider will be notified.")
            return redirect("listing_detail", pk=listing.pk)
    else:
        form = BidForm()
    return render(request, "core/place_bid.html", {"form": form, "listing": listing})


@login_required
def bid_edit(request, pk):
    bid = get_object_or_404(Bid, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if bid.client != profile:
        return HttpResponseForbidden("You can only edit your own bids.")
    if bid.status != "pending":
        return HttpResponseBadRequest("Only pending bids can be edited.")
    if request.method == "POST":
        form = BidForm(request.POST, instance=bid)
        if form.is_valid():
            form.save()
            messages.success(request, "Bid updated.")
            return redirect("listing_detail", pk=bid.listing.pk)
    else:
        form = BidForm(instance=bid)
    return render(request, "core/place_bid.html", {
        "form": form, "listing": bid.listing, "editing_bid": True, "bid": bid,
    })


@login_required
@require_POST
def bid_delete(request, pk):
    bid = get_object_or_404(Bid, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if bid.client != profile:
        return HttpResponseForbidden("You can only withdraw your own bids.")
    if bid.status != "pending":
        return HttpResponseBadRequest("Only pending bids can be withdrawn.")
    listing_pk = bid.listing.pk
    bid.delete()
    messages.success(request, "Bid withdrawn.")
    return redirect("listing_detail", pk=listing_pk)


@login_required
@require_POST
def bid_accept(request, pk):
    bid = get_object_or_404(Bid, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if bid.listing.owner != profile:
        return HttpResponseForbidden("Only the listing owner can accept bids.")
    if bid.status != "pending":
        return HttpResponseBadRequest("This bid is no longer pending.")
    bid.status = "accepted"
    bid.save()
    listing = bid.listing
    listing.is_active = False
    listing.save()
    Bid.objects.filter(listing=listing, status="pending").exclude(pk=bid.pk).update(status="rejected")
    contract = Contract.objects.create(
        bid=bid, student=listing.owner, client=bid.client,
        agreed_price=bid.proposed_price, status="active",
    )
    Payment.objects.create(contract=contract, amount=contract.agreed_price, status="held")
    _notify(bid.client, f"Your bid was accepted! Contract #{contract.pk} is now active.", f"/contracts/{contract.pk}/")
    messages.success(request, f"Bid accepted. Contract #{contract.pk} created.")
    return redirect("contract_detail", pk=contract.pk)


@login_required
@require_POST
def bid_reject(request, pk):
    bid = get_object_or_404(Bid, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if bid.listing.owner != profile:
        return HttpResponseForbidden("Only the listing owner can reject bids.")
    if bid.status != "pending":
        return HttpResponseBadRequest("This bid is no longer pending.")
    bid.status = "rejected"
    bid.save()
    _notify(bid.client, f"Your bid on '{bid.listing.title}' was rejected.", f"/listings/{bid.listing.pk}/")
    messages.success(request, "Bid rejected.")
    return redirect("listing_detail", pk=bid.listing.pk)


# ── Job requests (client posts, students bid) ─────────────────────────────────

def job_request_list(request):
    jobs = JobRequest.objects.filter(is_active=True).select_related("client", "category")
    categories = Category.objects.all()

    category_id = request.GET.get("category")
    if category_id:
        jobs = jobs.filter(category_id=category_id)

    budget_max = request.GET.get("budget_max")
    if budget_max:
        try:
            jobs = jobs.filter(budget__lte=float(budget_max))
        except ValueError:
            pass

    remote = request.GET.get("remote")
    if remote in ("true", "false"):
        jobs = jobs.filter(is_remote=(remote == "true"))

    sort = request.GET.get("sort", "newest")
    if sort == "budget_asc":
        jobs = jobs.order_by("budget")
    elif sort == "budget_desc":
        jobs = jobs.order_by("-budget")
    else:
        jobs = jobs.order_by("-created_at")

    return render(request, "core/job_request_list.html", {
        "jobs": jobs, "categories": categories, "sort": sort,
    })


@login_required
def job_request_create(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != "client":
        return HttpResponseForbidden("Only clients can post job requests.")
    if not profile.is_kyc_verified:
        messages.error(request, "KYC verification is required to post a job request. Use the 'Simulate KYC Verification' button on your dashboard.")
        return redirect("dashboard")
    if request.method == "POST":
        form = JobRequestForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.client = profile
            job.save()
            messages.success(request, "Job request posted.")
            return redirect("job_request_detail", pk=job.pk)
    else:
        form = JobRequestForm()
    return render(request, "core/job_request_create.html", {"form": form})


def job_request_detail(request, pk):
    job = get_object_or_404(JobRequest, pk=pk)
    my_bid = None
    can_bid = False
    is_owner = False
    bids = None
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile:
            if profile == job.client:
                is_owner = True
                bids = job.bids.select_related("student").all()
            elif profile.role == "student" and profile.is_kyc_verified:
                my_bid = job.bids.filter(student=profile).first()
                can_bid = job.is_active and my_bid is None
    form = JobBidForm() if can_bid else None
    return render(request, "core/job_request_detail.html", {
        "job": job, "my_bid": my_bid, "can_bid": can_bid,
        "is_owner": is_owner, "bids": bids, "form": form,
    })


@login_required
def job_bid_create(request, pk):
    job = get_object_or_404(JobRequest, pk=pk, is_active=True)
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != "student":
        return HttpResponseForbidden("Only students can bid on job requests.")
    if not profile.is_kyc_verified:
        messages.error(request, "KYC verification is required to bid on jobs. Use the 'Simulate KYC Verification' button on your dashboard.")
        return redirect("job_request_detail", pk=job.pk)
    if JobBid.objects.filter(job_request=job, student=profile).exists():
        messages.error(request, "You already have a bid on this job request.")
        return redirect("job_request_detail", pk=job.pk)
    if request.method == "POST":
        form = JobBidForm(request.POST)
        if form.is_valid():
            bid = form.save(commit=False)
            bid.job_request = job
            bid.student = profile
            bid.save()
            _notify(
                job.client,
                f"New bid of ${bid.proposed_price} from {profile.user.username} on '{job.title}'",
                f"/jobs/{job.pk}/",
            )
            messages.success(request, "Bid submitted.")
            return redirect("job_request_detail", pk=job.pk)
    else:
        form = JobBidForm()
    return render(request, "core/job_request_detail.html", {
        "job": job, "form": form, "placing_bid": True,
        "my_bid": None, "can_bid": False, "is_owner": False, "bids": None,
    })


@login_required
@require_POST
def job_bid_accept(request, pk):
    job_bid = get_object_or_404(JobBid, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if job_bid.job_request.client != profile:
        return HttpResponseForbidden("Only the job owner can accept bids.")
    if job_bid.status != "pending":
        return HttpResponseBadRequest("This bid is no longer pending.")
    job_bid.status = "accepted"
    job_bid.save()
    job = job_bid.job_request
    job.is_active = False
    job.save()
    JobBid.objects.filter(job_request=job, status="pending").exclude(pk=job_bid.pk).update(status="rejected")
    contract = Contract.objects.create(
        job_bid=job_bid, student=job_bid.student, client=profile,
        agreed_price=job_bid.proposed_price, status="active",
    )
    Payment.objects.create(contract=contract, amount=contract.agreed_price, status="held")
    _notify(job_bid.student, f"Your bid was accepted! Contract #{contract.pk} is active.", f"/contracts/{contract.pk}/")
    messages.success(request, f"Bid accepted. Contract #{contract.pk} created.")
    return redirect("contract_detail", pk=contract.pk)


@login_required
@require_POST
def job_bid_reject(request, pk):
    job_bid = get_object_or_404(JobBid, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if job_bid.job_request.client != profile:
        return HttpResponseForbidden("Only the job owner can reject bids.")
    if job_bid.status != "pending":
        return HttpResponseBadRequest("This bid is no longer pending.")
    job_bid.status = "rejected"
    job_bid.save()
    _notify(job_bid.student, f"Your bid on '{job_bid.job_request.title}' was rejected.", f"/jobs/{job_bid.job_request.pk}/")
    messages.success(request, "Bid rejected.")
    return redirect("job_request_detail", pk=job_bid.job_request.pk)


# ── Contracts ─────────────────────────────────────────────────────────────────

@login_required
def contract_detail(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if contract.student != profile and contract.client != profile:
        return HttpResponseForbidden("Access denied.")
    msg_form = ContractMessageForm()
    thread = contract.messages.select_related("sender").order_by("created_at")
    return render(request, "core/contract_detail.html", {
        "contract": contract, "profile": profile,
        "msg_form": msg_form, "thread": thread,
    })


@login_required
@require_POST
def contract_message_create(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if contract.student != profile and contract.client != profile:
        return HttpResponseForbidden("Access denied.")
    form = ContractMessageForm(request.POST)
    if form.is_valid():
        msg = form.save(commit=False)
        msg.contract = contract
        msg.sender = profile
        msg.save()
        other = contract.client if profile == contract.student else contract.student
        _notify(other, f"New message on Contract #{contract.pk}", f"/contracts/{contract.pk}/")
    return redirect("contract_detail", pk=contract.pk)


@login_required
@require_POST
def contract_complete(request, pk):
    """Student submits work — moves to 'delivered'."""
    contract = get_object_or_404(Contract, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if contract.student != profile:
        return HttpResponseForbidden("Only the student can submit work.")
    if contract.status != "active":
        return HttpResponseBadRequest("Contract is not active.")
    contract.status = "delivered"
    contract.save()
    _notify(contract.client, f"Work submitted on Contract #{contract.pk}. Please review.", f"/contracts/{contract.pk}/")
    messages.success(request, "Work submitted. The client will review and accept or raise a dispute.")
    return redirect("contract_detail", pk=contract.pk)


@login_required
@require_POST
def contract_accept(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if contract.client != profile:
        return HttpResponseForbidden("Only the client can accept delivery.")
    if contract.status != "delivered":
        return HttpResponseBadRequest("Work has not been submitted yet.")
    contract.status = "completed"
    contract.completed_at = timezone.now()
    contract.save()
    contract.payment.status = "released"
    contract.payment.save(update_fields=["status"])
    _notify(contract.student, f"Payment released for Contract #{contract.pk}. Work accepted!", f"/contracts/{contract.pk}/")
    messages.success(request, "Delivery accepted. Payment released.")
    return redirect("contract_detail", pk=contract.pk)


@login_required
@require_POST
def contract_reject(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if contract.client != profile:
        return HttpResponseForbidden("Only the client can reject delivery.")
    if contract.status != "delivered":
        return HttpResponseBadRequest("Work has not been submitted yet.")
    contract.status = "disputed"
    contract.save()
    _notify(contract.student, f"A dispute was raised on Contract #{contract.pk}. Admin will review.", f"/contracts/{contract.pk}/")
    messages.warning(request, "Dispute raised. An admin has been notified and will review the case.")
    return redirect("contract_detail", pk=contract.pk)


@login_required
def contracts(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    active_contracts = Contract.objects.filter(
        Q(student=profile) | Q(client=profile), status__in=["active", "delivered"],
    ).select_related("bid__listing", "job_bid__job_request", "student", "client")
    completed_contracts = Contract.objects.filter(
        Q(student=profile) | Q(client=profile), status__in=["completed", "disputed"],
    ).select_related("bid__listing", "job_bid__job_request", "student", "client")
    received_bids = None
    my_bids = None
    if profile.role == "student":
        received_bids = Bid.objects.filter(listing__owner=profile, status="pending").select_related("client", "listing")
    else:
        my_bids = Bid.objects.filter(client=profile).exclude(status="accepted").select_related("listing", "listing__owner")
    return render(request, "core/contracts.html", {
        "active_contracts": active_contracts,
        "completed_contracts": completed_contracts,
        "received_bids": received_bids,
        "my_bids": my_bids,
    })


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    student_contracts = None
    received_bids = None
    client_contracts = None
    my_bids = None
    my_job_requests = None

    if profile.role == "student":
        student_contracts = Contract.objects.filter(student=profile).select_related(
            "client", "bid__listing", "job_bid__job_request"
        )
        received_bids = Bid.objects.filter(listing__owner=profile, status="pending").select_related("client", "listing")
    else:
        client_contracts = Contract.objects.filter(client=profile).select_related(
            "student", "bid__listing", "job_bid__job_request"
        )
        my_bids = Bid.objects.filter(client=profile).exclude(status="accepted").select_related("listing", "listing__owner")
        my_job_requests = JobRequest.objects.filter(client=profile).order_by("-created_at")[:5]

    return render(request, "core/dashboard.html", {
        "student_contracts": student_contracts,
        "client_contracts": client_contracts,
        "received_bids": received_bids,
        "my_bids": my_bids,
        "my_job_requests": my_job_requests,
    })


# ── Notifications ─────────────────────────────────────────────────────────────

@login_required
def notifications_list(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    notifs = profile.notifications.order_by("-created_at")
    return render(request, "core/notifications.html", {"notifs": notifs})


@login_required
@require_POST
def notifications_mark_read(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    profile.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications_list")


# ── Auth ──────────────────────────────────────────────────────────────────────

def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()
            profile = user.userprofile
            profile.role = form.cleaned_data["role"]
            profile.is_kyc_verified = False
            profile.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = UserRegisterForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
@require_POST
def kyc_self_verify(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    profile.is_kyc_verified = True
    profile.save()
    messages.success(request, "KYC verified (test mode). You can now post listings and place bids.")
    return redirect("dashboard")


def profile_detail(request, user_pk):
    profile = get_object_or_404(UserProfile, user__pk=user_pk)
    listings = profile.listings.filter(is_active=True) if profile.role == "student" else None
    reviews = profile.reviews_received.select_related("reviewer")
    return render(request, "core/profile_detail.html", {
        "profile": profile, "listings": listings, "reviews": reviews,
    })


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
            messages.success(request, "Review submitted.")
            return redirect("contract_detail", pk=contract.pk)
    else:
        form = ReviewForm()
    return render(request, "core/review_form.html", {"form": form, "contract": contract})
