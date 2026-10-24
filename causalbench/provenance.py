"""Retain the source loaded by this process, rather than relabelling old code after file edits."""
from pathlib import Path
import threading

_LOCK=threading.RLock()
_SOURCES={}


def loaded_source(filename):
    path=str(Path(filename).resolve())
    with _LOCK:
        if path in _SOURCES:
            return _SOURCES[path]
        return Path(path).read_bytes()


def register_source(filename):
    path=str(Path(filename).resolve())
    with _LOCK:
        _SOURCES[path]=Path(path).read_bytes()
        return _SOURCES[path]


def retained_sources():
    with _LOCK:
        return dict(_SOURCES)


_LOADED_SOURCE=register_source(__file__)
