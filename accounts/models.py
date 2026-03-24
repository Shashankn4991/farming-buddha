from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('SUPERVISOR', 'Supervisor'),
        ('FARM', 'Farm Staff'),
        ('WAREHOUSE', 'Warehouse Staff'),
        ('DELIVERY', 'Delivery Person'),
        ('DRIVER', 'Driver'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    route_name = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"{self.username} - {self.role}"