# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings

from isolate.connections.grpc.definitions import common_pb2 as common__pb2
from isolate.server.definitions import server_pb2 as server__pb2

GRPC_GENERATED_VERSION = '1.64.0'
GRPC_VERSION = grpc.__version__
EXPECTED_ERROR_RELEASE = '1.65.0'
SCHEDULED_RELEASE_DATE = 'June 25, 2024'
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    warnings.warn(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + f' but the generated code in server_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
        + f' This warning will become an error in {EXPECTED_ERROR_RELEASE},'
        + f' scheduled for release on {SCHEDULED_RELEASE_DATE}.',
        RuntimeWarning
    )


class IsolateStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Run = channel.unary_stream(
                '/Isolate/Run',
                request_serializer=server__pb2.BoundFunction.SerializeToString,
                response_deserializer=common__pb2.PartialRunResult.FromString,
                _registered_method=True)
        self.Submit = channel.unary_unary(
                '/Isolate/Submit',
                request_serializer=server__pb2.SubmitRequest.SerializeToString,
                response_deserializer=server__pb2.SubmitResponse.FromString,
                _registered_method=True)
        self.List = channel.unary_unary(
                '/Isolate/List',
                request_serializer=server__pb2.ListRequest.SerializeToString,
                response_deserializer=server__pb2.ListResponse.FromString,
                _registered_method=True)
        self.Cancel = channel.unary_unary(
                '/Isolate/Cancel',
                request_serializer=server__pb2.CancelRequest.SerializeToString,
                response_deserializer=server__pb2.CancelResponse.FromString,
                _registered_method=True)


class IsolateServicer(object):
    """Missing associated documentation comment in .proto file."""

    def Run(self, request, context):
        """Run the given function on the specified environment. Streams logs
        and the result originating from that function.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Submit(self, request, context):
        """Submit a function to be run without waiting for results.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def List(self, request, context):
        """List running tasks
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Cancel(self, request, context):
        """Cancel a running task
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_IsolateServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Run': grpc.unary_stream_rpc_method_handler(
                    servicer.Run,
                    request_deserializer=server__pb2.BoundFunction.FromString,
                    response_serializer=common__pb2.PartialRunResult.SerializeToString,
            ),
            'Submit': grpc.unary_unary_rpc_method_handler(
                    servicer.Submit,
                    request_deserializer=server__pb2.SubmitRequest.FromString,
                    response_serializer=server__pb2.SubmitResponse.SerializeToString,
            ),
            'List': grpc.unary_unary_rpc_method_handler(
                    servicer.List,
                    request_deserializer=server__pb2.ListRequest.FromString,
                    response_serializer=server__pb2.ListResponse.SerializeToString,
            ),
            'Cancel': grpc.unary_unary_rpc_method_handler(
                    servicer.Cancel,
                    request_deserializer=server__pb2.CancelRequest.FromString,
                    response_serializer=server__pb2.CancelResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'Isolate', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('Isolate', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class Isolate(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def Run(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_stream(
            request,
            target,
            '/Isolate/Run',
            server__pb2.BoundFunction.SerializeToString,
            common__pb2.PartialRunResult.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Submit(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/Isolate/Submit',
            server__pb2.SubmitRequest.SerializeToString,
            server__pb2.SubmitResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def List(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/Isolate/List',
            server__pb2.ListRequest.SerializeToString,
            server__pb2.ListResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Cancel(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/Isolate/Cancel',
            server__pb2.CancelRequest.SerializeToString,
            server__pb2.CancelResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
