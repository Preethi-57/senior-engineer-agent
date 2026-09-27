import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from .security import redact_secrets

class AuditLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def event(self, event: str, **data):
        payload = {"ts": datetime.now(timezone.utc).isoformat(), "event": event,
                   **{k: redact_secrets(str(v)) for k,v in data.items()}}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

logger = logging.getLogger("ai_sre")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
