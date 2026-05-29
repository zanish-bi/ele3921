from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class UserProfile(models.Model):
    ROLE_CHOICES = [("student", "Student"), ("client", "Client")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="userprofile")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    bio = models.TextField(blank=True)
    is_kyc_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class ServiceListing(models.Model):
    owner = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="listings")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="listings")
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_remote = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Bid(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    listing = models.ForeignKey(ServiceListing, on_delete=models.CASCADE, related_name="bids")
    client = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="bids_placed")
    proposed_price = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bid by {self.client} on {self.listing}"


class JobRequest(models.Model):
    """Client posts a job — students bid to take it."""
    client = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="job_requests")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="job_requests")
    title = models.CharField(max_length=200)
    description = models.TextField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    is_remote = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class JobBid(models.Model):
    """Student bids on a client's JobRequest."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    job_request = models.ForeignKey(JobRequest, on_delete=models.CASCADE, related_name="bids")
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="job_bids")
    proposed_price = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("job_request", "student")]

    def __str__(self):
        return f"Job bid by {self.student} on {self.job_request}"


class Contract(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("disputed", "Disputed"),
    ]

    # Exactly one of bid / job_bid will be set.
    bid = models.OneToOneField(
        Bid, on_delete=models.PROTECT, related_name="contract", null=True, blank=True
    )
    job_bid = models.OneToOneField(
        JobBid, on_delete=models.PROTECT, related_name="contract", null=True, blank=True
    )
    student = models.ForeignKey(UserProfile, on_delete=models.PROTECT, related_name="contracts_as_student")
    client = models.ForeignKey(UserProfile, on_delete=models.PROTECT, related_name="contracts_as_client")
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True, default="")

    @property
    def listing_title(self):
        if self.bid_id:
            return self.bid.listing.title
        if self.job_bid_id:
            return self.job_bid.job_request.title
        return "—"

    @property
    def bid_message(self):
        if self.bid_id:
            return self.bid.message
        if self.job_bid_id:
            return self.job_bid.message
        return ""

    def __str__(self):
        return f"Contract #{self.pk} ({self.status})"


class Payment(models.Model):
    STATUS_CHOICES = [
        ("held", "Held"),
        ("released", "Released"),
        ("refunded", "Refunded"),
    ]

    contract = models.OneToOneField(Contract, on_delete=models.PROTECT, related_name="payment")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="held")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Keep contract status in sync whenever payment status changes.
        contract = self.contract
        if self.status == "released" and contract.status != "completed":
            from django.utils import timezone as tz
            contract.status = "completed"
            if not contract.completed_at:
                contract.completed_at = tz.now()
            contract.save(update_fields=["status", "completed_at"])
        elif self.status == "refunded" and contract.status not in ("completed",):
            contract.status = "disputed"
            contract.save(update_fields=["status"])

    def __str__(self):
        return f"Payment for Contract #{self.contract_id} ({self.status})"


class Review(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="reviews_given")
    reviewee = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="reviews_received")
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("contract", "reviewer")]

    def __str__(self):
        return f"Review by {self.reviewer} for {self.reviewee} ({self.rating}/5)"


class ContractMessage(models.Model):
    """Simple message thread on a contract — visible to both parties."""
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message by {self.sender} on Contract #{self.contract_id}"


class Notification(models.Model):
    recipient = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=300)
    url = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.recipient}: {self.message[:50]}"
