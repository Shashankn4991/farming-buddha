from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('accounts.urls')),
    
    path('dashboard/', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('bottles/', include(('bottles.urls', 'bottles'), namespace='bottles')),
]