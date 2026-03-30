from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("listings/", views.listing_list, name="listing_list"),
    path("listings/create/", views.listing_create, name="listing_create"),
    path("listings/<int:pk>/", views.listing_detail, name="listing_detail"),
    path("listings/<int:listing_pk>/bid/", views.bid_create, name="bid_create"),
    path("bids/<int:pk>/accept/", views.bid_accept, name="bid_accept"),
    path("bids/<int:pk>/reject/", views.bid_reject, name="bid_reject"),
    path("contracts/<int:pk>/", views.contract_detail, name="contract_detail"),
    path("contracts/<int:pk>/complete/", views.contract_complete, name="contract_complete"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("accounts/register/", views.register, name="register"),
    path("verify-kyc/", views.verify_kyc, name="verify_kyc"),
]
