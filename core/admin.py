from django.contrib import admin
from .models import UserProfile, Category, ServiceListing, Bid, Contract, Payment, Review


class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    readonly_fields = ["created_at"]


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "is_kyc_verified"]
    list_filter = ["role", "is_kyc_verified"]
    actions = ["toggle_kyc"]

    @admin.action(description="Toggle KYC verified status")
    def toggle_kyc(self, request, queryset):
        for profile in queryset:
            profile.is_kyc_verified = not profile.is_kyc_verified
            profile.save()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(ServiceListing)
class ServiceListingAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "category", "price", "is_active", "is_remote"]
    list_filter = ["category", "is_active", "is_remote"]
    search_fields = ["title", "owner__user__username"]
    inlines = [BidInline]


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ["listing", "client", "proposed_price", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["created_at"]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ["pk", "student", "client", "agreed_price", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["created_at", "completed_at"]
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["contract", "amount", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["created_at"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["reviewer", "reviewee", "rating", "contract"]
    list_filter = ["rating"]
