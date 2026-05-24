#!/usr/bin/env python3
"""Callback type aliases for collision detection.
"""

from typing import Callable

# Callback type aliases — used by key_collision_engine.py, gpu/engine.py, gpu/core.py
MatchCallback = Callable[..., None]
ProgressCallback = Callable[..., None]
CompleteCallback = Callable[..., None]
ErrorCallback = Callable[..., None]
ErrorHandler = Callable[..., None]
EventHandler = Callable[..., None]
