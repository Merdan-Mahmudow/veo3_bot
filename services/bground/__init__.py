from celery import Celery
from config import ENV


class CeleryManager:
    def __init__(self):
        self.env = ENV()
        self.celery_app = Celery(
            "veo3_bot",
            broker=self.env.CELERY_BROKER_URL,
            backend=self.env.CELERY_RESULT_BACKEND,
            include=["tasks.veo", "tasks.prompt"]
        )

        self.celery_app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            timezone=self.env.CELERY_TIMEZONE,
            worker_prefetch_multiplier=1,   
            task_acks_late=True,            
            broker_transport_options={"visibility_timeout": 3600},
        )