# -*- coding: utf-8 -*-
"""Threaded backend job helpers for future Windows/PySide6 UI.

v62 / Этап 021 keeps this import-safe module as the thin UI integration layer and adds richer snapshot counters for polished progress/log UI.
It does not change the processing pipeline and does not import heavy ML
packages at module import time.  A GUI can use BackendJob to run the existing
backend in a worker thread, poll snapshots, drain progress events and capture
tracebacks in a structured way.

Cancellation is intentionally soft at this stage: request_cancel() records the
UI request and exposes it in snapshots, but the current pipeline does not yet
have cooperative cancellation checkpoints.  A future UI may still terminate its
own worker process externally if hard cancellation is required.
"""
from __future__ import annotations

import datetime as dt
import threading
import time
import traceback as traceback_module
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import ProgressCallbacks, RunConfig, RunResult
from .api import CallbackEvent
from .constants import SCRIPT_VERSION

BackendRunner = Callable[[RunConfig, ProgressCallbacks], RunResult]


@dataclass(frozen=True)
class BackendJobSnapshot:
    """Serializable snapshot of one backend job for UI polling."""

    job_id: str
    version: str
    state: str
    created_at: str
    started_at: str = ""
    finished_at: str = ""
    duration_ms: Optional[int] = None
    cancel_requested: bool = False
    current_stage: str = ""
    last_message: str = ""
    progress_done: Optional[int] = None
    progress_total: Optional[int] = None
    progress_ratio: Optional[float] = None
    result_status: str = ""
    output_dir: Optional[Path] = None
    db_path: Optional[Path] = None
    bug_report_path: Optional[Path] = None
    stages_completed: Tuple[str, ...] = ()
    error: str = ""
    traceback: str = ""
    events_pending: int = 0
    events_total: int = 0
    warnings_count: int = 0
    errors_count: int = 0
    last_event_kind: str = ""
    last_event_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ("output_dir", "db_path", "bug_report_path"):
            value = data.get(key)
            data[key] = str(value) if value else None
        return data


class _JobProgressCallbacks(ProgressCallbacks):
    """Progress adapter that updates BackendJob state and delegates safely."""

    handles_console_output = True

    def __init__(self, job: "BackendJob", external: Optional[ProgressCallbacks] = None) -> None:
        self._job = job
        self._external = external

    def _delegate(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        if self._external is None:
            return
        method = getattr(self._external, method_name, None)
        if method is None:
            return
        try:
            method(*args, **kwargs)
        except Exception as exc:  # GUI callback bugs should not kill backend processing.
            stage = str(args[0]) if args else "callback"
            self._job._append_event(
                CallbackEvent(
                    kind="callback_error",
                    stage=stage,
                    message=f"{type(exc).__name__}: {exc}",
                    data={"method": method_name},
                )
            )

    def on_stage(self, stage: str, message: str = "", **data: Any) -> None:
        event = CallbackEvent("stage", stage, message, data=dict(data))
        self._job._record_progress_event(event, current_stage=stage, last_message=message)
        self._delegate("on_stage", stage, message, **data)

    def on_progress(self, stage: str, done: int, total: Optional[int] = None, **data: Any) -> None:
        event = CallbackEvent("progress", stage, "", done=done, total=total, data=dict(data))
        self._job._record_progress_event(
            event,
            current_stage=stage,
            progress_done=done,
            progress_total=total,
        )
        self._delegate("on_progress", stage, done, total, **data)

    def on_warning(self, stage: str, message: str, **data: Any) -> None:
        event = CallbackEvent("warning", stage, message, data=dict(data))
        self._job._record_progress_event(event, current_stage=stage, last_message=message)
        self._delegate("on_warning", stage, message, **data)

    def on_error(self, stage: str, message: str, **data: Any) -> None:
        event = CallbackEvent("error", stage, message, data=dict(data))
        self._job._record_progress_event(event, current_stage=stage, last_message=message)
        self._delegate("on_error", stage, message, **data)

    def on_info(self, stage: str, message: str, **data: Any) -> None:
        event = CallbackEvent("info", stage, message, data=dict(data))
        self._job._record_progress_event(event, current_stage=stage, last_message=message)
        self._delegate("on_info", stage, message, **data)


def _default_runner(config: RunConfig, callbacks: ProgressCallbacks) -> RunResult:
    """Load the real pipeline lazily only when the job is actually executed."""
    from .pipeline import run_pipeline

    return run_pipeline(config, callbacks)


class BackendJob:
    """Small thread-backed job controller for GUI integrations.

    The class is deliberately lightweight.  It owns exactly one run attempt and
    captures state, progress events, result metadata and exceptions.  It is safe
    to import from a GUI process before ML dependencies are initialized.
    """

    def __init__(
        self,
        config: RunConfig,
        callbacks: Optional[ProgressCallbacks] = None,
        *,
        runner: Optional[BackendRunner] = None,
        job_id: Optional[str] = None,
    ) -> None:
        self.config = config
        self.external_callbacks = callbacks
        self.runner = runner or _default_runner
        self.job_id = job_id or uuid.uuid4().hex[:12]
        self.created_at = dt.datetime.now().isoformat(timespec="seconds")
        self._created_perf = time.perf_counter()
        self._started_perf: Optional[float] = None
        self._finished_perf: Optional[float] = None
        self._started_at = ""
        self._finished_at = ""
        self._state = "pending"
        self._cancel_requested = False
        self._current_stage = ""
        self._last_message = ""
        self._progress_done: Optional[int] = None
        self._progress_total: Optional[int] = None
        self._result: Optional[RunResult] = None
        self._error = ""
        self._traceback = ""
        self._events: List[CallbackEvent] = []
        self._event_counts: Dict[str, int] = {}
        self._events_total = 0
        self._last_event_kind = ""
        self._last_event_at = ""
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

    @property
    def state(self) -> str:
        return self.snapshot().state

    @property
    def cancel_requested(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def start(self) -> "BackendJob":
        """Start the job in a daemon thread and return self."""
        with self._lock:
            if self._thread is not None or self._state != "pending":
                raise RuntimeError(f"BackendJob {self.job_id} is already started or finished: {self._state}")
            self._thread = threading.Thread(target=self._run_target, name=f"face-sorter-job-{self.job_id}", daemon=True)
            self._state = "starting"
            self._thread.start()
        return self

    def run_sync(self) -> BackendJobSnapshot:
        """Run the job in the current thread and return the final snapshot."""
        with self._lock:
            if self._thread is not None or self._state != "pending":
                raise RuntimeError(f"BackendJob {self.job_id} is already started or finished: {self._state}")
            self._state = "starting"
        self._run_target()
        return self.snapshot()

    def join(self, timeout: Optional[float] = None) -> BackendJobSnapshot:
        """Wait for the background thread and return the current snapshot."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return self.snapshot()

    def is_alive(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def request_cancel(self, reason: str = "") -> BackendJobSnapshot:
        """Record a soft cancellation request.

        v62 / Этап 021 does not interrupt the existing pipeline.  This method is
        still useful for a UI because it records intent and allows a future
        cooperative-cancel implementation to keep the same public API.
        """
        with self._lock:
            self._cancel_requested = True
            if self._state in {"pending", "starting", "running"}:
                self._state = "cancel_requested"
            self._last_message = reason or self._last_message
            event = CallbackEvent(
                kind="cancel_requested",
                stage=self._current_stage or "job",
                message=reason,
                data={"hard_cancel_supported": False},
            )
            self._events.append(event)
            self._note_event_locked(event)
        return self.snapshot()

    def result(self) -> Optional[RunResult]:
        with self._lock:
            return self._result

    def drain_events(self) -> List[CallbackEvent]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
            return events

    def snapshot(self) -> BackendJobSnapshot:
        with self._lock:
            duration_ms: Optional[int] = None
            if self._started_perf is not None:
                end = self._finished_perf if self._finished_perf is not None else time.perf_counter()
                duration_ms = int((end - self._started_perf) * 1000)
            ratio: Optional[float] = None
            if self._progress_total and self._progress_total > 0 and self._progress_done is not None:
                ratio = max(0.0, min(1.0, float(self._progress_done) / float(self._progress_total)))
            result = self._result
            return BackendJobSnapshot(
                job_id=self.job_id,
                version=SCRIPT_VERSION,
                state=self._state,
                created_at=self.created_at,
                started_at=self._started_at,
                finished_at=self._finished_at,
                duration_ms=duration_ms,
                cancel_requested=self._cancel_requested,
                current_stage=self._current_stage,
                last_message=self._last_message,
                progress_done=self._progress_done,
                progress_total=self._progress_total,
                progress_ratio=ratio,
                result_status=result.status if result else "",
                output_dir=result.output_dir if result else None,
                db_path=result.db_path if result else None,
                bug_report_path=result.bug_report_path if result else None,
                stages_completed=result.stages_completed if result else (),
                error=self._error,
                traceback=self._traceback,
                events_pending=len(self._events),
                events_total=self._events_total,
                warnings_count=self._event_counts.get("warning", 0),
                errors_count=sum(self._event_counts.get(kind, 0) for kind in ("error", "callback_error", "job_error")),
                last_event_kind=self._last_event_kind,
                last_event_at=self._last_event_at,
            )

    def _note_event_locked(self, event: CallbackEvent) -> None:
        kind = str(getattr(event, "kind", "event") or "event")
        self._events_total += 1
        self._event_counts[kind] = self._event_counts.get(kind, 0) + 1
        self._last_event_kind = kind
        self._last_event_at = dt.datetime.now().isoformat(timespec="seconds")

    def _append_event(self, event: CallbackEvent) -> None:
        with self._lock:
            self._events.append(event)
            self._note_event_locked(event)

    def _record_progress_event(self, event: CallbackEvent, **state_updates: Any) -> None:
        with self._lock:
            self._events.append(event)
            self._note_event_locked(event)
            for key, value in state_updates.items():
                setattr(self, f"_{key}", value)

    def _run_target(self) -> None:
        callbacks = _JobProgressCallbacks(self, self.external_callbacks)
        with self._lock:
            self._state = "running"
            self._started_at = dt.datetime.now().isoformat(timespec="seconds")
            self._started_perf = time.perf_counter()
            event = CallbackEvent("job_start", "job", "Backend job started.")
            self._events.append(event)
            self._note_event_locked(event)
        try:
            result = self.runner(self.config, callbacks)
            with self._lock:
                self._result = result
                self._state = "done"
                self._finished_at = dt.datetime.now().isoformat(timespec="seconds")
                self._finished_perf = time.perf_counter()
                event = CallbackEvent(
                    "job_done",
                    "job",
                    "Backend job finished.",
                    data={"status": result.status, "stages_completed": list(result.stages_completed)},
                )
                self._events.append(event)
                self._note_event_locked(event)
        except Exception as exc:
            tb = "".join(traceback_module.format_exception(type(exc), exc, exc.__traceback__))
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"
                self._traceback = tb
                self._state = "error"
                self._finished_at = dt.datetime.now().isoformat(timespec="seconds")
                self._finished_perf = time.perf_counter()
                event = CallbackEvent("job_error", "job", self._error, data={"traceback": tb[-12000:]})
                self._events.append(event)
                self._note_event_locked(event)


def create_backend_job(
    config: RunConfig,
    callbacks: Optional[ProgressCallbacks] = None,
    *,
    runner: Optional[BackendRunner] = None,
    autostart: bool = False,
) -> BackendJob:
    """Create a backend job object for UI code."""
    job = BackendJob(config, callbacks=callbacks, runner=runner)
    if autostart:
        job.start()
    return job


def run_backend_job_sync(
    config: RunConfig,
    callbacks: Optional[ProgressCallbacks] = None,
    *,
    runner: Optional[BackendRunner] = None,
) -> BackendJobSnapshot:
    """Run one backend job synchronously and return a structured snapshot."""
    return BackendJob(config, callbacks=callbacks, runner=runner).run_sync()


__all__ = [
    "BackendRunner",
    "BackendJobSnapshot",
    "BackendJob",
    "create_backend_job",
    "run_backend_job_sync",
]
