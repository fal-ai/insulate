import base64
import importlib
import os
import subprocess
from contextlib import ExitStack, closing
from dataclasses import dataclass
from multiprocessing.connection import ConnectionWrapper, Listener
from pathlib import Path
from typing import Any, ContextManager, List, Tuple, Union

from isolate.backends import (
    BasicCallable,
    CallResultType,
    EnvironmentConnection,
)
from isolate.backends.common import get_executable_path, python_path_for
from isolate.backends.connections.ipc import agent


class _MultiFormatListener(Listener):
    def __init__(self, backend_name: str, *args: Any, **kwargs: Any) -> None:
        self.serialization_backend = load_serialization_backend(backend_name)
        super().__init__(*args, **kwargs)

    def accept(self) -> ConnectionWrapper:
        return closing(
            ConnectionWrapper(
                super().accept(),
                dumps=self.serialization_backend.dumps,
                loads=self.serialization_backend.loads,
            )
        )


def load_serialization_backend(backend_name: str) -> Any:
    # TODO(feat): This should probably throw a better error if the
    # given backend does not exist.
    return importlib.import_module(backend_name)


def encode_service_address(address: Tuple[str, int]) -> str:
    host, port = address
    return base64.b64encode(f"{host}:{port}".encode()).decode("utf-8")


@dataclass
class IsolatedProcessConnection(EnvironmentConnection):
    """A generic IPC implementation for running the isolate backend
    in a separated process.

    Each implementation needs to define a start_process method to
    spawn the agent."""

    def start_process(
        self,
        connection: ConnectionWrapper,
        *args: Any,
        **kwargs: Any,
    ) -> ContextManager[subprocess.Popen]:
        """Start the agent process."""
        raise NotImplementedError

    def run(
        self, executable: BasicCallable, *args: Any, **kwargs: Any
    ) -> CallResultType:
        """Spawn an agent process using the given environment, run the given
        `executable` in that process, and return the result object back."""

        with ExitStack() as stack:
            # IPC flow is the following:
            #  1. [controller]: Create the socket server
            #  2. [controller]: Spawn the call agent with the socket address
            #  3.      [agent]: Connect to the socket server
            #  4. [controller]: Accept the incoming connection request
            #  5. [controller]: Send the executable over the established bridge
            #  6.      [agent]: Receive the executable from the bridge
            #  7.      [agent]: Execute the executable and once done send the result back
            #  8. [controller]: Loop until either the isolated process exits or sends any
            #                   data (will be interpreted as a tuple of two mutually exclusive
            #                   objects, either a result object or an exception to be raised).
            #

            self.log("Starting the controller bridge.")
            controller_service = stack.enter_context(
                _MultiFormatListener(
                    self.environment.context.serialization_backend_name,
                    family="AF_INET",
                )
            )

            self.log(
                "Controller server is listening at {}. Attempting to start the agent process.",
                controller_service.address,
            )
            assert not (args or kwargs), "run() should not receive any arguments."
            isolated_process = stack.enter_context(
                self.start_process(controller_service, *args, **kwargs)
            )

            # TODO(fix): this might hang if the agent process crashes before it can
            # connect to the controller bridge.
            self.log(
                "Awaiting agent process of {} to establish a connection.",
                isolated_process.pid,
            )
            established_connection = stack.enter_context(controller_service.accept())

            self.log(
                "Bridge between controller and the agent has been established.",
                controller_service.address,
            )
            established_connection.send(executable)

            self.log(
                "Executable has been sent, awaiting execution result.",
            )
            return self.poll_until_result(isolated_process, established_connection)

    def poll_until_result(
        self, process: subprocess.Popen, connection: ConnectionWrapper
    ) -> CallResultType:
        """Take the given process, and poll until either it exits or returns
        a result object."""

        while process.poll() is None:
            # Normally, if we do connection.read() without having this loop
            # it is going to block us indefinitely (even if the underlying
            # process has crashed). We can use a combination of process.poll
            # and connection.poll to check if the process is alive and has data
            # to move forward.
            if not connection.poll():
                continue

            # TODO(fix): handle EOFError that might happen here (e.g. problematic
            # serialization might cause it).
            result, did_it_raise = connection.recv()

            if did_it_raise:
                raise result
            else:
                return result

        raise OSError("The isolated process has exited unexpectedly with code '{}'.")


@dataclass
class PythonIPC(IsolatedProcessConnection):
    """A simply Python IPC implementation that takes the base directory
    of a new Python environment (structure that complies with sysconfig)
    and runs the agent process in that environment."""

    environment_path: Path

    def start_process(
        self,
        connection: ConnectionWrapper,
        *args: Any,
        **kwargs: Any,
    ) -> ContextManager[subprocess.Popen]:
        """Start the Python agent process with using the Python interpreter from
        the given environment_path."""

        python_executable = get_executable_path(self.environment_path, "python")
        print(python_executable)
        return subprocess.Popen(self._get_python_cmd(python_executable, connection))

    def _get_python_cmd(
        self,
        executable: Path,
        connection: ConnectionWrapper,
    ) -> List[Union[str, Path]]:
        assert executable.exists(), f"Python executable {executable} does not exist."
        return [
            executable,
            agent.__file__,
            encode_service_address(connection.address),
            # TODO(feat): we probably should check if the given backend is installed
            # on the remote interpreter, otherwise it will fail without establishing
            # the connection with the bridge.
            "--serialization-backend",
            self.environment.context.serialization_backend_name,
        ]


@dataclass
class DualPythonIPC(PythonIPC):
    """A dual-environment Python IPC implementation that
    can run the agent process in an environment with its
    Python and also load the shared libraries from a different
    one."""

    secondary_path: Path

    def start_process(
        self,
        connection: ConnectionWrapper,
        *args: Any,
        **kwargs: Any,
    ) -> ContextManager[subprocess.Popen]:
        # We are going to use the primary environment to run the Python
        # interpreter, but at the same time we are going to inherit all
        # the packages from the secondary environment.

        # The search order is important, we want the primary path to
        # take precedence.
        python_path = python_path_for(self.environment_path, self.secondary_path)

        # The user of DualPythonIPC must ensure that the Python versions from
        # both of these environments are the same. Using different versions is
        # an undefined behavior.
        python_executable = get_executable_path(self.environment_path, "python")
        return subprocess.Popen(
            self._get_python_cmd(python_executable, connection),
            env={"PYTHONPATH": python_path, **os.environ},
        )
