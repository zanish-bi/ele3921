from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import UserProfile, Category, ServiceListing, Bid, Contract, Payment, Review, JobRequest


TEST_USERS = [
    {
        "username": "student1", "password": "pass1234",
        "role": "student", "kyc": True,
        "bio": "Computer Science student specialising in web development, Python, and graphic design. 3 years freelancing experience.",
    },
    {
        "username": "student2", "password": "pass1234",
        "role": "student", "kyc": False,
        "bio": "Linguistics major offering essay editing and translation services. Native English speaker.",
    },
    {
        "username": "client1", "password": "pass1234",
        "role": "client", "kyc": True,
        "bio": "Startup founder looking for talented student freelancers for short-term projects.",
    },
]

TEST_LISTINGS = [
    {
        "owner": "student1",
        "category": "Programming",
        "title": "Python & Django Web Development",
        "description": (
            "I will build you a clean, tested Django web application with modern templates, "
            "user authentication, and database integration. Includes deployment instructions. "
            "Portfolio available on request."
        ),
        "price": "120.00",
        "is_remote": True,
    },
    {
        "owner": "student1",
        "category": "Design",
        "title": "Logo & Brand Identity Design",
        "description": (
            "Professional logo design with unlimited revisions until you are happy. "
            "Deliverables: SVG, PNG (multiple sizes), and PDF. Turnaround 3–5 business days."
        ),
        "price": "75.00",
        "is_remote": True,
    },
    {
        "owner": "student2",
        "category": "Writing",
        "title": "Academic Essay Editing",
        "description": (
            "Native-level English editing for essays, reports, and dissertations. "
            "I improve grammar, structure, and flow while keeping your voice. "
            "Max 5,000 words per order."
        ),
        "price": "30.00",
        "is_remote": True,
    },
]


class Command(BaseCommand):
    help = "Seed the database with demo users, listings, contracts, and reviews for testing."

    def handle(self, *args, **options):
        self._seed_users()
        self._seed_listings()
        self._seed_active_contract()
        self._seed_completed_contract()
        self._seed_job_request()
        self._print_summary()

    def _seed_users(self):
        self.stdout.write("Seeding users...")
        for u in TEST_USERS:
            user, created = User.objects.get_or_create(username=u["username"])
            if created:
                user.set_password(u["password"])
                user.save()
            profile = user.userprofile
            profile.role = u["role"]
            profile.is_kyc_verified = u["kyc"]
            profile.bio = u.get("bio", "")
            profile.save()
            tag = "created" if created else "already exists"
            kyc = "KYC verified" if u["kyc"] else "KYC pending"
            self.stdout.write(f"  {u['username']} ({u['role']}, {kyc}) — {tag}")

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@studentgig.local", "admin")
            self.stdout.write("  admin (superuser, pw: admin) — created")
        else:
            self.stdout.write("  admin — already exists")

    def _seed_listings(self):
        self.stdout.write("Seeding listings...")
        for data in TEST_LISTINGS:
            owner = User.objects.get(username=data["owner"]).userprofile
            cat = Category.objects.filter(name=data["category"]).first()
            if not cat:
                self.stdout.write(self.style.WARNING(
                    f"  Category '{data['category']}' not found — run migrate first"
                ))
                continue
            listing, created = ServiceListing.objects.get_or_create(
                owner=owner,
                title=data["title"],
                defaults={
                    "category": cat,
                    "description": data["description"],
                    "price": data["price"],
                    "is_remote": data["is_remote"],
                    "is_active": True,
                },
            )
            tag = "created" if created else "already exists"
            self.stdout.write(f"  '{listing.title}' — {tag}")

    def _seed_active_contract(self):
        """Bid placed and accepted; contract is active, payment held."""
        self.stdout.write("Seeding active contract...")
        try:
            student = User.objects.get(username="student1").userprofile
            client = User.objects.get(username="client1").userprofile
            listing = ServiceListing.objects.get(
                owner=student, title="Python & Django Web Development"
            )
        except (User.DoesNotExist, ServiceListing.DoesNotExist):
            self.stdout.write(self.style.WARNING("  Required objects missing, skipping"))
            return

        if Bid.objects.filter(listing=listing, status="accepted").exists():
            self.stdout.write("  active contract already exists, skipping")
            return

        bid = Bid.objects.create(
            listing=listing,
            client=client,
            proposed_price="110.00",
            message=(
                "Hi! I need a task management app — login, add/complete/delete tasks, "
                "simple dashboard. Django preferred. Happy to discuss requirements."
            ),
            status="accepted",
        )
        listing.is_active = False
        listing.save()
        contract = Contract.objects.create(
            bid=bid,
            student=student,
            client=client,
            agreed_price=bid.proposed_price,
            status="active",
        )
        Payment.objects.create(contract=contract, amount=contract.agreed_price, status="held")
        self.stdout.write(f"  contract #{contract.pk} (active, payment held) — created")

    def _seed_completed_contract(self):
        """Completed contract with released payment and a client review."""
        self.stdout.write("Seeding completed contract...")
        try:
            student = User.objects.get(username="student1").userprofile
            client = User.objects.get(username="client1").userprofile
            listing = ServiceListing.objects.get(
                owner=student, title="Logo & Brand Identity Design"
            )
        except (User.DoesNotExist, ServiceListing.DoesNotExist):
            self.stdout.write(self.style.WARNING("  Required objects missing, skipping"))
            return

        if Contract.objects.filter(bid__listing=listing).exists():
            self.stdout.write("  completed contract already exists, skipping")
            return

        bid = Bid.objects.create(
            listing=listing,
            client=client,
            proposed_price="70.00",
            message="Need a logo for my startup. Clean, modern look. Prefer SVG + PNG deliverables.",
            status="accepted",
        )
        listing.is_active = False
        listing.save()
        contract = Contract.objects.create(
            bid=bid,
            student=student,
            client=client,
            agreed_price=bid.proposed_price,
            status="completed",
            completed_at=timezone.now(),
        )
        Payment.objects.create(contract=contract, amount=contract.agreed_price, status="released")

        if not Review.objects.filter(contract=contract, reviewer=client).exists():
            Review.objects.create(
                contract=contract,
                reviewer=client,
                reviewee=student,
                rating=5,
                comment="Delivered ahead of schedule. Clean SVG files, very professional communication.",
            )
        self.stdout.write(
            f"  contract #{contract.pk} (completed, payment released, review by client) — created"
        )

    def _seed_job_request(self):
        """One open job request from client1 so the Jobs page is not empty on first load."""
        self.stdout.write("Seeding job request...")
        try:
            client = User.objects.get(username="client1").userprofile
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING("  client1 not found, skipping"))
            return

        cat = Category.objects.filter(name="Programming").first()
        if not cat:
            self.stdout.write(self.style.WARNING("  'Programming' category not found, skipping"))
            return

        job, created = JobRequest.objects.get_or_create(
            client=client,
            title="Need a Python Script for Data Processing",
            defaults={
                "category": cat,
                "description": (
                    "I have a CSV file with ~10,000 rows of sales data. "
                    "I need a Python script that cleans the data, removes duplicates, "
                    "and generates a summary report (totals by month, top products). "
                    "Output should be a new CSV plus a simple text summary. "
                    "Deadline: one week. Please bid if you have pandas/numpy experience."
                ),
                "budget": "60.00",
                "is_active": True,
            },
        )
        tag = "created" if created else "already exists"
        self.stdout.write(f"  '{job.title}' — {tag}")

    def _print_summary(self):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed complete. Test accounts:"))
        self.stdout.write("")
        self.stdout.write("  Username   Password   Role      KYC")
        self.stdout.write("  ─────────────────────────────────────────")
        self.stdout.write("  student1   pass1234   Student   Verified   (has listings + contracts)")
        self.stdout.write("  student2   pass1234   Student   Pending    (use Test Mode button)")
        self.stdout.write("  client1    pass1234   Client    Verified   (has bids + contracts)")
        self.stdout.write("  admin      admin      Superuser (Django admin at /admin/)")
        self.stdout.write("")
        self.stdout.write("  Available listing for bidding:")
        self.stdout.write("  'Academic Essay Editing' by student2 — log in as client1 to bid")
        self.stdout.write("")
        self.stdout.write("  Available job request for bidding:")
        self.stdout.write("  'Need a Python Script for Data Processing' by client1 — log in as student1 to bid")
