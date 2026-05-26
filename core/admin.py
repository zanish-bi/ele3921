from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    UserProfile, Category, ServiceListing, Bid, Contract, Payment, Review,
    JobRequest, JobBid, ContractMessage, Notification,
)


class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    readonly_fields = ["created_at"]


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0
    readonly_fields = ["created_at"]
    fields = ["amount", "status", "created_at"]


class ContractMessageInline(admin.TabularInline):
    model = ContractMessage
    extra = 0
    readonly_fields = ["sender", "created_at"]
    fields = ["sender", "body", "created_at"]


class JobBidInline(admin.TabularInline):
    model = JobBid
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


@admin.register(JobRequest)
class JobRequestAdmin(admin.ModelAdmin):
    list_display = ["title", "client", "category", "budget", "is_active", "created_at"]
    list_filter = ["category", "is_active"]
    search_fields = ["title", "client__user__username"]
    inlines = [JobBidInline]


@admin.register(JobBid)
class JobBidAdmin(admin.ModelAdmin):
    list_display = ["job_request", "student", "proposed_price", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["created_at"]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        "pk", "student_username", "client_username",
        "agreed_price", "payment_status_display", "status_display", "created_at",
    ]
    list_filter = ["status"]
    readonly_fields = ["created_at", "completed_at", "student_username", "client_username"]
    inlines = [PaymentInline, ContractMessageInline]
    fieldsets = [
        ("Parties", {"fields": ["student_username", "client_username", "bid", "job_bid"]}),
        ("Contract", {"fields": ["student", "client", "agreed_price", "status", "created_at", "completed_at"]}),
        ("Admin Message to Parties", {
            "fields": ["admin_note"],
            "description": "This message is displayed to both parties on the contract page.",
        }),
    ]
    actions = ["release_payment", "refund_payment"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # If admin directly sets contract status, keep payment in sync.
        if change and "status" in form.changed_data:
            try:
                payment = obj.payment
                if obj.status == "completed" and payment.status != "released":
                    payment.status = "released"
                    payment.save(update_fields=["status"])
                elif obj.status == "disputed" and payment.status == "released":
                    payment.status = "refunded"
                    payment.save(update_fields=["status"])
            except Payment.DoesNotExist:
                pass

    @admin.display(description="Student")
    def student_username(self, obj):
        u = obj.student.user
        email = u.email or "—"
        return format_html(
            "<strong>{}</strong> <span style='color:#6b7280;font-size:.85em;'>({})</span>",
            u.username, email,
        )

    @admin.display(description="Client")
    def client_username(self, obj):
        u = obj.client.user
        email = u.email or "—"
        return format_html(
            "<strong>{}</strong> <span style='color:#6b7280;font-size:.85em;'>({})</span>",
            u.username, email,
        )

    @admin.display(description="Payment")
    def payment_status_display(self, obj):
        try:
            s = obj.payment.status
        except Payment.DoesNotExist:
            return "—"
        colours = {"held": "#854d0e", "released": "#166534", "refunded": "#991b1b"}
        return format_html(
            "<span style='color:{};font-weight:600;'>{}</span>",
            colours.get(s, "#374151"), s.title(),
        )

    @admin.display(description="Status")
    def status_display(self, obj):
        colours = {
            "active": "#1e3a5f", "delivered": "#b45309",
            "completed": "#166534", "disputed": "#991b1b",
        }
        icons = {"active": "●", "delivered": "▲", "completed": "✔", "disputed": "⚠"}
        return format_html(
            "<span style='color:{};font-weight:700;'>{} {}</span>",
            colours.get(obj.status, "#374151"),
            icons.get(obj.status, ""),
            obj.get_status_display(),
        )

    @admin.action(description="✔ Release payment → mark Completed")
    def release_payment(self, request, queryset):
        updated = 0
        for contract in queryset.filter(status__in=["delivered", "disputed"]):
            contract.status = "completed"
            contract.completed_at = timezone.now()
            contract.save()
            try:
                contract.payment.status = "released"
                contract.payment.save()
            except Payment.DoesNotExist:
                pass
            updated += 1
        self.message_user(request, f"{updated} contract(s) completed and payment released.")

    @admin.action(description="↩ Refund payment → mark Disputed/Resolved")
    def refund_payment(self, request, queryset):
        updated = 0
        for contract in queryset.filter(status__in=["delivered", "disputed"]):
            contract.status = "disputed"
            contract.save()
            try:
                contract.payment.status = "refunded"
                contract.payment.save()
            except Payment.DoesNotExist:
                pass
            updated += 1
        self.message_user(request, f"{updated} contract(s) payment refunded.")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["contract", "amount", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["created_at"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["reviewer", "reviewee", "rating", "contract"]
    list_filter = ["rating"]


@admin.register(ContractMessage)
class ContractMessageAdmin(admin.ModelAdmin):
    list_display = ["contract", "sender", "body", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "message", "is_read", "created_at"]
    list_filter = ["is_read"]
    readonly_fields = ["created_at"]
