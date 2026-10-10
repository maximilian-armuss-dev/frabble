"""Bounded spawn workers; only the coordinator touches manifests and UI.

Each worker has one task and one pipe at a time. Pipes carry cumulative progress
and small completion records, never boards. Explicit process ownership also
allows reliable termination on Python versions without executor termination.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
import multiprocessing as mp
from multiprocessing.connection import Connection, wait
import os
import signal
import time
from typing import Any

from ..generator.config import GeneratorConfig
from ..generator.engine import ScenarioGenerator
from .artifacts import file_sha256

ProgressFactory = Callable[[str, int], AbstractContextManager[Callable[[int], None]]]


@dataclass(frozen=True)
class ScenarioTask:
    scenario_id: str
    config: dict[str, Any]


class ScenarioWorkerError(RuntimeError):
    pass


def resolve_worker_count(workers: int | None, pending: int) -> int:
    if workers is not None and (type(workers) is not int or workers < 1):
        raise ValueError("workers must be a positive integer or None.")
    # CPU-based cap, not a claim about available RAM.
    return min(workers if workers is not None else min(4, os.cpu_count() or 1), pending)


def _worker_main(connection: Connection) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        while (task := connection.recv()) is not None:
            count = 0
            last_sent = time.monotonic()

            def progress(amount: int) -> None:
                nonlocal count, last_sent
                count += amount
                now = time.monotonic()
                if now - last_sent >= 0.1:
                    connection.send(("progress", task.scenario_id, count, None))
                    last_sent = now

            connection.send(("started", task.scenario_id, 0, None))
            try:
                config = GeneratorConfig.model_validate(task.config)
                generator = ScenarioGenerator(config)
                run = generator.generate(progress_callback=progress)
                path = generator.write(run)
                connection.send(("complete", task.scenario_id, count, file_sha256(path)))
            except Exception as exc:
                connection.send((
                    "failed", task.scenario_id, count,
                    f"{type(exc).__name__}: {exc}",
                ))
    except (EOFError, BrokenPipeError):
        pass
    finally:
        connection.close()


@dataclass
class _Worker:
    process: Any
    connection: Connection
    task: ScenarioTask | None = None
    progress: AbstractContextManager | None = None
    update: Callable[[int], None] | None = None
    count: int = 0

    def close_progress(self, error: BaseException | None = None) -> None:
        context, self.progress = self.progress, None
        self.update = None
        if context is not None:
            context.__exit__(type(error) if error else None, error, None)


def run_scenarios(
    tasks: Iterable[ScenarioTask],
    *,
    workers: int,
    completed: Callable[[ScenarioTask, str], None],
    failed: Callable[[ScenarioTask, Exception], None],
    progress_factory: ProgressFactory | None = None,
) -> None:
    context = mp.get_context("spawn")
    pool: list[_Worker] = []
    pending = iter(tasks)
    errors: list[str] = []
    shutdown_error: BaseException | None = None

    def dispatch(worker: _Worker) -> None:
        task = next(pending, None)
        if task is None:
            return
        worker.task = task
        worker.count = 0
        worker.connection.send(task)

    try:
        for _ in range(workers):
            parent, child = context.Pipe()
            process = context.Process(target=_worker_main, args=(child,))
            try:
                process.start()
            except BaseException:
                parent.close()
                raise
            finally:
                child.close()
            worker = _Worker(process, parent)
            pool.append(worker)
            dispatch(worker)

        while any(worker.task is not None for worker in pool):
            ready = wait(
                [worker.connection for worker in pool if worker.task is not None]
                + [worker.process.sentinel for worker in pool],
                timeout=0.1,
            )
            # Drain available events before dispatch, so a known failure stops
            # new work even when another worker completed in the same batch.
            for worker in pool:
                while worker.task is not None and worker.connection in ready:
                    try:
                        kind, scenario_id, count, payload = worker.connection.recv()
                    except EOFError:
                        break
                    task = worker.task
                    if scenario_id != task.scenario_id or count < worker.count:
                        raise ScenarioWorkerError("Invalid scenario worker event.")
                    if kind == "started" and progress_factory is not None:
                        worker.progress = progress_factory(
                            scenario_id, task.config["target_transition_count"]
                        )
                        worker.update = worker.progress.__enter__()
                    if worker.update is not None and count > worker.count:
                        worker.update(count - worker.count)
                    worker.count = count
                    if kind in {"complete", "failed"}:
                        error = None
                        try:
                            if kind == "failed":
                                raise ScenarioWorkerError(f"{scenario_id}: {payload}")
                            if count != task.config["target_transition_count"]:
                                raise ScenarioWorkerError(f"{scenario_id}: incomplete progress")
                            completed(task, payload)
                        except Exception as exc:
                            error = exc
                            errors.append(f"{scenario_id}: {exc}")
                            failed(task, exc)
                        finally:
                            worker.close_progress(error)
                            worker.task = None
                    if not worker.connection.poll():
                        break

            crashed = [worker for worker in pool if worker.process.exitcode is not None]
            if crashed:
                affected = [worker.task.scenario_id for worker in pool if worker.task]
                exits = [worker.process.exitcode for worker in crashed]
                raise ScenarioWorkerError(
                    f"Scenario pool exited unexpectedly (exit codes {exits}); "
                    f"affected scenarios: {', '.join(affected)}"
                )
            if not errors:
                for worker in pool:
                    if worker.task is None:
                        dispatch(worker)
        if errors:
            raise ScenarioWorkerError("Preparation failed: " + "; ".join(errors))
    except BaseException as exc:
        shutdown_error = exc
        for worker in pool:
            if worker.task is not None:
                failed(worker.task, ScenarioWorkerError(
                    f"{worker.task.scenario_id}: {type(exc).__name__}: {exc}"
                ))
        raise
    finally:
        # On success (including drained ordinary failures), all workers are
        # idle. On interrupt/crash, terminate before closing their pipes so no
        # full progress channel can prevent shutdown. Reap every owned child.
        for worker in pool:
            if worker.process.is_alive():
                if worker.task is not None:
                    worker.process.terminate()
                else:
                    try:
                        worker.connection.send(None)
                    except (BrokenPipeError, OSError):
                        worker.process.terminate()
        for worker in pool:
            worker.process.join(timeout=2)
            if worker.process.is_alive():
                worker.process.kill()
                worker.process.join()
            worker.connection.close()
            worker.process.close()
        for worker in pool:
            worker.close_progress(shutdown_error)
