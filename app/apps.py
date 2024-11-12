from django.apps import AppConfig

class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
        # Import the template tags when the app is ready
        from django.template.defaulttags import register
        from .templatetags import table_filters
