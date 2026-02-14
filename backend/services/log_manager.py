"""Log management service.

Provides:
- Rotating log file handler factory for training subprocess logs
- Background task to compress old log files (gzip after N days)
- Log directory size monitoring
"""

from __future__ import annotations

import asyncio
import gzip
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)

# Archive logs older than this many days
LOG_ARCHIVE_DAYS = 7

# Check interval (run once per hour)
ARCHIVE_CHECK_INTERVAL = 3600.0


def get_log_path(run_id: int) -> Path:
    """Get the log file path for a run, creating parent dirs if needed."""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"run_{run_id}.log"


def get_log_dir_stats() -> dict[str, int | float]:
    """Get log directory statistics.

    Returns:
        Dict with total_files, total_size_bytes, archived_files.
    """
    log_dir = Path(settings.LOG_DIR)
    if not log_dir.exists():
        return {"total_files": 0, "total_size_bytes": 0, "archived_files": 0}

    total_files = 0
    total_size = 0
    archived = 0

    for f in log_dir.iterdir():
        if f.is_file():
            total_files += 1
            total_size += f.stat().st_size
            if f.suffix == ".gz":
                archived += 1

    return {
        "total_files": total_files,
        "total_size_bytes": total_size,
        "archived_files": archived,
    }


def compress_log_file(log_path: Path) -> Path | None:
    """Compress a log file with gzip.

    Returns the path to the compressed file, or None on failure.
    """
    if not log_path.exists() or log_path.suffix == ".gz":
        return None

    gz_path = log_path.with_suffix(log_path.suffix + ".gz")
    try:
        with open(log_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        log_path.unlink()
        logger.debug("Compressed %s → %s", log_path.name, gz_path.name)
        return gz_path
    except Exception:
        logger.exception("Failed to compress %s", log_path)
        # Clean up partial gz file
        if gz_path.exists():
            gz_path.unlink()
        return None


def archive_old_logs(days: int = LOG_ARCHIVE_DAYS) -> int:
    """Compress log files older than `days` days.

    Returns the number of files archived.
    """
    log_dir = Path(settings.LOG_DIR)
    if not log_dir.exists():
        return 0

    cutoff = datetime.utcnow() - timedelta(days=days)
    archived = 0

    for f in log_dir.iterdir():
        if f.is_file() and f.suffix == ".log":
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                if compress_log_file(f):
                    archived += 1

    if archived:
        logger.info("Archived %d log files older than %d days", archived, days)

    return archived


class LogArchiveService:
    """Background service that periodically archives old log files."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        """Start the background archive loop."""
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("LogArchiveService started (interval=%ds)", int(ARCHIVE_CHECK_INTERVAL))

    def stop(self) -> None:
        """Stop the background archive loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("LogArchiveService stopped")

    async def _loop(self) -> None:
        """Main loop: periodically archive old logs."""
        while self._running:
            try:
                # Run compression in thread pool to avoid blocking event loop
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, archive_old_logs)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("LogArchiveService error")

            await asyncio.sleep(ARCHIVE_CHECK_INTERVAL)


# Global instance
log_archive_service = LogArchiveService()
