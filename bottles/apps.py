from django.apps import AppConfig

class BottlesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bottles'

    def ready(self):
        from django.db.utils import OperationalError, ProgrammingError

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            

        except (OperationalError, ProgrammingError):
            # DB not ready yet (migrations not run)
            pass