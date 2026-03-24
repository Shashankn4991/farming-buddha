from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum


# ------------------------------
# Bottle Type
# ------------------------------

class BottleType(models.Model):
    name = models.CharField(max_length=20)

    def __str__(self):
        return self.name


# ------------------------------
# Bottle Purchase
# ------------------------------

class BottlePurchase(models.Model):
    date = models.DateField()

    bottle_type = models.ForeignKey(
        BottleType,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField()
    notes = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.date} - {self.bottle_type.name}"


# ------------------------------
# Farm Daily Entry
# ------------------------------

class FarmDailyEntry(models.Model):
    date = models.DateField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.date)

# ------------------------------
# Farm Daily Entry Item
# ------------------------------

class FarmDailyEntryItem(models.Model):
    farm_entry = models.ForeignKey(
        FarmDailyEntry,
        on_delete=models.CASCADE
    )

    bottle_type = models.ForeignKey(
        BottleType,
        on_delete=models.CASCADE
    )

    # Core flow
    sent_to_warehouse = models.PositiveIntegerField(default=0)
    empty_received_from_warehouse = models.PositiveIntegerField(default=0)

    # 🔥 NEW: Empty bottle breakage
    empty_breakage = models.PositiveIntegerField(default=0)

    # 🔥 NEW: Reason tracking
    breakage_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('farm_entry', 'bottle_type')

    def __str__(self):
        return f"{self.farm_entry.date} - {self.bottle_type.name}"




# ------------------------------
# Warehouse Daily Entry
# ------------------------------

class WarehouseDailyEntry(models.Model):

    ENTRY_TYPE_CHOICES = [
        ('INWARD', 'Inward'),
        ('OUTWARD', 'Outward'),
    ]

    date = models.DateField()
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('date', 'entry_type')   # 🔥 KEY FIX

    def __str__(self):
        return f"{self.date} - {self.entry_type}"


# ------------------------------
# Warehouse Daily Entry Item
# ------------------------------

from django.core.exceptions import ValidationError



class WarehouseDailyEntryItem(models.Model):

    warehouse_entry = models.ForeignKey(
        WarehouseDailyEntry,
        on_delete=models.CASCADE
    )

    bottle_type = models.ForeignKey(
        BottleType,
        on_delete=models.CASCADE
    )

    # INWARD fields
    received_from_farm = models.PositiveIntegerField(default=0)

    # OUTWARD fields
    empty_received_from_delivery = models.PositiveIntegerField(default=0)
    empty_sent_to_farm = models.PositiveIntegerField(default=0)

    # COMMON
    warehouse_breakage = models.PositiveIntegerField(default=0)
    breakage_reason = models.CharField(max_length=50, blank=True)
    breakage_approved = models.BooleanField(default=False)
    filled_sent_to_delivery = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('warehouse_entry', 'bottle_type')

    def __str__(self):
        return f"{self.warehouse_entry.date} - {self.bottle_type.name} ({self.warehouse_entry.entry_type})"

    # ✅ VALIDATION
    def clean(self):
        from .services import get_current_stock
        stock = get_current_stock(self.bottle_type)

        if self.empty_sent_to_farm > stock["warehouse"]:
            raise ValidationError(
                f"Only {stock['warehouse']} bottles available in warehouse"
            )

        if self.warehouse_breakage > 0 and not self.breakage_reason:
            raise ValidationError("Breakage reason is required")

    # ✅ FORCE VALIDATION
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ------------------------------
# Delivery Assignment
# ------------------------------

class DeliveryAssignment(models.Model):
    date = models.DateField()

    delivery_user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='delivery_assignments'
    )

    created_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='created_assignments'
    )

    def __str__(self):
        return f"{self.date} - {self.delivery_user.username}"

    class Meta:
        unique_together = ['delivery_user', 'date']  # ✅ prevent duplicates
        ordering = ['-date']  # ✅ consistent sorting
        indexes = [
            models.Index(fields=['date']),  # ✅ performance
        ]


# ------------------------------
# Delivery Assignment Item
# ------------------------------

class DeliveryAssignmentItem(models.Model):
    assignment = models.ForeignKey(
        DeliveryAssignment,
        on_delete=models.CASCADE,
        related_name="items"
    )

    bottle_type = models.ForeignKey(
        BottleType,
        on_delete=models.CASCADE
    )

    quantity_assigned = models.PositiveIntegerField()

    def clean(self):
        # ✅ Basic safety validation (keep model stable)
        if self.quantity_assigned < 0:
            raise ValidationError("Quantity cannot be negative")

    def save(self, *args, **kwargs):
        self.full_clean()  # ✅ enforce validation always
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("assignment", "bottle_type")
        ordering = ['bottle_type']
        indexes = [
            models.Index(fields=['assignment']),
        ]

    def __str__(self):
        return f"{self.assignment} - {self.bottle_type}"


# ------------------------------
# Delivery Entry
# ------------------------------

class DeliveryEntry(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    assignment = models.OneToOneField(
        DeliveryAssignment,
        on_delete=models.CASCADE
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_deliveries"
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def clean(self):
        if not self.assignment:
            raise ValidationError("Assignment is required.")

        # ✅ CRITICAL FIX
        if self.submitted_by != self.assignment.delivery_user:
            raise ValidationError("Submitted user must match assignment user.")

        if self.approved_by and self.approved_by == self.submitted_by:
            raise ValidationError("User cannot approve their own delivery.")

        if self.status == "APPROVED":
            if not self.approved_by:
                raise ValidationError("Approved entry must have approved_by.")

            if self.approved_by.role.upper() not in ["SUPERVISOR", "ADMIN"]:
                raise ValidationError("Only SUPERVISOR or ADMIN can approve.")

    def save(self, *args, **kwargs):

        # ✅ Move mutation logic here
        if self.status in ["PENDING", "REJECTED"]:
            self.approved_by = None
            self.approved_at = None

        if self.status == "APPROVED" and not self.approved_at:
            self.approved_at = timezone.now()

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.assignment} - {self.submitted_by.username}"

    class Meta:
        ordering = ['-assignment__date']
        indexes = [
            models.Index(fields=['status']),
        ]



# ------------------------------
# Delivery Entry Item
# ------------------------------

class DeliveryEntryItem(models.Model):

    entry = models.ForeignKey(
        "DeliveryEntry",
        on_delete=models.CASCADE,
        related_name="items"
    )

    bottle_type = models.ForeignKey(
        "BottleType",
        on_delete=models.CASCADE
    )

    delivered = models.PositiveIntegerField(default=0)
    collected = models.PositiveIntegerField(default=0)
    breakage = models.PositiveIntegerField(default=0)

    # 🔥 VALIDATION
    def clean(self):

        # ✅ Safety check
        if not self.entry or not self.bottle_type:
            raise ValidationError("Entry and bottle type are required.")

        # ------------------------------
        # Rule 1: Delivered ≤ Assigned
        # ------------------------------
        try:
            assignment_item = self.entry.assignment.items.get(
                bottle_type=self.bottle_type
            )
        except DeliveryAssignmentItem.DoesNotExist:
            raise ValidationError(
                f"No assignment found for {self.bottle_type.name}"
            )

        if self.delivered > assignment_item.quantity_assigned:
            raise ValidationError(
                f"{self.bottle_type.name}: Delivered ({self.delivered}) "
                f"cannot exceed assigned ({assignment_item.quantity_assigned})."
            )

        # ------------------------------
        # Rule 2: Collected ≤ Customer Outstanding
        # ------------------------------
        from bottles.services import get_customer_outstanding

        outstanding = get_customer_outstanding(self.bottle_type)

        # Allow first-time entries (outstanding = 0)
        if outstanding > 0 and self.collected > outstanding:
            raise ValidationError(
                f"{self.bottle_type.name}: Cannot collect {self.collected}. "
                f"Only {outstanding} bottles are currently with customers."
            )

        # ------------------------------
        # Rule 3: No negative values
        # ------------------------------
        if self.delivered < 0 or self.collected < 0 or self.breakage < 0:
            raise ValidationError("Values cannot be negative")

    # 🔥 FORCE VALIDATION
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("entry", "bottle_type")
        ordering = ["bottle_type"]
        indexes = [
            models.Index(fields=["entry"]),
        ]

    def __str__(self):
        return f"{self.entry} - {self.bottle_type}"
    
    
    
# ------------------------------
# Washing Cycle
# ------------------------------

class WashingCycle(models.Model):
    date = models.DateField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.date)

    class Meta:
        ordering = ['-date']
    



from django.core.exceptions import ValidationError

# ------------------------------
# Washing Cycle Item
# ------------------------------

class WashingCycleItem(models.Model):

    washing = models.ForeignKey(
        "WashingCycle",
        on_delete=models.CASCADE,
        related_name="items"
    )

    bottle_type = models.ForeignKey(
        BottleType,
        on_delete=models.CASCADE
    )

    empty_sent_to_wash = models.PositiveIntegerField(default=0)
    ready_after_wash = models.PositiveIntegerField(default=0)
    washing_breakage = models.PositiveIntegerField(default=0)

    def clean(self):

        # ✅ Safety check
        if not self.washing or not self.bottle_type:
            raise ValidationError("Washing and bottle type are required.")

        # ------------------------------
        # Rule 0: No negative values
        # ------------------------------
        if self.ready_after_wash < 0 or self.washing_breakage < 0:
            raise ValidationError("Values cannot be negative")

        # ------------------------------
        # Rule 1: Ready ≤ Input
        # ------------------------------
        if self.ready_after_wash > self.empty_sent_to_wash:
            raise ValidationError(
                f"{self.bottle_type.name}: Ready cannot exceed sent quantity."
            )

        # ------------------------------
        # Rule 2: Total must match
        # ------------------------------
        if (self.ready_after_wash + self.washing_breakage) != self.empty_sent_to_wash:
            raise ValidationError(
                f"{self.bottle_type.name}: Ready + Breakage must equal {self.empty_sent_to_wash}."
            )

        # ------------------------------
        # Rule 3: Farm entry must exist
        # ------------------------------
        from .models import FarmDailyEntryItem

        exists = FarmDailyEntryItem.objects.filter(
            farm_entry__date=self.washing.date,
            bottle_type=self.bottle_type
        ).exists()

        if not exists:
            raise ValidationError(
                f"No farm data for {self.bottle_type.name} on {self.washing.date}"
            )

        farm_item = FarmDailyEntryItem.objects.get(
            farm_entry__date=self.washing.date,
            bottle_type=self.bottle_type
        )

        farm_available = farm_item.empty_received_from_warehouse or 0

        # ------------------------------
        # Rule 4: Cannot exceed farm stock
        # ------------------------------
        if self.empty_sent_to_wash > farm_available:
            raise ValidationError(
                f"{self.bottle_type.name}: Only {farm_available} bottles available."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("washing", "bottle_type")
        ordering = ["bottle_type"]
        indexes = [
            models.Index(fields=["washing"]),
        ]

    def __str__(self):
        return f"{self.washing.date} - {self.bottle_type.name}"

# ------------------------------
# Daily Closure
# ------------------------------

class DailyClosure(models.Model):
    date = models.DateField(unique=True)

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    locked = models.BooleanField(default=False)

    def clean(self):
        if self.locked and not self.closed_by:
            raise ValidationError("Closed day must have closed_by user")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.date)

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
        ]
# ------------------------------
# Van Movement
# ------------------------------

# ------------------------------
# Van Movement
# ------------------------------

class VanMovement(models.Model):
    date = models.DateField()

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="van_driver"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="van_created"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("date", "driver")
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.date} - {self.driver.username}"


# ------------------------------
# Van Movement Item
# ------------------------------

class VanMovementItem(models.Model):
    BREAKAGE_REASON_CHOICES = [
        ("TRANSPORT", "Transport Damage"),
        ("HANDLING", "Handling Mistake"),
        ("OTHER", "Other"),
    ]

    van_movement = models.ForeignKey(
        VanMovement,
        on_delete=models.CASCADE,
        related_name='items'
    )

    bottle_type = models.ForeignKey(
        BottleType,
        on_delete=models.CASCADE
    )

    empty_sent_to_farm = models.PositiveIntegerField(default=0)
    filled_received_from_farm = models.PositiveIntegerField(default=0)

    breakage = models.PositiveIntegerField(default=0)

    breakage_reason = models.CharField(
        max_length=50,
        choices=BREAKAGE_REASON_CHOICES,
        blank=True,
        null=True
    )

    def clean(self):

        # ✅ No negative values
        if self.empty_sent_to_farm < 0 or self.filled_received_from_farm < 0 or self.breakage < 0:
            raise ValidationError("Values cannot be negative")

        # ✅ Breakage reason required
        if self.breakage > 0 and not self.breakage_reason:
            raise ValidationError(
                "Breakage reason is required when breakage > 0."
            )

        # ✅ Breakage sanity
        if self.breakage > (self.empty_sent_to_farm + self.filled_received_from_farm):
            raise ValidationError("Breakage exceeds handled bottles")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("van_movement", "bottle_type")
        ordering = ["bottle_type"]
        indexes = [
            models.Index(fields=["van_movement"]),
        ]

    def __str__(self):
        return f"{self.van_movement.date} - {self.bottle_type.name}"

# ------------------------------
# Alert History
# ------------------------------

class AlertHistory(models.Model):
    date = models.DateField()

    message = models.TextField()  # ✅ flexible length

    created_at = models.DateTimeField(auto_now_add=True)  # ✅ timestamp

    def __str__(self):
        return f"{self.date} - {self.message[:50]}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['date']),
        ]
        
        
        



class OpeningStock(models.Model):
    date = models.DateField()

    bottle_type = models.ForeignKey(
        'BottleType',
        on_delete=models.CASCADE
    )

    # stock distribution
    farm_stock = models.IntegerField(default=0)
    warehouse_stock = models.IntegerField(default=0)
    customer_stock = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} - {self.bottle_type}"