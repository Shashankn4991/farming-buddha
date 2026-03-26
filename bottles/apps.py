from django.apps import AppConfig


class BottlesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bottles'

    def ready(self):
        from django.db.utils import OperationalError, ProgrammingError

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            if not User.objects.filter(username='shashankn').exists():
                User.objects.create_superuser(
                    username='shashankn',
                    email='admin@example.com',
                    password='1234'
                )
                print("✅ Superuser CREATED: shashankn")

            else:
                user = User.objects.get(username='shashankn')
                user.set_password('1234')
                user.is_staff = True
                user.is_superuser = True
                user.save()
                print("✅ Password reset for shashankn")

        except (OperationalError, ProgrammingError):
            pass