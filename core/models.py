from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class UserProfile(models.Model):
    ROLE_CHOICES = [("student", "Student"), ("client", "Client")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
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


class Contract(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("disputed", "Disputed"),
    ]

    bid = models.OneToOneField(Bid, on_delete=models.PROTECT, related_name="contract")
    student = models.ForeignKey(UserProfile, on_delete=models.PROTECT, related_name="contracts_as_student")
    client = models.ForeignKey(UserProfile, on_delete=models.PROTECT, related_name="contracts_as_client")
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

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

    def __str__(self):
        return f"Payment for Contract #{self.contract_id} ({self.status})"


class Review(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="reviews_given")
    reviewee = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="reviews_received")
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.reviewer} for {self.reviewee} ({self.rating}/5)"
