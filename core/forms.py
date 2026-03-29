from django import forms
from .models import Bid, ServiceListing


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ["proposed_price", "message"]


class ServiceListingForm(forms.ModelForm):
    class Meta:
        model = ServiceListing
        fields = ["category", "title", "description", "price", "is_remote"]
