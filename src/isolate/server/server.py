from __future__ import annotations

import os
import threading
import time
import traceback
import uuid
from collections import defaultdict
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from queue import Empty as QueueEmpty
from queue import Queue
from typing import Any, Callable, Iterator, cast

import grpc
from grpc import ServicerContext, StatusCode

from isolate.backends import (
    EnvironmentCreationError,
    IsolateSettings,
)
from isolate.backends.common import active_python
from isolate.backends.local import LocalPythonEnvironment
from isolate.backends.virtualenv import VirtualPythonEnvironment
from isolate.connections.grpc import AgentError, LocalPythonGRPC
from isolate.connections.grpc.configuration import get_default_options
from isolate.logger import logger
from isolate.logs import Log, LogLevel, LogSource
from isolate.server import definitions, health
from isolate.server.health_server import HealthServicer
from isolate.server.interface import from_grpc, to_grpc

EMPTY_MESSAGE_INTERVAL = float(os.getenv("ISOLATE_EMPTY_MESSAGE_INTERVAL", "600"))
MAX_GRPC_WAIT_TIMEOUT = float(os.getenv("ISOLATE_MAX_GRPC_WAIT_TIMEOUT", "10.0"))

# Whether to inherit all the packages from the current environment or not.
INHERIT_FROM_LOCAL = os.getenv("ISOLATE_INHERIT_FROM_LOCAL") == "1"

# Number of threads that the gRPC server will use.
MAX_THREADS = int(os.getenv("MAX_THREADS", "5"))
_AGENT_REQUIREMENTS_TXT = os.getenv("AGENT_REQUIREMENTS_TXT")

if _AGENT_REQUIREMENTS_TXT is not None:
    with open(_AGENT_REQUIREMENTS_TXT) as stream:
        AGENT_REQUIREMENTS = stream.read().splitlines()
else:
    AGENT_REQUIREMENTS = []


# Number of seconds to observe the queue before checking the termination
# event.
_Q_WAIT_DELAY = 0.1
RUNNER_THREAD_POOL = futures.ThreadPoolExecutor(max_workers=MAX_THREADS)


class GRPCException(Exception):
    def __init__(self, message: str, code: StatusCode = StatusCode.INVALID_ARGUMENT):
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        return f"{self.code.name}: {self.message}"


@dataclass
class RunnerAgent:
    stub: definitions.AgentStub
    message_queue: Queue
    _bound_context: ExitStack
    _channel_state_history: list[grpc.ChannelConnectivity] = field(default_factory=list)

    def __post_init__(self):
        def switch_state(connectivity_update: grpc.ChannelConnectivity) -> None:
            self._channel_state_history.append(connectivity_update)

        self.channel.subscribe(switch_state)

    @property
    def channel(self) -> grpc.Channel:
        return self.stub._channel  # type: ignore

    @property
    def is_accessible(self) -> bool:
        try:
            last_known_state = self._channel_state_history[-1]
        except IndexError:
            last_known_state = None

        return last_known_state is grpc.ChannelConnectivity.READY

    def check_connectivity(self) -> bool:
        # Check whether the server is ready.
        # TODO: This is more of a hack rather than a guaranteed health check,
        # we might have to introduce the proper protocol to the agents as well
        # to make sure that they are ready to receive requests.
        return self.is_accessible

    def terminate(self) -> None:
        self._bound_context.close()


@dataclass
class BridgeManager:
    _agent_access_lock: threading.Lock = field(default_factory=threading.Lock)
    _agents: dict[tuple[Any, ...], list[RunnerAgent]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _stack: ExitStack = field(default_factory=ExitStack)

    @contextmanager
    def establish(
        self,
        connection: LocalPythonGRPC,
        queue: Queue,
    ) -> Iterator[RunnerAgent]:
        agent = self._allocate_new_agent(connection, queue)

        try:
            yield agent
        finally:
            self._cache_agent(connection, agent)

    def _cache_agent(
        self,
        connection: LocalPythonGRPC,
        agent: RunnerAgent,
    ) -> None:
        with self._agent_access_lock:
            self._agents[self._identify(connection)].append(agent)

    def _allocate_new_agent(
        self,
        connection: LocalPythonGRPC,
        queue: Queue,
    ) -> RunnerAgent:
        with self._agent_access_lock:
            available_agents = self._agents[self._identify(connection)]
            while available_agents:
                agent = available_agents.pop()
                if agent.check_connectivity():
                    return agent
                else:
                    agent.terminate()

        bound_context = ExitStack()
        stub = bound_context.enter_context(
            connection._establish_bridge(max_wait_timeout=MAX_GRPC_WAIT_TIMEOUT)
        )
        return RunnerAgent(stub, queue, bound_context)

    def _identify(self, connection: LocalPythonGRPC) -> tuple[Any, ...]:
        return (
            connection.environment_path,
            *connection.extra_inheritance_paths,
        )

    def __enter__(self) -> BridgeManager:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        for agents in self._agents.values():
            for agent in agents:
                agent.terminate()


@dataclass
class Task:
    request: definitions.BoundFunction
    future: futures.Future | None = None
    agent: RunnerAgent | None = None

    def cancel(self):
        while True:
            self.future.cancel()
            if self.agent:
                self.agent.terminate()
            try:
                self.future.exception(timeout=0.1)
                return
            except futures.TimeoutError:
                pass


@dataclass
class IsolateServicer(definitions.IsolateServicer):
    bridge_manager: BridgeManager
    default_settings: IsolateSettings = field(default_factory=IsolateSettings)
    background_tasks: dict[str, Task] = field(default_factory=dict)

    def _run_task(self, task: Task) -> Iterator[definitions.PartialRunResult]:
        messages: Queue[definitions.PartialRunResult] = Queue()
        environments = []
        for env in task.request.environments:
            try:
                environments.append((env.force, from_grpc(env)))
            except ValueError:
                raise GRPCException(f"Unknown environment kind: {env.kind}")
            except TypeError as exc:
                raise GRPCException(f"Invalid environment: {str(exc)}")

        if not environments:
            raise GRPCException(
                "At least one environment must be specified for a run!",
                StatusCode.INVALID_ARGUMENT,
            )

        log_handler = LogHandler(messages)
        run_settings = replace(
            self.default_settings,
            log_hook=log_handler.handle,
            serialization_method=task.request.function.method,
        )

        for _, environment in environments:
            environment.apply_settings(run_settings)

        _, primary_environment = environments[0]

        if AGENT_REQUIREMENTS:
            python_version = getattr(
                primary_environment, "python_version", active_python()
            )
            agent_environ = VirtualPythonEnvironment(
                requirements=AGENT_REQUIREMENTS,
                python_version=python_version,
            )
            agent_environ.apply_settings(run_settings)
            environments.insert(1, (False, agent_environ))

        extra_inheritance_paths = []
        if INHERIT_FROM_LOCAL:
            local_environment = LocalPythonEnvironment()
            extra_inheritance_paths.append(local_environment.create())

        with ThreadPoolExecutor(max_workers=1) as local_pool:
            environment_paths = []
            for should_force_create, environment in environments:
                future = local_pool.submit(
                    environment.create, force=should_force_create
                )
                yield from self.watch_queue_until_completed(messages, future.done)
                try:
                    # Assuming that the iterator above only stops yielding once
                    # the future is completed, the timeout here should be redundant
                    # but it is just in case.
                    environment_paths.append(future.result(timeout=0.1))
                except EnvironmentCreationError as e:
                    raise GRPCException(f"{e}", StatusCode.INVALID_ARGUMENT)

            primary_path, *inheritance_paths = environment_paths
            inheritance_paths.extend(extra_inheritance_paths)
            _, primary_environment = environments[0]

            connection = LocalPythonGRPC(
                primary_environment,
                primary_path,
                extra_inheritance_paths=inheritance_paths,
            )

            with self.bridge_manager.establish(connection, queue=messages) as agent:
                task.agent = agent
                function_call = definitions.FunctionCall(
                    function=task.request.function,
                    setup_func=task.request.setup_func,
                )
                if not task.request.HasField("setup_func"):
                    function_call.ClearField("setup_func")

                future = local_pool.submit(
                    _proxy_to_queue,
                    queue=agent.message_queue,
                    bridge=agent.stub,
                    input=function_call,
                )

                # Unlike above; we are not interested in the result value of future
                # here, since it will be already transferred to other side without
                # us even seeing (through the queue).
                yield from self.watch_queue_until_completed(
                    agent.message_queue, future.done
                )

                # But we still have to check whether there were any errors raised
                # during the execution, and handle them accordingly.
                exception = future.exception(timeout=0.1)
                if exception is not None:
                    # If this is an RPC error, propagate it as is without any
                    # further processing.
                    if isinstance(exception, grpc.RpcError):
                        raise GRPCException(
                            str(exception),
                            exception.code(),
                        )

                    # Otherwise this is a bug in the agent itself, so needs
                    # to be propagated with more details.
                    for line in traceback.format_exception(
                        type(exception), exception, exception.__traceback__
                    ):
                        yield from self.log(line, level=LogLevel.ERROR)
                    if isinstance(exception, AgentError):
                        raise GRPCException(str(exception), StatusCode.ABORTED)
                    else:
                        raise GRPCException(
                            f"An unexpected error occurred: {exception}.",
                            StatusCode.UNKNOWN,
                        )

    def _run_task_in_background(self, task: Task) -> None:
        for _ in self._run_task(task):
            pass

    def Submit(
        self,
        request: definitions.SubmitRequest,
        context: ServicerContext,
    ) -> definitions.SubmitResponse:
        task = Task(request=request.function)
        task.future = RUNNER_THREAD_POOL.submit(
            self._run_task_in_background,
            task,
        )
        task_id = str(uuid.uuid4())

        print(f"Submitted a task {task_id}")

        self.background_tasks[task_id] = task

        def _callback(_):
            print(f"Task {task_id} finished")
            self.background_tasks.pop(task_id, None)

        task.future.add_done_callback(_callback)

        return definitions.SubmitResponse(task_id=task_id)

    def Run(
        self,
        request: definitions.BoundFunction,
        context: ServicerContext,
    ) -> Iterator[definitions.PartialRunResult]:
        try:
            yield from self._run_task(Task(request=request))
        except GRPCException as exc:
            return self.abort_with_msg(
                exc.message,
                context,
                code=exc.code,
            )

    def List(
        self,
        request: definitions.ListRequest,
        context: ServicerContext,
    ) -> definitions.ListResponse:
        return definitions.ListResponse(
            tasks=[
                definitions.TaskInfo(task_id=task_id)
                for task_id in self.background_tasks.keys()
            ]
        )

    def Cancel(
        self,
        request: definitions.CancelRequest,
        context: ServicerContext,
    ) -> definitions.CancelResponse:
        task_id = request.task_id

        print(f"Canceling task {task_id}")
        task = self.background_tasks.get(task_id)
        if task is not None:
            task.cancel()

        return definitions.CancelResponse()

    def watch_queue_until_completed(
        self, queue: Queue, is_completed: Callable[[], bool]
    ) -> Iterator[definitions.PartialRunResult]:
        """Watch the given queue until the is_completed function returns True.
        Note that even if the function is completed, this function might not
        finish until the queue is empty.
        """

        timer = time.monotonic()
        while not is_completed():
            try:
                yield queue.get(timeout=_Q_WAIT_DELAY)
            except QueueEmpty:
                # Send an empty (but 'real') packet to the client, currently a hacky way
                # to make sure the stream results are never ignored.
                if time.monotonic() - timer > EMPTY_MESSAGE_INTERVAL:
                    timer = time.monotonic()
                    yield definitions.PartialRunResult(
                        is_complete=False,
                        logs=[],
                        result=None,
                    )

        # Clear the final messages
        while not queue.empty():
            try:
                yield queue.get_nowait()
            except QueueEmpty:
                continue

    def log(
        self,
        message: str,
        level: LogLevel = LogLevel.TRACE,
        source: LogSource = LogSource.BRIDGE,
    ) -> Iterator[definitions.PartialRunResult]:
        log = to_grpc(Log(message, level=level, source=source))
        log = cast(definitions.Log, log)
        yield definitions.PartialRunResult(result=None, is_complete=False, logs=[log])

    def abort_with_msg(
        self,
        message: str,
        context: ServicerContext,
        *,
        code: StatusCode = StatusCode.INVALID_ARGUMENT,
    ) -> None:
        context.set_code(code)
        context.set_details(message)
        return None

    def cancel_tasks(self):
        for task in self.background_tasks.values():
            task.cancel()


def _proxy_to_queue(
    queue: Queue,
    bridge: definitions.AgentStub,
    input: definitions.FunctionCall,
) -> None:
    for message in bridge.Run(input):
        queue.put_nowait(message)


@dataclass
class LogHandler:
    messages: Queue

    def handle(self, log: Log) -> None:
        logger.log(log.level, log.message, source=log.source)
        self._add_log_to_queue(log)

    def _add_log_to_queue(self, log: Log) -> None:
        grpc_log = cast(definitions.Log, to_grpc(log))
        grpc_result = definitions.PartialRunResult(
            is_complete=False,
            logs=[grpc_log],
            result=None,
        )
        self.messages.put_nowait(grpc_result)


def main() -> None:
    server = grpc.server(
        RUNNER_THREAD_POOL,
        options=get_default_options(),
    )
    with BridgeManager() as bridge_manager:
        definitions.register_isolate(IsolateServicer(bridge_manager), server)
        health.register_health(HealthServicer(), server)

        server.add_insecure_port("[::]:50001")
        print("Started listening at localhost:50001")

        server.start()
        server.wait_for_termination()


if __name__ == "__main__":
    main()
