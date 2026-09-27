from __future__ import annotations
import json, time
from ..core.settings import settings

class JobQueue:
    def __init__(self):
        self.enabled=bool(settings.redis_url)
        self.client=None
        if self.enabled:
            try:
                import redis
                self.client=redis.Redis.from_url(settings.redis_url, decode_responses=True)
                self.client.ping()
            except Exception:
                self.client=None
                self.enabled=False
    def enqueue(self, kind:str, run_id:str):
        if not self.client: return False
        self.client.rpush(settings.job_queue_name, json.dumps({"kind":kind,"run_id":run_id,"enqueued_at":time.time()})); return True
    def pop(self, timeout=5):
        if not self.client: return None
        item=self.client.blpop(settings.job_queue_name, timeout=timeout)
        return json.loads(item[1]) if item else None
queue=JobQueue()
