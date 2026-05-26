from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("listings/", views.listing_list, name="listing_list"),
    path("listings/create/", views.listing_create, name="listing_create"),
    path("listings/<int:pk>/", views.listing_detail, name="listing_detail"),
    path("listings/<int:pk>/bid/", views.place_bid, name="place_bid"),
    path("bids/<int:pk>/accept/", views.bid_accept, name="bid_accept"),
    path("bids/<int:pk>/reject/", views.bid_reject, name="bid_reject"),
    path("contracts/<int:pk>/", views.contract_detail, name="contract_detail"),
    path("contracts/<int:pk>/complete/", views.contract_complete, name="contract_complete"),
    path("accounts/register/", views.register, name="register"),
    path("contracts/", views.contracts, name="contracts"),
    path("profiles/<int:user_pk>/", views.profile_detail, name="profile_detail"),
    path("contracts/<int:contract_pk>/review/", views.review_create, name="review_create"),
]
