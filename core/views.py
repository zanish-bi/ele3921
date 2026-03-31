from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.auth import login
from django.utils import timezone
from .models import UserProfile, Category, ServiceListing, Bid, Contract, Payment
from .forms import BidForm, ServiceListingForm, UserRegisterForm


def home(request):
    return render(request, "core/index.html")


def listing_list(request):
    listings = ServiceListing.objects.filter(is_active=True).select_related("owner", "category")
    category_id = request.GET.get("category")
    if category_id:
        listings = listings.filter(category_id=category_id)
    categories = Category.objects.all()
    return render(request, "core/listing_list.html", {"listings": listings, "categories": categories})


def listing_detail(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk)
    bids = None
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile and profile == listing.owner:
            bids = listing.bids.select_related("client").all()
    return render(request, "core/listing_detail.html", {"listing": listing, "bids": bids})


@login_required
def listing_create(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != "student":
        return HttpResponseForbidden("Only students can create listings.")
    if not profile.is_kyc_verified:
        return HttpResponseForbidden("KYC verification required to create listings.")
    if request.method == "POST":
        form = ServiceListingForm(request.POST)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.owner = profile
            listing.save()
            return redirect("listing_detail", pk=listing.pk)
    else:
        form = ServiceListingForm()
    return render(request, "core/listing_create.html", {"form": form})


@login_required
def place_bid(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk, is_active=True)
    profile = get_object_or_404(UserProfile, user=request.user)

    if profile.role != "client":
        return HttpResponseForbidden("Only clients can place bids.")

    if not profile.is_kyc_verified:
        return HttpResponseForbidden("KYC verification required.")

    if request.method == "POST":
        form = BidForm(request.POST)
        print("POST received")
        print(request.POST)

        if form.is_valid():
            bid = form.save(commit=False)
            bid.listing = listing
            bid.client = profile
            bid.save()
            return redirect("listing_detail", pk=listing.pk)
        else:
            print("FORM NOT VALID")
            print(form.errors)
    else:
        form = BidForm()

    return render(request, "core/place_bid.html", {
        "form": form,
        "listing": listing
    })


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
        bid=bid,
        student=listing.owner,
        client=bid.client,
        agreed_price=bid.proposed_price,
        status="active",
    )
    Payment.objects.create(
        contract=contract,
        amount=contract.agreed_price,
        status="held",
    )

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
    return redirect("listing_detail", pk=bid.listing.pk)


@login_required
def contract_detail(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if contract.student != profile and contract.client != profile:
        return HttpResponseForbidden("Access denied.")
    return render(request, "core/contract_detail.html", {"contract": contract})


@login_required
@require_POST
def contract_complete(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    if contract.student != profile:
        return HttpResponseForbidden("Only the student can mark the contract as complete.")
    if contract.status != "active":
        return HttpResponseBadRequest("Contract is not active.")

    contract.status = "completed"
    contract.completed_at = timezone.now()
    contract.save()

    contract.payment.status = "released"
    contract.payment.save()

    return redirect("contract_detail", pk=contract.pk)


@login_required
def dashboard(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    student_contracts = Contract.objects.filter(student=profile).select_related("client", "bid__listing")
    client_contracts = Contract.objects.filter(client=profile).select_related("student", "bid__listing")
    return render(request, "core/dashboard.html", {
        "student_contracts": student_contracts,
        "client_contracts": client_contracts,
    })


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
