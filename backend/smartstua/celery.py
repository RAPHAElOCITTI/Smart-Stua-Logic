"""
Celery application configuration for Smart-Stua.
Redis broker for async task processing (alert dispatch, ARI computation).
"""

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartstua.settings')

app = Celery('smartstua')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
