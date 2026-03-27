from django.contrib import admin
from .models import (
    BottleType,
    BottlePurchase,
    FarmDailyEntry,
    FarmDailyEntryItem,
    WarehouseDailyEntry,
    WarehouseDailyEntryItem,
    WashingCycle,
    WashingCycleItem,
    DeliveryAssignment,
    DeliveryAssignmentItem,
    DeliveryEntry,
    DeliveryEntryItem,
    DailyClosure,
    VanMovement,
    VanMovementItem
)


# ------------------------------
# Farm Daily Entry Inline
# ------------------------------

class FarmDailyEntryItemInline(admin.TabularInline):
    model = FarmDailyEntryItem
    extra = 1


@admin.register(FarmDailyEntry)
class FarmDailyEntryAdmin(admin.ModelAdmin):
    list_display = ("date",)
    inlines = [FarmDailyEntryItemInline]


# ------------------------------
# Warehouse Daily Entry Inline
# ------------------------------

class WarehouseDailyEntryItemInline(admin.TabularInline):
    model = WarehouseDailyEntryItem
    extra = 1


@admin.register(WarehouseDailyEntry)
class WarehouseDailyEntryAdmin(admin.ModelAdmin):
    list_display = ("date",)
    inlines = [WarehouseDailyEntryItemInline]


# ------------------------------
# Delivery Assignment Inline
# ------------------------------

class DeliveryAssignmentItemInline(admin.TabularInline):
    model = DeliveryAssignmentItem
    extra = 2


@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = ("date", "delivery_user", "created_by")
    inlines = [DeliveryAssignmentItemInline]


# ------------------------------
# Delivery Entry Inline
# ------------------------------

class DeliveryEntryItemInline(admin.TabularInline):
    model = DeliveryEntryItem
    extra = 2


@admin.register(DeliveryEntry)
class DeliveryEntryAdmin(admin.ModelAdmin):
    list_display = ("assignment", "status")
    inlines = [DeliveryEntryItemInline]


# ------------------------------
# Washing Cycle Inline
# ------------------------------

class WashingCycleItemInline(admin.TabularInline):
    model = WashingCycleItem
    extra = 1


@admin.register(WashingCycle)
class WashingCycleAdmin(admin.ModelAdmin):
    inlines = [WashingCycleItemInline]


# ------------------------------
# Register Remaining Models
# ------------------------------

admin.site.register(BottleType)
admin.site.register(BottlePurchase)
admin.site.register(DailyClosure)





# Van movements

class VanMovementItemInline(admin.TabularInline):
    model = VanMovementItem
    extra = 0


@admin.register(VanMovement)
class VanMovementAdmin(admin.ModelAdmin):
    inlines = [VanMovementItemInline]




from .models import OpeningStock

@admin.register(OpeningStock)
class OpeningStockAdmin(admin.ModelAdmin):
    list_display = ['date', 'bottle_type', 'farm_stock', 'warehouse_stock', 'customer_stock']
    
    
    
from .models import OpeningOutstanding

admin.site.register(OpeningOutstanding)