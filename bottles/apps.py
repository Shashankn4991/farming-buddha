from django.apps import AppConfig


class BottlesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bottles'

    def ready(self):
        from django.db.utils import OperationalError, ProgrammingError

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # Reset password for shashank
            user = User.objects.get(username='shashankn')
            user.set_password('1234')
            user.is_staff = True
            user.is_superuser = True
            user.save()

            print("✅ Password reset for shashank")

        except User.DoesNotExist:
            print("❌ User not found")

        except (OperationalError, ProgrammingError):
            # DB not ready yet
            pass