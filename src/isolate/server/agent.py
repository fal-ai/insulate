# agent-requires: isolate[server]

from __future__ import annotations

import traceback
from argparse import ArgumentParser
from concurrent import futures
from dataclasses import dataclass
from typing import Any, Iterator

import grpc
from grpc import ServicerContext, StatusCode

from isolate.server import definitions
from isolate.server.serialization import SerializationError, from_grpc, to_grpc


@dataclass
class AgentServicer(definitions.AgentServicer):
    def Run(
        self,
        request: definitions.SerializedObject,
        context: ServicerContext,
    ) -> Iterator[definitions.PartialRunResult]:
        yield from self.log(f"A connection has been established: {context.peer()}!")

        if request.was_it_raised:
            return self.abort_with_msg(
                "The input function must be callable, not a raised exception.", context
            )

        try:
            function = from_grpc(request, object)
        except SerializationError:
            yield from self.log(traceback.format_exc())
            return self.abort_with_msg(
                "The input function could not be deserialized.",
                context,
            )

        if not callable(function):
            return self.abort_with_msg(
                f"The input function must be callable, not {type(function).__name__}.",
                context,
            )

        yield from self.log("Starting the execution of the input function.")

        was_it_raised = False
        try:
            result = function()
        except BaseException as exc:
            result = exc
            was_it_raised = True

        yield from self.log("Completed the execution of the input function.")

        try:
            serialized_result = to_grpc(
                result,
                definitions.SerializedObject,
                method=request.method,
                was_it_raised=was_it_raised,
            )
        except SerializationError:
            yield from self.log(traceback.format_exc(), level=definitions.ERROR)
            return self.abort_with_msg(
                "The result of the input function could not be serialized.",
                context,
            )
        except BaseException:
            yield from self.log(traceback.format_exc(), level=definitions.ERROR)
            return self.abort_with_msg(
                "An unexpected error occurred while serializing the result.", context
            )

        yield from self.log(
            "Serialization of the result is complete. Sending the result."
        )
        yield definitions.PartialRunResult(
            result=serialized_result, is_complete=True, logs=[]
        )

    def log(
        self,
        message: str,
        level: definitions.LogLevel = definitions.TRACE,
        source: definitions.LogSource = definitions.BRIDGE,
    ) -> Iterator[definitions.PartialRunResult]:
        log = definitions.Log(message=message, level=level, source=source)
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


def create_server(address: str) -> grpc.Server:
    """Create a new (temporary) gRPC server listening on the given
    address."""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=1),
        maximum_concurrent_rpcs=1,
    )

    # Local server credentials allow us to ensure that the
    # connection is established by a local process.
    server_credentials = grpc.local_server_credentials()
    server.add_secure_port(address, server_credentials)
    return server


def run_agent(address: str) -> int:
    """Run the agent servicer on the given address."""
    server = create_server(address)
    servicer = AgentServicer()

    # This function just calls some methods on the server
    # and register a generic handler for the bridge. It does
    # not have any global side effects.
    definitions.register_agent(servicer, server)

    server.start()
    server.wait_for_termination()
    return 0


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("address", type=str)

    options = parser.parse_args()
    return run_agent(options.address)


if __name__ == "__main__":
    main()
