"""Thread-safe notifications for exposure-affecting state changes."""

from collections.abc import Callable
from dataclasses import dataclass
import threading

from src.utils.logger import get_logger

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ExposureChange:
    source: str
    action: str
    name: str | None = None


ChangeCallback = Callable[[ExposureChange], None]


class ChangeNotifier:
    """Publish immutable change events to an isolated callback snapshot."""

    def __init__(self, source: str) -> None:
        self._source = source
        self._callbacks: dict[int, ChangeCallback] = {}
        self._next_token = 1
        self._lock = threading.Lock()

    def subscribe(self, callback: ChangeCallback) -> int:
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._callbacks[token] = callback
            return token

    def unsubscribe(self, token: int) -> None:
        with self._lock:
            self._callbacks.pop(token, None)

    def notify(self, *, action: str, name: str | None = None) -> None:
        event = ExposureChange(source=self._source, action=action, name=name)
        with self._lock:
            callbacks = tuple(self._callbacks.values())

        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                _logger.exception("Exposure change callback failed")
