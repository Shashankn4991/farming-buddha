from django.db.models import Sum
from accounts.models import CustomUser
from .models import DeliveryEntryItem


def get_delivery_performance(month=None):
    users = CustomUser.objects.filter(role='DELIVERY')

    report = []

    for user in users:
        items = DeliveryEntryItem.objects.filter(
            entry__submitted_by=user
        )

        # Apply month filter if selected
        if month:
            items = items.filter(
                entry__assignment__date__month=month
            )

        delivered = items.aggregate(
            total=Sum('delivered')
        )['total'] or 0

        collected = items.aggregate(
            total=Sum('collected')
        )['total'] or 0

        breakage = items.aggregate(
            total=Sum('breakage')
        )['total'] or 0

        score = delivered - breakage

        report.append({
            'user': user,
            'delivered': delivered,
            'collected': collected,
            'breakage': breakage,
            'score': score
        })

    return sorted(report, key=lambda x: x['score'], reverse=True)