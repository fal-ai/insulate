from functools import wraps
import secrets
import threading
from typing import Dict

from flask import Flask, request
from marshmallow import validate

from isolate import prepare_environment
from isolate.backends import BaseEnvironment
from isolate.backends.context import GLOBAL_CONTEXT
from isolate.server._models import (
    Environment,
    EnvironmentRun,
    StatusRequest,
    with_schema,
)
from isolate.server._runs import RunInfo, dehydrated_dual_env_run
from isolate.server._utils import (
    error,
    load_token,
    success,
    wrap_validation_errors,
)
from isolate.server._auth import create_auth_token, validate_auth_token

app = Flask(__name__)


ENV_STORE: Dict[str, BaseEnvironment] = {}
RUN_STORE: Dict[str, RunInfo] = {}
MAX_JOIN_WAIT = 1

app.config.from_prefixed_env("FAL")

if app.config.get('USER_NAME', False):
    app.config['SECRET_KEY'] = secrets.token_urlsafe()
    app.config['AUTH_TOKEN'] = create_auth_token(
        app.config['USER_NAME'],
        app.config['SECRET_KEY'])

    print("++++")
    print("The following line contains your authentication token. Put it in 'x-access-token' header.")
    print(app.config['AUTH_TOKEN'])
    print("++++")

# Authentication decorator
def check_auth(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
            if validate_auth_token(
                    token,
                    app.config["USER_NAME"],
                    app.config["SECRET_KEY"]):
                return f(*args, **kwargs)
            else:
                return error(code=401, message="Invalid token")

        if not token and app.config.get("USER_NAME", False):
            return error(code=401, message="Isolate server is configured with the authentication mode, but no authentication token was passed")
            ```

        return f(*args, **kwargs)

    return decorator


@app.route("/environments/create", methods=["POST"])
@wrap_validation_errors
@check_auth
def create_environment():
    """Create a new environment from the POST'd definition
    (as JSON). Returns the token that can be used for running
    it in the future."""

    data = with_schema(Environment, request.json)
    token = secrets.token_urlsafe()
    ENV_STORE[token] = prepare_environment(
        data["kind"],
        **data["configuration"],
    )
    return success(token=token)


@app.route("/environments/runs", methods=["POST"])
@wrap_validation_errors
@check_auth
def run_environment():
    """Run the function (serialized with the `serialization_backend` specified
    as a query parameter) from the POST'd data on the specified environment.
    It will return a new token that can be used to check the status of the run
    periodically through `/environment/runs/<token>/status` endpoint."""
    data = with_schema(EnvironmentRun, request.args)
    env = load_token(ENV_STORE, data["environment_token"])

    run_info = RunInfo()

    # Context can allow us to change the serialization backend
    # and the log processing.
    run_context = GLOBAL_CONTEXT._replace(
        _serialization_backend=data["serialization_backend"],
        _log_handler=run_info.logs.append,
    )
    env.set_context(run_context)

    # We start running the environment (both the build and the run, actually)
    # in a separate thread, since we don't want this request to block.
    run_info.bound_thread = threading.Thread(
        target=dehydrated_dual_env_run,
        args=(env, request.data, run_info.done_signal),
    )
    run_info.bound_thread.start()

    RUN_STORE[run_info.token] = run_info
    return success(token=run_info.token, code=202)


@app.route("/environments/runs/<token>/status", methods=["GET"])
@wrap_validation_errors
@check_auth
def get_run_status(token):
    """Poll for the status of an environment. Returns all the logs
    (unless the starting point is specified through `logs_start` query
    parameter) and a boolean indicating whether the run is finished.

    Can be accessed even after the run is finished."""

    data = with_schema(StatusRequest, request.args)

    run_info = load_token(RUN_STORE, token)
    if run_info.is_done and run_info.bound_thread.is_alive():
        try:
            run_info.bound_thread.join(timeout=MAX_JOIN_WAIT)
        except TimeoutError:
            return error(message="Runner thread is still running.")

    new_logs = run_info.logs[data["logs_start"] :]
    return success(
        is_done=run_info.is_done,
        logs=[log.serialize() for log in new_logs],
    )
