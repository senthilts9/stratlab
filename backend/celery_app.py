# backend/celery_app.py
import os
from celery import Celery

# ------------------------------------------------------------------
# Broker & result backend – tweak the URLs if you already use RabbitMQ
# ------------------------------------------------------------------
BROKER_URL  = os.getenv("CELERY_BROKER_URL",  "redis://redis:6379/0")
RESULT_URL  = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery(
    "stratlab",          # choose any name
    broker  = BROKER_URL,
    backend = RESULT_URL,
)

celery_app.conf.update(
    task_serializer   = "json",
    result_serializer = "json",
    accept_content    = ["json"],
    task_track_started = True,
    result_extended    = True,
)
