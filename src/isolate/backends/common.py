import functools
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def rmdir_on_fail(path: Path) -> Iterator[None]:
    try:
        yield
    except Exception:
        if path.exists():
            shutil.rmtree(path)
        raise


def get_executable_path(search_path: Path, executable_name: str) -> Path:
    bin_dir = (search_path / "bin").as_posix()
    executable_path = shutil.which(executable_name, path=bin_dir)
    if executable_path is None:
        raise FileNotFoundError(
            f"Could not find '{executable_name}' in '{search_path}'. "
            f"Is the virtual environment corrupted?"
        )

    return Path(executable_path)


_NO_HIT = object()


def cache_static(func):
    """Cache the result of an parameter-less function."""
    _function_cache = _NO_HIT

    @functools.wraps(func)
    def wrapper():
        nonlocal _function_cache
        if _function_cache is _NO_HIT:
            _function_cache = func()
        return _function_cache

    return wrapper
