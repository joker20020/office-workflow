import dataclasses
import threading

import pytest

from src.core.change_notifier import ChangeNotifier, ExposureChange


def test_notify_uses_snapshot_and_immutable_event():
    notifier = ChangeNotifier("skills")
    received = []

    def unsubscribe_second(event):
        received.append(event)
        notifier.unsubscribe(second_token)

    notifier.subscribe(unsubscribe_second)
    second_token = notifier.subscribe(received.append)

    notifier.notify(action="added", name="writer")

    assert received == [
        ExposureChange("skills", "added", "writer"),
        ExposureChange("skills", "added", "writer"),
    ]
    with pytest.raises(dataclasses.FrozenInstanceError):
        received[0].action = "deleted"


def test_tokens_are_unique_positive_and_unsubscribe_is_idempotent():
    notifier = ChangeNotifier("mcp")
    first = notifier.subscribe(lambda event: None)
    second = notifier.subscribe(lambda event: None)

    assert first > 0
    assert second > 0
    assert first != second
    notifier.unsubscribe(first)
    notifier.unsubscribe(first)


def test_callback_failure_is_logged_and_isolated(monkeypatch):
    notifier = ChangeNotifier("permissions")
    received = []
    exception = RuntimeError("listener boom")
    logged = []

    def fail(event):
        raise exception

    monkeypatch.setattr(
        "src.core.change_notifier._logger.exception",
        lambda message, *args: logged.append((message, args)),
    )
    notifier.subscribe(fail)
    notifier.subscribe(received.append)

    notifier.notify(action="granted", name="plugin")

    assert received == [ExposureChange("permissions", "granted", "plugin")]
    assert len(logged) == 1
    assert "callback" in logged[0][0].lower()


def test_callbacks_may_subscribe_and_unsubscribe_during_notification():
    notifier = ChangeNotifier("mcp")
    received = []
    late_token = None

    def late(event):
        received.append(("late", event.action))

    def first(event):
        nonlocal late_token
        received.append(("first", event.action))
        notifier.unsubscribe(first_token)
        late_token = notifier.subscribe(late)

    first_token = notifier.subscribe(first)
    notifier.notify(action="added")
    notifier.notify(action="updated")

    assert received == [("first", "added"), ("late", "updated")]
    notifier.unsubscribe(late_token)


def test_concurrent_subscribe_and_notify_completes_without_deadlock():
    notifier = ChangeNotifier("skills")
    start = threading.Barrier(3)
    errors = []

    def subscribe_many():
        try:
            start.wait()
            for _ in range(250):
                token = notifier.subscribe(lambda event: None)
                notifier.unsubscribe(token)
        except BaseException as exc:
            errors.append(exc)

    def notify_many():
        try:
            start.wait()
            for _ in range(250):
                notifier.notify(action="updated")
        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=subscribe_many),
        threading.Thread(target=notify_many),
    ]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
