from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.db.utils import OperationalError, ProgrammingError
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            if not User.objects.filter(username='shashankn').exists():
                User.objects.create_superuser(
                    username='shashankn',
                    email='admin@example.com',
                    password='admin123'
                )
                print("✅ Superuser created")

        except (OperationalError, ProgrammingError):
            pass