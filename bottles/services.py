from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from collections import defaultdict

from .models import (
    BottleType,
    BottlePurchase,
    FarmDailyEntry,
    FarmDailyEntryItem,
    WarehouseDailyEntry,
    WarehouseDailyEntryItem,
    WashingCycleItem,
    DeliveryEntry,
    DeliveryEntryItem,
    AlertHistory,
    VanMovement,
    VanMovementItem
)

User = get_user_model()


# -------------------------------------------------
# GLOBAL STOCK VALIDATOR
# -------------------------------------------------

def validate_stock_available(current_stock, requested_qty, action_name):
    if requested_qty > current_stock:
        raise ValidationError(
            f"{action_name} cannot exceed available stock ({current_stock})."
        )


# -------------------------------------------------
# STOCK SUMMARY
# -------------------------------------------------

from django.db.models import Sum
from .models import (
    BottleType,
    BottlePurchase,
    DeliveryEntryItem,
    WarehouseDailyEntryItem,
    VanMovementItem,
    WashingCycleItem,
)


from django.db.models import Sum
from .models import (
    BottleType,
    BottlePurchase,
    DeliveryEntryItem,
    WarehouseDailyEntryItem,
    VanMovementItem,
    WashingCycleItem,
    OpeningStock
)


def get_stock_summary():
    summary = {}

    bottle_types = BottleType.objects.all()

    for bottle in bottle_types:

        # ------------------------------
        # OPENING STOCK (NEW)
        # ------------------------------
        opening = OpeningStock.objects.filter(
            bottle_type=bottle
        ).order_by('-date').first()

        opening_farm = opening.farm_stock if opening else 0
        opening_warehouse = opening.warehouse_stock if opening else 0
        opening_customer = opening.customer_stock if opening else 0

        # ------------------------------
        # PURCHASED
        # ------------------------------
        purchased = BottlePurchase.objects.filter(
            bottle_type=bottle
        ).aggregate(total=Sum("quantity"))["total"] or 0

        # ------------------------------
        # DELIVERY DATA (ONLY APPROVED)
        # ------------------------------
        delivered = DeliveryEntryItem.objects.filter(
            bottle_type=bottle,
            entry__status="APPROVED"
        ).aggregate(total=Sum("delivered"))["total"] or 0

        collected = DeliveryEntryItem.objects.filter(
            bottle_type=bottle,
            entry__status="APPROVED"
        ).aggregate(total=Sum("collected"))["total"] or 0

        delivery_breakage = DeliveryEntryItem.objects.filter(
            bottle_type=bottle,
            entry__status="APPROVED"
        ).aggregate(total=Sum("breakage"))["total"] or 0

        # ------------------------------
        # WAREHOUSE DATA
        # ------------------------------
        warehouse_breakage = WarehouseDailyEntryItem.objects.filter(
            bottle_type=bottle
        ).aggregate(total=Sum("warehouse_breakage"))["total"] or 0

        # ------------------------------
        # VAN MOVEMENT
        # ------------------------------
        empty_sent_to_farm = VanMovementItem.objects.filter(
            bottle_type=bottle
        ).aggregate(total=Sum("empty_sent_to_farm"))["total"] or 0

        filled_received_from_farm = VanMovementItem.objects.filter(
            bottle_type=bottle
        ).aggregate(total=Sum("filled_received_from_farm"))["total"] or 0

        van_breakage = VanMovementItem.objects.filter(
            bottle_type=bottle
        ).aggregate(total=Sum("breakage"))["total"] or 0

        # ------------------------------
        # WASHING CYCLE
        # ------------------------------
        collected_after_wash = WashingCycleItem.objects.filter(
            bottle_type=bottle
        ).aggregate(total=Sum("ready_after_wash"))["total"] or 0

        washing_breakage = WashingCycleItem.objects.filter(
            bottle_type=bottle
        ).aggregate(total=Sum("washing_breakage"))["total"] or 0

        # ------------------------------
        # TOTAL BREAKAGE
        # ------------------------------
        total_breakage = (
            delivery_breakage +
            warehouse_breakage +
            van_breakage +
            washing_breakage
        )

        # ------------------------------
        # CUSTOMER STOCK (OUTSTANDING)
        # ------------------------------
        customer_stock = max(
            opening_customer
            + delivered
            - collected
            - delivery_breakage,
            0
        )

        # ------------------------------
        # WAREHOUSE STOCK
        # ------------------------------
        warehouse_stock = max(
            opening_warehouse
            + filled_received_from_farm
            - delivered
            + collected
            - empty_sent_to_farm
            - warehouse_breakage,
            0
        )

        # ------------------------------
        # FARM STOCK
        # ------------------------------
        farm_stock = max(
            opening_farm
            + purchased
            + empty_sent_to_farm
            - filled_received_from_farm
            - total_breakage,
            0
        )

        # ------------------------------
        # FINAL SUMMARY
        # ------------------------------
        summary[bottle.name] = {
            "purchased": purchased,
            "farm_stock": farm_stock,
            "warehouse_stock": warehouse_stock,
            "customer_stock": customer_stock,
            "breakage": total_breakage,
        }

    return summary

from django.db.models import Sum
from .models import OpeningOutstanding, BottleType, DeliveryEntry, DeliveryEntryItem
from django.contrib.auth import get_user_model
User = get_user_model()  # adjust if your User model path is different


def get_route_outstanding():
    results = []

    delivery_users = User.objects.filter(role="DELIVERY")
    bottle_types = BottleType.objects.all()

    for user in delivery_users:
        bottle_summary = {}

        entries = DeliveryEntry.objects.filter(submitted_by=user)
        
        
        for bottle in bottle_types:

            delivered = DeliveryEntryItem.objects.filter(
                entry__in=entries,
                bottle_type=bottle
            ).aggregate(total=Sum("delivered"))["total"] or 0

            collected = DeliveryEntryItem.objects.filter(
                entry__in=entries,
                bottle_type=bottle
            ).aggregate(total=Sum("collected"))["total"] or 0

            breakage = DeliveryEntryItem.objects.filter(
                entry__in=entries,
                bottle_type=bottle
            ).aggregate(total=Sum("breakage"))["total"] or 0

            opening = OpeningOutstanding.objects.filter(
                driver=user,
                bottle_type=bottle
            ).aggregate(total=Sum("quantity"))["total"] or 0

            outstanding = opening + delivered - (collected + breakage)

            # ✅ FIX: clean key mapping
            if "1" in bottle.name:
                key = "1L"
            else:
                key = "500ML"

            bottle_summary[key] = {
                "delivered": delivered,
                "collected": collected,
                "breakage": breakage,
                "opening": opening,
                "outstanding": outstanding,
            }

        # ✅ totals (for alert logic)
        total_delivered = sum(b["delivered"] for b in bottle_summary.values())
        total_collected = sum(b["collected"] for b in bottle_summary.values())
        total_breakage = sum(b["breakage"] for b in bottle_summary.values())
        total_outstanding = sum(b["outstanding"] for b in bottle_summary.values())

        results.append({
            "delivery_user": user,
            "bottle_data": bottle_summary,
            "delivered": total_delivered,
            "collected": total_collected,
            "breakage": total_breakage,
            "outstanding": total_outstanding,
        })

    return results


# -------------------------------------------------
# RETURN DELAY TRACKER
# -------------------------------------------------

def get_bottle_return_delays():
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    delayed_records = []

    yesterday_deliveries = DeliveryEntryItem.objects.filter(
        entry__assignment__date=yesterday
    ).values("bottle_type__name").annotate(
        delivered_total=Sum("delivered")
    )

    today_collections = DeliveryEntryItem.objects.filter(
        entry__assignment__date=today
    ).values("bottle_type__name").annotate(
        collected_total=Sum("collected")
    )

    collected_map = {
        item["bottle_type__name"]: item["collected_total"]
        for item in today_collections
    }

    for delivery in yesterday_deliveries:
        bottle = delivery["bottle_type__name"]
        expected = delivery["delivered_total"]
        collected = collected_map.get(bottle, 0)

        if collected < expected:
            delayed_records.append({
                "bottle_type": bottle,
                "expected": expected,
                "collected": collected,
                "missing": expected - collected
            })

    return delayed_records


# -------------------------------------------------
# TODAY ALERTS
# -------------------------------------------------

def get_today_alerts():
    today = timezone.localdate()
    alerts = []

    bottle_types = BottleType.objects.all()

    for bottle in bottle_types:

        delivery_breakage = DeliveryEntryItem.objects.filter(
            bottle_type=bottle,
            entry__assignment__date=today
        ).aggregate(total=Sum("breakage"))["total"] or 0

        warehouse_breakage = WarehouseDailyEntryItem.objects.filter(
            bottle_type=bottle,
            warehouse_entry__date=today
        ).aggregate(total=Sum("warehouse_breakage"))["total"] or 0

        van_breakage = VanMovementItem.objects.filter(
            bottle_type=bottle,
            van_movement__date=today
        ).aggregate(total=Sum("breakage"))["total"] or 0

        washing_breakage = WashingCycleItem.objects.filter(
            bottle_type=bottle,
            washing__date=today
        ).aggregate(total=Sum("washing_breakage"))["total"] or 0

        total_breakage = (
            delivery_breakage +
            warehouse_breakage +
            van_breakage +
            washing_breakage
        )

        if total_breakage > 0:
            alerts.append(
                f"{bottle.name}: Damaged bottles = {total_breakage}"
            )

    return alerts


def save_today_alerts():
    today = timezone.localdate()
    alerts = get_today_alerts()

    for alert in alerts:
        AlertHistory.objects.get_or_create(
            date=today,
            message=alert
        )


# -------------------------------------------------
# LIVE BOTTLE FLOW
# -------------------------------------------------

def get_live_bottle_flow():

    data = {}

    latest_entry = FarmDailyEntry.objects.order_by('-date').first()

    if not latest_entry:
        return data

    bottle_types = BottleType.objects.all()

    for bottle in bottle_types:

        farm_item = FarmDailyEntryItem.objects.filter(
            farm_entry=latest_entry,
            bottle_type=bottle
        ).first()

        warehouse_item = WarehouseDailyEntryItem.objects.filter(
            bottle_type=bottle
        ).aggregate(
            received=Sum('received_from_farm'),
            empty=Sum('empty_received_from_delivery'),
            sent_farm=Sum('empty_sent_to_farm')
        )

        delivery_item = DeliveryEntryItem.objects.filter(
            bottle_type=bottle
        ).aggregate(
            delivered=Sum('delivered'),
            collected=Sum('collected')
        )

        wash_item = WashingCycleItem.objects.filter(
            bottle_type=bottle
        ).aggregate(
            sent=Sum('empty_sent_to_wash'),
            ready=Sum('ready_after_wash')
        )

        data[bottle.name] = {
            "sent_from_farm": farm_item.sent_to_warehouse if farm_item else 0,
            "warehouse_received": warehouse_item['received'] or 0,
            "empty_collected": delivery_item['collected'] or 0,
            "empty_received_farm": warehouse_item['sent_farm'] or 0,
            "sent_to_wash": wash_item['sent'] or 0,
            "collected_after_wash": wash_item['ready'] or 0,
        }

    return data

# -------------------------------------------------
# FARM ENTRY CREATE
# -------------------------------------------------

def create_farm_entry(date, items):
    stock = get_stock_summary()

    errors = []

    for item in items:
        bottle_name = item['bottle_type'].name
        farm_stock = stock[bottle_name]["farm_stock"]

        if item['sent_to_warehouse'] > farm_stock:
            errors.append(
                f"{bottle_name} farm dispatch cannot exceed available stock ({farm_stock})"
            )

    if errors:
        raise ValidationError(errors)

    farm_entry = FarmDailyEntry.objects.create(date=date)

    for item in items:
        FarmDailyEntryItem.objects.create(
            farm_entry=farm_entry,
            bottle_type=item['bottle_type'],
            sent_to_warehouse=item['sent_to_warehouse'],
            empty_received_from_warehouse=item['empty_received_from_warehouse']
        )

    return farm_entry


# -------------------------------------------------
# WAREHOUSE ENTRY CREATE (UPDATED)
# -------------------------------------------------

def create_warehouse_entry(date, entry_type, items):

    stock = get_stock_summary()

    errors = []

    # Create entry first (will delete if error)
    warehouse_entry = WarehouseDailyEntry.objects.create(
        date=date,
        entry_type=entry_type
    )

    for item in items:
        bottle = item['bottle_type']
        bottle_name = bottle.name

        warehouse_stock = stock[bottle_name]["warehouse_stock"]
        customer_stock = stock[bottle_name]["customer_stock"]

        received = item.get('received_from_farm', 0)
        empty_delivery = item.get('empty_received_from_delivery', 0)
        empty_sent = item.get('empty_sent_to_farm', 0)
        breakage = item.get('warehouse_breakage', 0)
        reason = item.get('breakage_reason', '')

        # -------------------------
        # BREAKAGE VALIDATION
        # -------------------------
        if breakage > 0 and not reason:
            errors.append(f"{bottle_name}: Breakage reason required.")

        # -------------------------
        # INWARD (Morning)
        # -------------------------
        if entry_type == "INWARD":

            if received < 0:
                errors.append(f"{bottle_name}: Invalid received quantity.")

            # Optional strict rule:
            # received + breakage consistency (you mentioned)
            # no strict limit needed here unless business defines it

        # -------------------------
        # OUTWARD (Evening)
        # -------------------------
        elif entry_type == "OUTWARD":

            # Rule 1
            if empty_delivery > (customer_stock + breakage):
                errors.append(
                    f"{bottle_name}: Empty received exceeds customer stock ({customer_stock})."
                )

            # Rule 2
            if empty_sent != empty_delivery:
                errors.append(
                    f"{bottle_name}: Empty sent must equal empty received."
                )

            # Rule 3
            if empty_sent > warehouse_stock:
                errors.append(
                    f"{bottle_name}: Not enough warehouse stock ({warehouse_stock})."
                )

        # -------------------------
        # CREATE ITEM
        # -------------------------
        WarehouseDailyEntryItem.objects.create(
            warehouse_entry=warehouse_entry,
            bottle_type=bottle,

            received_from_farm=received if entry_type == "INWARD" else 0,

            empty_received_from_delivery=empty_delivery if entry_type == "OUTWARD" else 0,
            empty_sent_to_farm=empty_sent if entry_type == "OUTWARD" else 0,

            warehouse_breakage=breakage,
            breakage_reason=reason
        )

    # -------------------------
    # FINAL ERROR CHECK
    # -------------------------
    if errors:
        warehouse_entry.delete()
        raise ValidationError(errors)

    return warehouse_entry


# -------------------------------------------------
# VAN MOVEMENT CREATE
# -------------------------------------------------

def create_van_movement(date, driver, created_by, items):
    stock = get_stock_summary()

    errors = []

    for item in items:
        bottle_name = item['bottle_type'].name

        farm_stock = stock[bottle_name]["farm_stock"]
        warehouse_stock = stock[bottle_name]["warehouse_stock"]

        if item['filled_received_from_farm'] > farm_stock:
            errors.append(
                f"{bottle_name} van loading from farm cannot exceed available stock ({farm_stock})"
            )

        if item['empty_sent_to_farm'] > warehouse_stock:
            errors.append(
                f"{bottle_name} empty return to farm cannot exceed warehouse stock ({warehouse_stock})"
            )

    if errors:
        raise ValidationError(errors)

    van = VanMovement.objects.create(
        date=date,
        driver=driver,
        created_by=created_by
    )

    for item in items:
        VanMovementItem.objects.create(
            van_movement=van,
            bottle_type=item['bottle_type'],
            empty_sent_to_farm=item['empty_sent_to_farm'],
            filled_received_from_farm=item['filled_received_from_farm'],
            breakage=item['breakage'],
            breakage_reason=item['breakage_reason']
        )

    return van


# -------------------------------------------------
# ALERT HISTORY GROUPED
# -------------------------------------------------

def get_all_alerts_grouped_by_date():
    alerts_by_date = defaultdict(list)

    history = AlertHistory.objects.all().order_by("-date")

    for item in history:
        alerts_by_date[item.date].append(item.message)

    return alerts_by_date


from django.db.models import Sum

def get_today_process_summary(today):
    summary = {}

    bottle_types = BottleType.objects.all()

    for bottle in bottle_types:

        # 1. Prepared and sent (Farm → Van)
        prepared_sent = FarmDailyEntryItem.objects.filter(
            bottle_type=bottle,
            farm_entry__date=today
        ).aggregate(total=Sum("sent_to_warehouse"))["total"] or 0
        # 2. Warehouse received (Farm → Warehouse)
        warehouse_received = WarehouseDailyEntryItem.objects.filter(
            bottle_type=bottle,
            warehouse_entry__date=today,
            warehouse_entry__entry_type="INWARD"
        ).aggregate(total=Sum("received_from_farm"))["total"] or 0

        # 3. Empty collected from customers
        empty_collected = DeliveryEntryItem.objects.filter(
            bottle_type=bottle,
            entry__assignment__date=today
        ).aggregate(total=Sum("collected"))["total"] or 0

        # 4. Empty received back at farm (Van → Farm)
        empty_received_farm = VanMovementItem.objects.filter(
            bottle_type=bottle,
            van_movement__date=today
        ).aggregate(total=Sum("empty_sent_to_farm"))["total"] or 0

        # 5. Sent to washing
        sent_to_wash = WashingCycleItem.objects.filter(
            bottle_type=bottle,
            washing__date=today
        ).aggregate(total=Sum("empty_sent_to_wash"))["total"] or 0

        # 6. Ready after washing
        collected_after_wash = WashingCycleItem.objects.filter(
            bottle_type=bottle,
            washing__date=today
        ).aggregate(total=Sum("ready_after_wash"))["total"] or 0

        summary[bottle.name] = {
            "prepared_sent": prepared_sent,
            "warehouse_received": warehouse_received,
            "empty_collected": empty_collected,
            "empty_received_farm": empty_received_farm,
            "sent_to_wash": sent_to_wash,
            "collected_after_wash": collected_after_wash,
        }

    return summary




from django.db.models import Sum
from .models import (
    VanMovementItem,
    WarehouseDailyEntryItem,
    DeliveryEntryItem,
    WashingCycleItem
)

def get_current_stock(bottle):

    # ---------------- FARM ----------------
    farm_sent = VanMovementItem.objects.filter(
        bottle_type=bottle
    ).aggregate(total=Sum("filled_received_from_farm"))["total"] or 0

    farm_received = VanMovementItem.objects.filter(
        bottle_type=bottle
    ).aggregate(total=Sum("empty_sent_to_farm"))["total"] or 0

    farm_stock = farm_received - farm_sent

    # ---------------- WAREHOUSE ----------------
    warehouse_in = WarehouseDailyEntryItem.objects.filter(
        bottle_type=bottle,
        warehouse_entry__entry_type="INWARD"
    ).aggregate(total=Sum("received_from_farm"))["total"] or 0

    warehouse_out = WarehouseDailyEntryItem.objects.filter(
        bottle_type=bottle,
        warehouse_entry__entry_type="OUTWARD"
    ).aggregate(total=Sum("empty_sent_to_farm"))["total"] or 0

    warehouse_stock = warehouse_in - warehouse_out

    # ---------------- CUSTOMER ----------------
    delivered = DeliveryEntryItem.objects.filter(
        bottle_type=bottle
    ).aggregate(total=Sum("delivered"))["total"] or 0

    collected = DeliveryEntryItem.objects.filter(
        bottle_type=bottle
    ).aggregate(total=Sum("collected"))["total"] or 0

    customer_stock = delivered - collected

    # ---------------- WASHING ----------------
    sent_to_wash = WashingCycleItem.objects.filter(
        bottle_type=bottle
    ).aggregate(total=Sum("empty_sent_to_wash"))["total"] or 0

    ready_after_wash = WashingCycleItem.objects.filter(
        bottle_type=bottle
    ).aggregate(total=Sum("ready_after_wash"))["total"] or 0

    washing_stock = sent_to_wash - ready_after_wash

    return {
        "farm": farm_stock,
        "warehouse": warehouse_stock,
        "customer": customer_stock,
        "washing": washing_stock
    }
    
    
    
    
    
    
    

from django.db.models import Sum
from .models import DeliveryEntryItem

def get_customer_outstanding(bottle_type):

    total_delivered = DeliveryEntryItem.objects.filter(
        bottle_type=bottle_type,
        entry__status="APPROVED"
    ).aggregate(total=Sum("delivered"))["total"] or 0

    total_collected = DeliveryEntryItem.objects.filter(
        bottle_type=bottle_type,
        entry__status="APPROVED"
    ).aggregate(total=Sum("collected"))["total"] or 0

    total_breakage = DeliveryEntryItem.objects.filter(
        bottle_type=bottle_type,
        entry__status="APPROVED"
    ).aggregate(total=Sum("breakage"))["total"] or 0

    outstanding = total_delivered - total_collected - total_breakage

    return max(outstanding, 0)





# =================================================
# STOCK CALCULATION (WAREHOUSE)
# =================================================

from django.db.models import Sum

def get_warehouse_stock(bottle):

    data = WarehouseDailyEntryItem.objects.filter(
        bottle_type=bottle
    ).aggregate(
        farm=Sum('received_from_farm'),
        collected=Sum('empty_received_from_delivery'),
        sent_farm=Sum('empty_sent_to_farm'),
        sent_delivery=Sum('filled_sent_to_delivery'),
        breakage=Sum('warehouse_breakage')
    )

    farm = data['farm'] or 0
    collected = data['collected'] or 0
    sent_farm = data['sent_farm'] or 0
    sent_delivery = data['sent_delivery'] or 0
    breakage = data['breakage'] or 0

    stock = farm + collected - sent_farm - sent_delivery - breakage

    # =========================
    # VALIDATION
    # =========================

    if stock < 0:
        # Optional: log or raise alert
        print(f"[WARNING] Negative warehouse stock for {bottle.name}: {stock}")
        stock = 0  # safeguard

    return stock