from django.urls import path
from . import views

# ✅ REQUIRED for namespace
app_name = 'bottles'

urlpatterns = [

    # -----------------
    # Main Dashboard
    # -----------------
    path('reports/', views.reports_dashboard, name='reports_dashboard'),


    # -----------------
    # Role Forms
    # -----------------
    path("farm-entry/", views.farm_entry_view, name="farm_entry"),
    path("warehouse-entry/", views.warehouse_entry_view, name="warehouse_entry"),
    path("delivery-entry/", views.delivery_entry, name="delivery_entry"),
    path("van-entry/", views.van_entry_view, name="van_entry"),

    # -----------------
    # Delivery Management
    # -----------------
    path("delivery/create/", views.delivery_entry, name="delivery_create"),
    path("delivery-list/", views.delivery_list, name="delivery_list"),

    # -----------------
    # Supervisor
    # -----------------
    path("assign-delivery/", views.assign_delivery_view, name="assign_delivery"),
    path("supervisor/", views.supervisor_panel, name="supervisor_panel"),
    path("supervisor/approve/<int:pk>/", views.approve_entry, name="approve_entry"),
    path("supervisor/reject/<int:pk>/", views.reject_entry, name="reject_entry"),

    # -----------------
    # Admin Controls
    # -----------------
    path("close-day/", views.admin_close_day, name="admin_close_day"),
    path("reopen-day/", views.admin_reopen_day, name="admin_reopen_day"),

    # -----------------
    # Alerts
    # -----------------
    path("alerts/history/", views.alert_history, name="alert_history"),

    # -----------------
    # Washing
    # -----------------
    path("washing-cycle/", views.washing_cycle_view, name="washing_cycle"),

    # -----------------
    # Reports
    # -----------------
    #Spath('reports/', views.reports_dashboard, name='reports_dashboard'),

    path('reports/pdf/', views.export_report_pdf, name='export_report_pdf'),
    path('reports/excel/', views.export_report_excel, name='export_report_excel'),

    path(
        'reports/user/<int:user_id>/',
        views.delivery_user_report,
        name='delivery_user_report'
    ),

    path(
        'reports/user/<int:user_id>/pdf/',
        views.export_user_pdf,
        name='export_user_pdf'
    ),

    path(
        'reports/user/<int:user_id>/excel/',
        views.export_user_excel,
        name='export_user_excel'
    ),
]