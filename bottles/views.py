# =================================================
# IMPORTS
# =================================================

from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse


from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from accounts.models import CustomUser

from .models import (
    DeliveryEntry,
    DeliveryEntryItem,
    DeliveryAssignment,
    DailyClosure,
    AlertHistory,
    BottleType,
    WashingCycle,
    WashingCycleItem,
    FarmDailyEntryItem,
    WarehouseDailyEntry,
    WarehouseDailyEntryItem
)

from .forms import (
    FarmDailyEntryForm,
    WarehouseDailyEntryForm,
    VanMovementForm,
    WashingCycleForm,
)

from .decorators import role_required

from .services import (
    get_bottle_return_delays,
    get_live_bottle_flow,
    get_today_process_summary,
    get_stock_summary,
    get_route_outstanding,
    create_farm_entry,
    create_warehouse_entry,
    create_van_movement,
)

from .reports import get_delivery_performance





def reports_dashboard(request):
    month = request.GET.get('month')

    report = get_delivery_performance(month)

    # sort
    report = sorted(report, key=lambda x: x['score'], reverse=True)

    # 🔥 Prepare chart data
    labels = []
    delivered_data = []
    collected_data = []

    for item in report:
        labels.append(item['user'].username)
        delivered_data.append(item['delivered'])
        collected_data.append(item['collected'])

    # optional
    top_performer = report[0] if report else None

    return render(request, 'reports/dashboard.html', {
        'report': report,
        'labels': labels,
        'delivered_data': delivered_data,
        'collected_data': collected_data,
        'top_performer': top_performer,
    })
# =================================================
# DELIVERY ENTRY
# =================================================



@login_required
@role_required("DELIVERY")
def delivery_entry(request):

    from bottles.services import get_customer_outstanding

    today = timezone.localdate()

    assignment = DeliveryAssignment.objects.filter(
        date=today,
        delivery_user=request.user
    ).prefetch_related("items__bottle_type").first()

    # ❌ No assignment
    if not assignment:
        return render(request, "bottles/no_assignment.html")

    # 🔴 Prevent duplicate submission
    if DeliveryEntry.objects.filter(assignment=assignment).exists():
        messages.info(request, "You have already submitted today's delivery entry.")
        return redirect("bottles:delivery_list")

    bottle_items = list(assignment.items.all())

    if request.method == "POST":

        delivered_list = request.POST.getlist("delivered")
        collected_list = request.POST.getlist("collected")
        breakage_list = request.POST.getlist("breakage")

        # ✅ Length safety check
        if not (len(delivered_list) == len(bottle_items) == len(collected_list) == len(breakage_list)):
            messages.error(request, "Invalid form submission. Please try again.")
            return redirect("bottles:delivery_entry")

        try:
            with transaction.atomic():

                entry = DeliveryEntry.objects.create(
                    assignment=assignment,
                    submitted_by=request.user,
                    status="PENDING"
                )

                # 🔥 LOOP THROUGH ITEMS
                for i, assigned_item in enumerate(bottle_items):

                    # ✅ Safe parsing
                    try:
                        delivered_qty = int(delivered_list[i] or 0)
                        collected_qty = int(collected_list[i] or 0)
                        breakage_qty = int(breakage_list[i] or 0)
                    except ValueError:
                        raise ValidationError("Invalid number input")

                    # ✅ Validation 1: Delivered ≤ Assigned
                    if delivered_qty > assigned_item.quantity_assigned:
                        raise ValidationError(
                            f"{assigned_item.bottle_type.name} exceeds assigned quantity ({assigned_item.quantity_assigned})"
                        )

                    # ✅ Validation 2: No negative values
                    if delivered_qty < 0 or collected_qty < 0 or breakage_qty < 0:
                        raise ValidationError(
                            f"{assigned_item.bottle_type.name}: Negative values not allowed"
                        )

                    # ✅ Validation 3: Collected ≤ Customer Outstanding
                    outstanding = get_customer_outstanding(assigned_item.bottle_type)

                    if collected_qty > outstanding:
                        raise ValidationError(
                            f"{assigned_item.bottle_type.name}: Cannot collect more than outstanding ({outstanding})"
                        )

                    # (Optional) Breakage sanity check
                    if breakage_qty > (delivered_qty + collected_qty):
                        raise ValidationError(
                            f"{assigned_item.bottle_type.name}: Breakage too high"
                        )

                    # ✅ Save item
                    DeliveryEntryItem.objects.create(
                        entry=entry,
                        bottle_type=assigned_item.bottle_type,
                        delivered=delivered_qty,
                        collected=collected_qty,
                        breakage=breakage_qty
                    )

            messages.success(request, "Delivery entry saved successfully.")
            return redirect("bottles:delivery_list")

        except ValidationError as e:
            messages.error(request, str(e))

        except Exception:
            messages.error(request, "Something went wrong. Please try again.")

    # ✅ Outstanding for display
    for item in bottle_items:
        item.outstanding = get_customer_outstanding(item.bottle_type)

    return render(request, "bottles/delivery_entry_form.html", {
        "assignment": assignment,
        "bottle_items": bottle_items,
    })
# =================================================
# DELIVERY LIST
# =================================================

@login_required
@role_required("DELIVERY")
def delivery_list(request):

    entries = DeliveryEntry.objects.filter(
        submitted_by=request.user
    ).order_by('-id')

    return render(request, 'bottles/delivery_list.html', {'entries': entries})


# =================================================
# SUPERVISOR PANEL
# =================================================

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db import transaction


@login_required
def supervisor_panel(request):

    if request.user.role not in ["SUPERVISOR", "ADMIN"]:
        raise PermissionDenied

    # ✅ Show pending first (clean UX)
    pending_entries = DeliveryEntry.objects.filter(
        status="PENDING"
    ).order_by('-id')

    return render(request, 'bottles/supervisor_panel.html', {
        'pending_entries': pending_entries
    })


# =================================================
# APPROVE ENTRY
# =================================================

@login_required
def approve_entry(request, pk):

    if request.user.role not in ["SUPERVISOR", "ADMIN"]:
        raise PermissionDenied

    entry = get_object_or_404(DeliveryEntry, pk=pk)

    # ✅ Prevent re-approval
    if entry.status != "PENDING":
        messages.warning(request, "Entry already processed")
        return redirect('bottles:supervisor_panel')

    try:
        with transaction.atomic():
            entry.status = 'APPROVED'
            entry.approved_by = request.user
            entry.save()

        messages.success(request, "Entry approved successfully")

    except Exception:
        messages.error(request, "Something went wrong")

    return redirect('bottles:supervisor_panel')


# =================================================
# REJECT ENTRY
# =================================================

@login_required
def reject_entry(request, pk):

    if request.user.role not in ["SUPERVISOR", "ADMIN"]:
        raise PermissionDenied

    entry = get_object_or_404(DeliveryEntry, pk=pk)

    # ✅ Prevent re-rejection
    if entry.status != "PENDING":
        messages.warning(request, "Entry already processed")
        return redirect('bottles:supervisor_panel')

    try:
        with transaction.atomic():
            entry.status = 'REJECTED'
            entry.save()

        messages.success(request, "Entry rejected")

    except Exception:
        messages.error(request, "Something went wrong")

    return redirect('bottles:supervisor_panel')





# =================================================
# SUPERVISOR ASSIGNMENT
# =================================================

from django.db import transaction
from django.utils.dateparse import parse_date
from .services import get_warehouse_stock

@login_required
def assign_delivery_view(request):

    from .services import get_warehouse_stock

    if request.user.role not in ["SUPERVISOR", "ADMIN"]:
        raise PermissionDenied

    bottle_types = BottleType.objects.all()
    delivery_users = CustomUser.objects.filter(role="DELIVERY")

    warehouse_stock = {
        bottle.id: get_warehouse_stock(bottle)
        for bottle in bottle_types
    }

    if request.method == "POST":

        try:
            delivery_user = get_object_or_404(
                CustomUser,
                id=request.POST.get("delivery_user")
            )

            date = parse_date(request.POST.get("date"))

            if not date:
                messages.error(request, "Invalid date")
                return redirect("bottles:assign_delivery")

            # 🔴 Prevent duplicate assignment
            if DeliveryAssignment.objects.filter(
                delivery_user=delivery_user,
                date=date
            ).exists():
                messages.error(request, "Assignment already exists")
                return redirect("bottles:assign_delivery")

            # =========================
            # SAFE PARSING FIRST
            # =========================
            parsed_data = []

            for bottle in bottle_types:
                try:
                    qty = int(request.POST.get(f"qty_{bottle.id}") or 0)
                except ValueError:
                    messages.error(request, f"{bottle.name}: Invalid number")
                    return redirect("bottles:assign_delivery")

                available = warehouse_stock[bottle.id]

                # VALIDATION
                if qty < 0:
                    messages.error(request, f"{bottle.name}: Negative quantity not allowed")
                    return redirect("bottles:assign_delivery")

                if qty > available:
                    messages.error(
                        request,
                        f"{bottle.name}: Only {available} available"
                    )
                    return redirect("bottles:assign_delivery")

                parsed_data.append((bottle, qty))

            # 🔴 Prevent empty assignment
            if all(qty == 0 for _, qty in parsed_data):
                messages.error(request, "Please assign at least one bottle")
                return redirect("bottles:assign_delivery")

            # =========================
            # SAVE (ATOMIC)
            # =========================
            with transaction.atomic():

                assignment = DeliveryAssignment.objects.create(
                    delivery_user=delivery_user,
                    date=date,
                    created_by=request.user
                )

                warehouse_entry, _ = WarehouseDailyEntry.objects.get_or_create(
                    date=date,
                    entry_type='OUTWARD'
                )

                for bottle, qty in parsed_data:

                    if qty > 0:

                        assignment.items.create(
                            bottle_type=bottle,
                            quantity_assigned=qty
                        )

                        item, _ = WarehouseDailyEntryItem.objects.get_or_create(
                            warehouse_entry=warehouse_entry,
                            bottle_type=bottle,
                            defaults={"filled_sent_to_delivery": 0}
                        )

                        item.filled_sent_to_delivery += qty
                        item.save()

            messages.success(request, "Assignment created successfully")
            return redirect("bottles:supervisor_panel")

        except Exception:
            messages.error(request, "Something went wrong. Please try again.")
            return redirect("bottles:assign_delivery")

    return render(request, "bottles/assign_delivery.html", {
        "bottle_types": bottle_types,
        "delivery_users": delivery_users,
        "warehouse_stock": warehouse_stock
    })
    
    
    
    
# =================================================
# ADMIN DAY CONTROL
# =================================================

@login_required
@role_required("ADMIN")
def admin_close_day(request):

    today = timezone.localdate()

    try:
        with transaction.atomic():

            closure, _ = DailyClosure.objects.get_or_create(date=today)

            # ✅ Prevent double closing
            if closure.locked:
                messages.warning(request, "Day is already closed.")
                return redirect('dashboard:home')

            closure.locked = True
            closure.closed_by = request.user
            closure.save()

        messages.success(request, "Day closed successfully.")

    except Exception:
        messages.error(request, "Something went wrong")

    return redirect('dashboard:home')


@login_required
@role_required("ADMIN")
def admin_reopen_day(request):

    today = timezone.localdate()

    try:
        with transaction.atomic():

            closure = DailyClosure.objects.get(date=today)

            # ✅ Prevent reopening if already open
            if not closure.locked:
                messages.warning(request, "Day is already open.")
                return redirect('dashboard:home')

            closure.locked = False
            closure.save()

        messages.success(request, "Day reopened successfully.")

    except DailyClosure.DoesNotExist:
        messages.error(request, "No closure record found for today.")

    except Exception:
        messages.error(request, "Something went wrong")

    return redirect('dashboard:home')






# =================================================
# FARM ENTRY
# =================================================

@login_required
@role_required("FARM")
def farm_entry_view(request):

    bottle_types = BottleType.objects.all()

    if request.method == 'POST':
        form = FarmDailyEntryForm(request.POST)

        if form.is_valid():
            date = form.cleaned_data['date']
            items = []

            try:
                has_data = False  # ✅ prevent empty entry

                for bottle in bottle_types:

                    # ✅ Safe parsing
                    try:
                        sent = int(request.POST.get(f"sent_{bottle.id}") or 0)
                        empty_received = int(request.POST.get(f"empty_{bottle.id}") or 0)
                        breakage = int(request.POST.get(f"breakage_{bottle.id}") or 0)
                    except ValueError:
                        raise ValidationError(f"{bottle.name}: Invalid number input")

                    reason = request.POST.get(f"reason_{bottle.id}", "").strip()

                    # ✅ Validation 1: No negative values
                    if sent < 0 or empty_received < 0 or breakage < 0:
                        raise ValidationError(f"{bottle.name}: Negative values not allowed")

                    # ✅ Validation 2: Breakage reason required
                    if breakage > 0 and not reason:
                        raise ValidationError(f"{bottle.name}: Breakage reason required")

                    if sent > 0 or empty_received > 0 or breakage > 0:
                        has_data = True

                    items.append({
                        'bottle_type': bottle,
                        'sent_to_warehouse': sent,
                        'empty_received_from_warehouse': empty_received,
                        'empty_breakage': breakage,
                        'breakage_reason': reason
                    })

                # 🔴 Prevent empty submission
                if not has_data:
                    raise ValidationError("Please enter at least one value")

                create_farm_entry(date, items)

                messages.success(request, "Farm entry saved successfully.")
                return redirect('bottles:farm_entry')

            except ValidationError as e:
                messages.error(request, str(e))

            except Exception:
                messages.error(request, "Something went wrong. Please try again.")

    else:
        form = FarmDailyEntryForm()

    return render(request, 'bottles/farm_entry.html', {
        'form': form,
        'bottle_types': bottle_types
    })

# =================================================
# WAREHOUSE ENTRY
# =================================================

@login_required
@role_required("WAREHOUSE")
def warehouse_entry_view(request):

    bottle_types = BottleType.objects.all()

    if request.method == 'POST':
        form = WarehouseDailyEntryForm(request.POST)

        if form.is_valid():
            date = form.cleaned_data['date']
            entry_type = request.POST.get("entry_type")

            if entry_type not in ["INWARD", "OUTWARD"]:
                messages.error(request, "Invalid entry type")
                return redirect("bottles:warehouse_entry")

            items = []

            try:
                has_data = False

                for bottle in bottle_types:

                    # ✅ Safe parsing
                    try:
                        received = int(request.POST.get(f"received_{bottle.id}") or 0)
                        empty_delivery = int(request.POST.get(f"empty_delivery_{bottle.id}") or 0)
                        empty_farm = int(request.POST.get(f"empty_farm_{bottle.id}") or 0)
                        breakage = int(request.POST.get(f"breakage_{bottle.id}") or 0)
                    except ValueError:
                        raise ValidationError(f"{bottle.name}: Invalid number input")

                    reason = request.POST.get(f"reason_{bottle.id}", "").strip()

                    # ✅ Validation 1: No negatives
                    if received < 0 or empty_delivery < 0 or empty_farm < 0 or breakage < 0:
                        raise ValidationError(f"{bottle.name}: Negative values not allowed")

                    # ✅ Validation 2: Breakage reason
                    if breakage > 0 and not reason:
                        raise ValidationError(f"{bottle.name}: Breakage reason required")

                    # ✅ Track if any meaningful data exists
                    if received > 0 or empty_delivery > 0 or empty_farm > 0 or breakage > 0:
                        has_data = True

                    items.append({
                        'bottle_type': bottle,
                        'received_from_farm': received,
                        'empty_received_from_delivery': empty_delivery,
                        'empty_sent_to_farm': empty_farm,
                        'warehouse_breakage': breakage,
                        'breakage_reason': reason
                    })

                # 🔴 VALIDATION RULE
                if entry_type == "INWARD" and not has_data:
                    raise ValidationError("INWARD entry must have at least one value")

                # ✅ OUTWARD allowed even if all zero

                # -----------------------------
                # SAVE
                # -----------------------------
                create_warehouse_entry(
                    date=date,
                    entry_type=entry_type,
                    items=items
                )

                messages.success(request, f"{entry_type} entry saved successfully.")
                return redirect('bottles:warehouse_entry')

            except ValidationError as e:
                messages.error(request, str(e))

            except Exception as e:
                # 🔥 IMPORTANT: show real error (for debugging)
                messages.error(request, f"Error: {str(e)}")

    else:
        form = WarehouseDailyEntryForm()

    return render(request, 'bottles/warehouse_entry.html', {
        'form': form,
        'bottle_types': bottle_types
    })
# =================================================
# VAN ENTRY
# =================================================

@login_required
@role_required("DRIVER")
def van_entry_view(request):

    bottle_types = BottleType.objects.all()

    # -----------------------------
    # STEP 1: DATE HANDLING
    # -----------------------------
    if request.method == 'POST':
        form = VanMovementForm(request.POST)
        if form.is_valid():
            selected_date = form.cleaned_data['date']
        else:
            selected_date = timezone.localdate()
    else:
        form = VanMovementForm()
        selected_date = timezone.localdate()

    # -----------------------------
    # STEP 2: LOAD FARM DATA
    # -----------------------------
    farm_data = {}

    farm_items = FarmDailyEntryItem.objects.filter(
        farm_entry__date=selected_date
    )

    for item in farm_items:
        farm_data[item.bottle_type.id] = item.sent_to_warehouse

    # -----------------------------
    # STEP 3: HANDLE SUBMIT
    # -----------------------------
    if request.method == 'POST' and form.is_valid():

        driver = form.cleaned_data['driver']
        items = []

        try:
            has_data = False  # ✅ Track if any input exists

            for bottle in bottle_types:

                # ✅ Safe parsing
                try:
                    empty_sent = int(request.POST.get(f"empty_{bottle.id}") or 0)
                    breakage = int(request.POST.get(f"breakage_{bottle.id}") or 0)
                except ValueError:
                    raise ValidationError(f"{bottle.name}: Invalid number")

                reason = request.POST.get(f"reason_{bottle.id}", "").strip()
                filled_received = farm_data.get(bottle.id, 0)

                # ✅ Validation 1: No negatives
                if empty_sent < 0 or breakage < 0:
                    raise ValidationError(f"{bottle.name}: Negative values not allowed")

                # ✅ Validation 2: Breakage reason
                if breakage > 0 and not reason:
                    raise ValidationError(f"{bottle.name}: Breakage reason required")

                # ✅ Validation 3: Breakage sanity
                if breakage > (empty_sent + filled_received):
                    raise ValidationError(
                        f"{bottle.name}: Breakage exceeds handled bottles"
                    )

                # ✅ Track meaningful input
                if empty_sent > 0 or filled_received > 0 or breakage > 0:
                    has_data = True

                # ✅ Add item
                items.append({
                    'bottle_type': bottle,
                    'empty_sent_to_farm': empty_sent,
                    'filled_received_from_farm': filled_received,
                    'breakage': breakage,
                    'breakage_reason': reason
                })

            # 🔴 FINAL VALIDATION (AFTER LOOP)
            if not has_data:
                raise ValidationError(
                    "Enter at least one value (Loading, Unloading, or Breakage)"
                )

            # -----------------------------
            # SAVE
            # -----------------------------
            with transaction.atomic():
                create_van_movement(
                    date=selected_date,
                    driver=driver,
                    created_by=request.user,
                    items=items
                )

            messages.success(request, "Van entry saved successfully")
            return redirect('bottles:van_entry')

        except ValidationError as e:
            messages.error(request, str(e))

        except Exception:
            messages.error(request, "Something went wrong")

    # -----------------------------
    # STEP 4: RENDER
    # -----------------------------
    return render(request, 'bottles/van_entry.html', {
        'form': form,
        'bottle_types': bottle_types,
        'farm_data': farm_data,
        'selected_date': selected_date
    })
# =================================================
# ALERT HISTORY
# =================================================

@login_required
@role_required("ADMIN")
def alert_history(request):

    alerts = AlertHistory.objects.all().order_by('-date')[:50]

    return render(request, "bottles/alert_history.html", {
        "alerts": alerts
    })
    
    
    
    
# =================================================
# WASHING CYCLE
# =================================================

@login_required
@role_required("FARM")
def washing_cycle_view(request):

    bottle_types = BottleType.objects.all()

    if request.method == "POST":
        form = WashingCycleForm(request.POST)

        if form.is_valid():
            date = form.cleaned_data["date"]

            try:
                # ✅ Ensure farm entry exists
                if not FarmDailyEntryItem.objects.filter(farm_entry__date=date).exists():
                    raise ValidationError("No farm entry found for this date.")

                has_data = False

                with transaction.atomic():

                    washing = WashingCycle.objects.create(date=date)

                    for bottle in bottle_types:

                        farm_item = FarmDailyEntryItem.objects.filter(
                            farm_entry__date=date,
                            bottle_type=bottle
                        ).first()

                        empty_sent = farm_item.empty_received_from_warehouse if farm_item else 0

                        # ✅ Safe parsing
                        try:
                            ready = int(request.POST.get(f"ready_{bottle.id}") or 0)
                            breakage = int(request.POST.get(f"breakage_{bottle.id}") or 0)
                        except ValueError:
                            raise ValidationError(f"{bottle.name}: Invalid number")

                        # ✅ Validation 1: No negatives
                        if ready < 0 or breakage < 0:
                            raise ValidationError(f"{bottle.name}: Negative values not allowed")

                        # ✅ Validation 2: Total must match
                        if (ready + breakage) != empty_sent:
                            raise ValidationError(
                                f"{bottle.name}: Ready + Breakage must equal {empty_sent}"
                            )

                        if ready > 0 or breakage > 0:
                            has_data = True

                        WashingCycleItem.objects.create(
                            washing=washing,
                            bottle_type=bottle,
                            empty_sent_to_wash=empty_sent,
                            ready_after_wash=ready,
                            washing_breakage=breakage
                        )

                # 🔴 Prevent empty submission
                if not has_data:
                    raise ValidationError("Please enter at least one value")

                messages.success(request, "Washing cycle saved successfully.")
                return redirect("bottles:washing_cycle")

            except ValidationError as e:
                messages.error(request, str(e))

            except Exception:
                messages.error(request, "Something went wrong")

    else:
        form = WashingCycleForm()

    # ✅ Show today's farm data
    farm_data = {}
    today = timezone.localdate()

    for bottle in bottle_types:
        item = FarmDailyEntryItem.objects.filter(
            farm_entry__date=today,
            bottle_type=bottle
        ).first()

        farm_data[bottle.id] = item.empty_received_from_warehouse if item else 0

    return render(request, "bottles/washing_cycle.html", {
        "form": form,
        "bottle_types": bottle_types,
        "farm_data": farm_data
    })
    
    
    
    
    
    
    
    
# =================================================
# IMPORTS (CLEANED)
# =================================================

from django.template.loader import get_template
# from xhtml2pdf import pisa
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.core.exceptions import PermissionDenied
from django.db.models import Sum



from .decorators import role_required
from .models import DeliveryEntryItem
from accounts.models import CustomUser
from .reports import get_delivery_performance


# =================================================
# REPORT EXPORTS (PDF / EXCEL)
# =================================================
@login_required
@role_required("ADMIN")
def export_report_pdf(request):

    month = request.GET.get('month')
    report = get_delivery_performance(month)
    report = sorted(report, key=lambda x: x['score'], reverse=True)

    template = get_template("reports/main_report_pdf.html")
    html = template.render({"report": report, "month": month})

    # ❌ Disabled PDF generation (xhtml2pdf removed)
    return HttpResponse("PDF generation temporarily disabled")


@login_required
@role_required("ADMIN")
def export_report_excel(request):

    month = request.GET.get('month')
    report = get_delivery_performance(month)
    report = sorted(report, key=lambda x: x['score'], reverse=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Delivery Report"

    ws.append(["#", "User", "Delivered", "Collected", "Breakage", "Score"])

    for idx, item in enumerate(report, start=1):
        ws.append([
            idx,
            item['user'].username,
            item['delivered'],
            item['collected'],
            item['breakage'],
            item['score'],
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=delivery_report.xlsx'

    wb.save(response)
    return response


# =================================================
# INDIVIDUAL USER REPORT
# =================================================

@login_required
def delivery_user_report(request, user_id):

    user = get_object_or_404(CustomUser, id=user_id)

    # 🔒 SECURITY
    if request.user.role != "ADMIN" and request.user != user:
        raise PermissionDenied

    items = DeliveryEntryItem.objects.filter(
        entry__submitted_by=user
    ).select_related('entry', 'bottle_type').order_by('-entry__assignment__date')

    delivered = items.aggregate(total=Sum('delivered'))['total'] or 0
    collected = items.aggregate(total=Sum('collected'))['total'] or 0
    breakage = items.aggregate(total=Sum('breakage'))['total'] or 0

    score = delivered - breakage

    if score >= 100:
        badge = "Excellent"
    elif score >= 50:
        badge = "Average"
    else:
        badge = "Needs Attention"

    return render(request, 'reports/user_report.html', {
        'user': user,
        'delivered': delivered,
        'collected': collected,
        'breakage': breakage,
        'score': score,
        'items': items,
        'labels': ['Delivered', 'Collected', 'Breakage'],
        'values': [delivered, collected, breakage],
        'badge': badge,
    })


# =================================================
# USER EXPORTS
# =================================================

@login_required
def export_user_excel(request, user_id):

    user = get_object_or_404(CustomUser, id=user_id)

    if request.user.role != "ADMIN" and request.user != user:
        raise PermissionDenied

    items = DeliveryEntryItem.objects.filter(
        entry__submitted_by=user
    ).select_related('entry', 'bottle_type')

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"{user.username} Report"

    sheet.append(["Date", "Bottle Type", "Delivered", "Collected", "Breakage"])

    for item in items:
        sheet.append([
            str(item.entry.assignment.date),
            item.bottle_type.name,
            item.delivered,
            item.collected,
            item.breakage
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={user.username}_report.xlsx'

    workbook.save(response)
    return response


@login_required
def export_user_pdf(request, user_id):

    user = get_object_or_404(CustomUser, id=user_id)

    if request.user.role != "ADMIN" and request.user != user:
        raise PermissionDenied

    items = DeliveryEntryItem.objects.filter(
        entry__submitted_by=user
    ).select_related('entry', 'bottle_type')

    delivered = items.aggregate(total=Sum('delivered'))['total'] or 0
    collected = items.aggregate(total=Sum('collected'))['total'] or 0
    breakage = items.aggregate(total=Sum('breakage'))['total'] or 0

    score = delivered - breakage

    if score >= 100:
        badge = "Excellent"
    elif score >= 50:
        badge = "Average"
    else:
        badge = "Needs Attention"

    template = get_template("reports/user_report_pdf.html")
    html = template.render({
        "user": user,
        "items": items,
        "delivered": delivered,
        "collected": collected,
        "breakage": breakage,
        "score": score,
        "badge": badge,
    })

    # ❌ Disabled PDF generation (xhtml2pdf removed)
    return HttpResponse("PDF generation temporarily disabled")







