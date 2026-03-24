from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from bottles.decorators import role_required
from django.utils import timezone

from bottles.services import (
    get_stock_summary,
    get_route_outstanding,
    get_today_process_summary,
    get_bottle_return_delays,
    get_live_bottle_flow,
)

from bottles.models import AlertHistory


@login_required
@role_required("ADMIN")
def dashboard_home(request):

    # 🔹 Safe defaults
    delayed_bottles = []
    flow_data = {}
    alerts = []
    alert_count = 0
    today_summary = {}
    stock_summary = {}
    route_outstanding = []

    today = timezone.localdate()

    # 🔹 Delayed bottles
    try:
        delayed_bottles = get_bottle_return_delays()
    except Exception:
        pass

    # 🔹 Flow data
    try:
        flow_data = get_live_bottle_flow()
    except Exception:
        pass

    # 🔹 Alerts (today only)
    try:
        alerts = AlertHistory.objects.filter(date=today).order_by('-date')
        alert_count = alerts.count()
    except Exception:
        pass

    # 🔹 Today's Activity
    try:
        today_summary = get_today_process_summary(today)
    except Exception:
        pass

    # 🔹 Stock Summary
    try:
        stock_summary = get_stock_summary()
    except Exception:
        pass

    # 🔹 Route Outstanding
    try:
        route_outstanding = get_route_outstanding()
    except Exception:
        pass

    return render(request, "dashboard/home.html", {
        "delayed_bottles": delayed_bottles,
        "flow_data": flow_data,
        "alerts": alerts,
        "alert_count": alert_count,
        "today_summary": today_summary,
        "stock_summary": stock_summary,
        "route_outstanding": route_outstanding,
    })