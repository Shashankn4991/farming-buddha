from django import forms
from django.contrib.auth import get_user_model

from .models import (
    DeliveryEntry,
    DeliveryEntryItem,
    WarehouseDailyEntry,
    FarmDailyEntry,
    BottleType,
    VanMovement,
)

from accounts.models import CustomUser

User = get_user_model()


# -------------------------------------------------
# DELIVERY ENTRY
# -------------------------------------------------

class DeliveryEntryItemForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.warehouse_stock = kwargs.pop('warehouse_stock', {})
        super().__init__(*args, **kwargs)

    class Meta:
        model = DeliveryEntryItem
        fields = [
            "bottle_type",
            "delivered",
            "collected",
            "breakage",
        ]

    def clean(self):
        cleaned_data = super().clean()

        bottle_type = cleaned_data.get("bottle_type")
        delivered = cleaned_data.get("delivered", 0)

        if bottle_type:
            available = self.warehouse_stock.get(bottle_type.id, 0)

            if delivered > available:
                raise forms.ValidationError(
                    f"Only {available} bottles available in warehouse"
                )

        return cleaned_data

# -------------------------------------------------
# FARM ENTRY
# -------------------------------------------------

class FarmDailyEntryForm(forms.ModelForm):
    class Meta:
        model = FarmDailyEntry
        fields = ['date']

        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'})
        }


class FarmDailyEntryItemForm(forms.Form):
    bottle_type = forms.ModelChoiceField(queryset=BottleType.objects.all())
    sent_to_warehouse = forms.IntegerField(min_value=0)
    empty_received_from_warehouse = forms.IntegerField(min_value=0)


# -------------------------------------------------
# WAREHOUSE ENTRY
# -------------------------------------------------

class WarehouseDailyEntryForm(forms.ModelForm):
    class Meta:
        model = WarehouseDailyEntry
        fields = ['date']

        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'})
        }


# -------------------------------------------------
# VAN MOVEMENT MODEL FORM
# -------------------------------------------------

class VanMovementForm(forms.ModelForm):
    class Meta:
        model = VanMovement
        fields = ['date', 'driver']

        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['driver'].queryset = User.objects.filter(role='DRIVER')


# -------------------------------------------------
# VAN ENTRY CUSTOM FORM
# -------------------------------------------------

class VanEntryForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    driver = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role='DRIVER')
    )

    # 1 Liter
    one_liter_empty_sent = forms.IntegerField(required=False, initial=0)
    one_liter_filled_received = forms.IntegerField(required=False, initial=0)
    one_liter_breakage = forms.IntegerField(required=False, initial=0)

    one_liter_reason = forms.ChoiceField(
        choices=[
            ("", "---------"),
            ("TRANSPORT", "Transport Damage"),
            ("HANDLING", "Handling Mistake"),
            ("OTHER", "Other"),
        ],
        required=False
    )

    # 0.5 Liter
    half_liter_empty_sent = forms.IntegerField(required=False, initial=0)
    half_liter_filled_received = forms.IntegerField(required=False, initial=0)
    half_liter_breakage = forms.IntegerField(required=False, initial=0)

    half_liter_reason = forms.ChoiceField(
        choices=[
            ("", "---------"),
            ("TRANSPORT", "Transport Damage"),
            ("HANDLING", "Handling Mistake"),
            ("OTHER", "Other"),
        ],
        required=False
    )


# -------------------------------------------------
# WASHING CYCLE
# -------------------------------------------------

class WashingCycleForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )