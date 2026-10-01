"""Install a JSON log formatter on the root logger.

Every log record becomes a single JSON line on stdout. Custom fields passed
via `logger.info("...", extra={...})` are merged into the JSON object.

uvicorn access logs are disabled — our request middleware emits the
canonical per-request line instead.
"""
import json
import logging
import sys
from datetime import datetime, timezone

# Attributes that always exist on a LogRecord. Anything else in __dict__
# was added via `extra={...}` and should be merged into the JSON payload.
_LOG_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "message",
    "asctime", "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k in _LOG_RECORD_ATTRS or k.startswith("_"):
                continue
            payload[k] = v
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
    root.addHandler(handler)

    # Our middleware emits the canonical request log — silence uvicorn's.
    logging.getLogger("uvicorn.access").disabled = True