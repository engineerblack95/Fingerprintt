from django.apps import AppConfig


class LogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "logs"
    verbose_name = "Entry logs"

    def ready(self):
        # Register the post_save alert hook for every EntryLog creation path.
        from . import signals  # noqa: F401
