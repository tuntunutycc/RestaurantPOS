"""Per-printer print queue.

Thermal LAN printers drop or merge tickets when several slips arrive at once.
Each printer target therefore gets its own ``asyncio.Queue`` and one worker
that sends a single slip, waits ``PRINT_QUEUE_DELAY_SECONDS``, then takes the
next. Different printers work in parallel, so a cashier receipt never waits
behind kitchen tickets.

The queue is in memory. What survives a restart is the ``print_jobs`` table
(see ``print_jobs.py``).
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DELAY_SECONDS = 1.0

Work = Callable[[], Awaitable[Any]]


def delay_from_env() -> float:
    raw = (os.getenv("PRINT_QUEUE_DELAY_SECONDS") or "").strip()
    if not raw:
        return DEFAULT_DELAY_SECONDS
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "PRINT_QUEUE_DELAY_SECONDS=%r is not a number; using %s",
            raw,
            DEFAULT_DELAY_SECONDS,
        )
        return DEFAULT_DELAY_SECONDS
    return max(value, 0.0)


# One key per physical printer. Jobs and Print Test must build keys the same
# way so they share a queue.
def lan_key(host: str, port: int) -> str:
    return f"lan:{(host or '').strip().lower()}:{int(port)}"


def windows_key(queue_name: str) -> str:
    return f"windows:{(queue_name or '').strip().lower()}"


def file_key(route: str) -> str:
    return f"file:{(route or '').strip().lower()}"


def unresolved_key(route: str) -> str:
    """No usable target; the send will fail and record why."""
    return f"unresolved:{(route or '').strip().lower()}"


class PrintQueue:
    def __init__(self, *, delay_seconds: float | None = None) -> None:
        self._delay_override = delay_seconds
        self.delay_seconds = (
            delay_seconds if delay_seconds is not None else DEFAULT_DELAY_SECONDS
        )
        self._queues: dict[str, asyncio.Queue] = {}
        self._workers: dict[str, asyncio.Task] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def running(self) -> bool:
        """True only on the event loop the queue was started on."""
        if self._loop is None:
            return False
        try:
            return asyncio.get_running_loop() is self._loop
        except RuntimeError:
            return False

    async def start(self) -> None:
        if self._loop is not None:
            await self.stop()
        if self._delay_override is None:
            self.delay_seconds = delay_from_env()
        self._loop = asyncio.get_running_loop()
        logger.info("Print queue started delay_seconds=%s", self.delay_seconds)

    async def stop(self) -> None:
        workers = list(self._workers.values())
        for task in workers:
            task.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        # Nobody may wait forever on a slip that will never be sent.
        for queue in self._queues.values():
            while not queue.empty():
                _work, future = queue.get_nowait()
                if future is not None and not future.done():
                    future.cancel()
        self._workers.clear()
        self._queues.clear()
        self._loop = None

    def submit(self, key: str, work: Work) -> None:
        """Queue ``work`` for the printer ``key`` and return at once."""
        if not self.running:
            raise RuntimeError("Print queue is not running")
        self._put(key, work, None)

    async def run(self, key: str, work: Work) -> Any:
        """Queue ``work`` behind that printer's other slips and wait for its result.

        Runs it directly when the queue is not started, so nothing is dropped.
        """
        if not self.running:
            return await work()
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._put(key, work, future)
        return await future

    async def join(self) -> None:
        """Wait until every queued slip has been processed."""
        queues = list(self._queues.values())
        if queues:
            await asyncio.gather(*(queue.join() for queue in queues))

    def pending_count(self) -> int:
        return sum(queue.qsize() for queue in self._queues.values())

    def _put(self, key: str, work: Work, future: asyncio.Future | None) -> None:
        queue = self._queues.get(key)
        if queue is None:
            queue = asyncio.Queue()
            self._queues[key] = queue
        worker = self._workers.get(key)
        if worker is None or worker.done():
            self._workers[key] = asyncio.create_task(
                self._worker(key, queue), name=f"print-queue:{key}"
            )
        queue.put_nowait((work, future))

    async def _worker(self, key: str, queue: asyncio.Queue) -> None:
        while True:
            work, future = await queue.get()
            try:
                if future is not None and future.cancelled():
                    continue  # caller gave up before its turn
                try:
                    result = await work()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if future is not None and not future.done():
                        future.set_exception(exc)
                    else:
                        logger.exception("Print queue work failed key=%s", key)
                else:
                    if future is not None and not future.done():
                        future.set_result(result)
            finally:
                queue.task_done()
            # Pause before the next slip for this printer so its buffer drains.
            if self.delay_seconds > 0:
                await asyncio.sleep(self.delay_seconds)


_print_queue = PrintQueue()


def get_print_queue() -> PrintQueue:
    return _print_queue
