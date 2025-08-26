import logging
import logging.handlers
import json
import os
import time
import uuid
from contextlib import contextmanager


class JSONFormatter(logging.Formatter):
    """Format logs as single-line JSON objects. Good for ingestion by Grafana/Loki.

    The formatter keeps a small set of core fields and includes any extra fields
    attached to the LogRecord via the ``extra`` parameter.
    """

    def format(self, record: logging.LogRecord) -> str:
        # base payload
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # attach any extra attributes passed via the extra= dict
        skip = set(
            [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            ]
        )

        for k, v in record.__dict__.items():
            if k in skip:
                continue
            # only non-callable and JSON-serializable values should be attached
            try:
                json.dumps({k: v})
                payload[k] = v
            except Exception:
                # fallback to string representation
                try:
                    payload[k] = str(v)
                except Exception:
                    payload[k] = "<unserializable>"

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def get_logger(
    name: str = "app",
    logfile: str = "logs/app.jsonl",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
):
    """Return a configured logger instance.

    Creates the logs directory if necessary, attaches a rotating file handler
    using JSON lines and a simple console handler for local debugging.
    Repeated calls for the same logger name will return the same configured logger.
    """

    logger = logging.getLogger(name)
    if getattr(logger, "_app_logger_configured", False):
        return logger

    logger.setLevel(level)

    # ensure directory exists
    logdir = os.path.dirname(logfile) or "."
    os.makedirs(logdir, exist_ok=True)

    fh = logging.handlers.RotatingFileHandler(
        logfile, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    fh.setFormatter(JSONFormatter())
    fh.setLevel(level)
    logger.addHandler(fh)

    # keep a console handler for convenience during development
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    ch.setLevel(level)
    logger.addHandler(ch)

    # mark configured so subsequent get_logger calls are idempotent
    setattr(logger, "_app_logger_configured", True)
    return logger


@contextmanager
def log_duration(logger: logging.Logger, operation: str, level: int = logging.INFO, **extra):
    """Context manager that measures execution time and emits a structured log entry.

    Usage:
        with log_duration(logger, "process_frame", frame_id=42):
            do_work()
    """
    start = time.time()
    trace_id = str(uuid.uuid4())
    success = False
    try:
        yield
        success = True
    except Exception:
        success = False
        raise
    finally:
        duration_ms = int((time.time() - start) * 1000)
        try:
            logger.log(
                level,
                f"{operation} finished",
                extra={
                    "operation": operation,
                    "duration_ms": duration_ms,
                    "success": success,
                    "trace_id": trace_id,
                    **extra,
                },
            )
        except Exception:
            # logging must not break the app
            pass
