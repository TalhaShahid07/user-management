import os
from celery import Celery, shared_task
from django.conf import settings
# ---------------------------------------------------------------------
#
#
# ---------------------------------------------------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "event_management.settings")

app = Celery("event_management")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Set the time zone explicitly
app.conf.timezone = "US/Eastern"

app.autodiscover_tasks()

# Create an alias for shared_task named celery_task
celery_task = shared_task


@celery_task(bind=True)
def debug_task(self):
    print("Request: {0!r}".format(self.request))
