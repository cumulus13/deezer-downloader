#!/usr/bin/env python3

# File: printer.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-06-29
# Description: Custom Rich & Fallback Printing System
# License: MIT

import re
import sys
from typing import Any, Dict, Set

import time
import threading
import traceback

# Save Python's real built-in print
__builtin_print__ = print

HAS_RICH = False
HAS_MAKE_COLORS = False
_console = None
Text = None
Live = None
make_colors = None
Syntax = None
Console = None

# Initialize Rich or Fallback Terminal Mechanics
try:
    from rich.console import Console
    _console = Console(force_terminal=True)
    console = _console
    cstatus = _console.status

    from rich.theme import Theme
    from rich.text import Text
    from rich.live import Live
    from rich.columns import Columns
    from rich.spinner import Spinner
    from rich.syntax import Syntax
    HAS_RICH = True
except Exception:
    from unittest.mock import MagicMock
    cstatus = MagicMock()

    try:
        from make_colors import make_colors  # type: ignore
        HAS_MAKE_COLORS = True
        TAG_PATTERN = re.compile(r'\[.*?\]')
        EMOJI_PATTERN = re.compile(r':.*?:')

        class console:
            @staticmethod
            def print(*args, **kwargs):
                cleaned = []
                for arg in args:
                    if isinstance(arg, str):
                        arg = TAG_PATTERN.sub("", arg)
                        arg = EMOJI_PATTERN.sub("", arg)
                    cleaned.append(arg)
                __builtin_print__(*cleaned, **kwargs)

            @staticmethod
            def print_exception(*args, **kwargs):
                exc_type, exc_value, exc_tb = sys.exc_info()
                tb_list = traceback.format_exception(exc_type, exc_value, exc_tb)
                for line in tb_list:
                    if line.strip().startswith("File"):
                        __builtin_print__(make_colors(line.rstrip(), 'lc'))
                    elif exc_type and line.strip().startswith(exc_type.__name__):
                        __builtin_print__(make_colors(line.strip(), 'lw', 'r'))
                    else:
                        __builtin_print__(make_colors(line.strip(), 'b', 'ly'))

            @staticmethod
            def input(message, *args, **kwargs):
                message = make_colors(message, *args, **kwargs)
                return input(message)
    except Exception:
        make_colors = lambda text, *args, **kwargs: text
        class console:
            @staticmethod
            def print(*args, **kwargs):
                clean_args = [re.sub(r'\[.*?\]', '', str(a)) for a in args]
                return __builtin_print__(*args, **kwargs)

            @staticmethod
            def print_exception():
                exc_type, exc_value, exc_tb = sys.exc_info()
                return traceback.print_exception(exc_type, exc_value, exc_tb)

            @staticmethod
            def input(message):
                return input(message)

SEVERITY_ALIASES: Dict[str, str] = {
    'emer': 'emergency', 'emerg': 'emergency', 'em': 'emergency', '7': 'emergency',
    'cri': 'critical', 'criti': 'critical', 'c': 'critical', '6': 'critical',
    'al': 'alert', 'a': 'alert', '5': 'alert',
    'err': 'error', 'er': 'error', 'e': 'error', '4': 'error',
    'not': 'notice', 'noti': 'notice', 'n': 'notice', '3': 'notice',
    'warn': 'warning', 'w': 'warning', '2': 'warning',
    'inf': 'info', 'i': 'info', '1': 'info',
    'deb': 'debug', 'd': 'debug', '0': 'debug',
}

# 2. Map primary severity levels to Rich style strings
SEVERITY_STYLES: Dict[str, str] = {
    'emergency': "white on #AA007F",
    'critical': "white on #5500FF",
    'alert': "white on #0000FF",
    'error': "white on red",
    'notice': "black on #00FFFF",
    'warning': "black on #FFFF00",
    'info': "black on #00FF00",
    'debug': "#00FF00 on #FF5500",
}


# 2. Build Theme Dictionary & Valid Keys
THEME_DICT: Dict[str, str] = {**SEVERITY_STYLES}
for alias, primary in SEVERITY_ALIASES.items():
    THEME_DICT[alias] = SEVERITY_STYLES[primary]

VALID_CUSTOM_KEYS: Set[str] = set(THEME_DICT.keys())

if HAS_RICH:
    _console = Console(theme=Theme(THEME_DICT))


def _core_output(is_log: bool, *args: Any, **kwargs: Any) -> None:
    """
    Core engine handling style extraction, span filtering, and fallbacks.
    Used by both _print and _log.
    """
    severity = kwargs.pop('s', None)
    style = None

    if isinstance(severity, str):
        severity_clean = severity.lower().strip()
        if severity_clean in VALID_CUSTOM_KEYS:
            style = severity_clean

    if HAS_RICH and _console:
        try:
            # Create a copy so we don't mutate the original kwargs destructively 
            rich_kwargs = kwargs.copy()
            rich_args = list(args)

            if style:
                rich_kwargs['style'] = style
                
                for i, arg in enumerate(rich_args):
                    if isinstance(arg, str):
                        try:
                            text_obj = Text.from_markup(arg)
                            
                            # Keep only our custom valid keys, discard standard formatting
                            text_obj.spans = [
                                span for span in text_obj.spans 
                                if str(span.style) in VALID_CUSTOM_KEYS
                            ]
                            rich_args[i] = text_obj 
                        except Exception:
                            pass
            
            # Route to the appropriate rich method
            if is_log:
                _console.log(*rich_args, **rich_kwargs)
            else:
                _console.print(*rich_args, **rich_kwargs)
            return
            
        except Exception:
            pass # Swallow rich crash and fallback

    # --- FALLBACK LOGIC ---
    safe_print_kwargs = {
        k: v for k, v in kwargs.items() 
        if k in ('sep', 'end', 'file', 'flush')
    }

    if 'make_colors' in globals() and callable(make_colors): # type: ignore
        try:
            colored_args = [
                make_colors(a) if isinstance(a, str) else a 
                for a in args
            ] 
            __builtin_print__(*colored_args, **safe_print_kwargs)
            return
        except Exception:
            pass

    __builtin_print__(*args, **safe_print_kwargs)


def _print(*args: Any, **kwargs: Any) -> None:
    """Safely print using Rich Console.print() or fallback printers."""
    _core_output(False, *args, **kwargs)

def _log(*args: Any, **kwargs: Any) -> None:
    """Safely log using Rich Console.log() or fallback printers."""
    _core_output(True, *args, **kwargs)

def render_markup(markup: str) -> str:
    """Render Rich markup into an ANSI string."""
    if HAS_RICH and _console:
        with _console.capture() as capture:
            _console.print(markup, end="")
        return capture.get()
    return markup


def spin_for(seconds: float, message: str, position: str = "left") -> None:
    """Runs a manual spinner for a set duration."""
    if not HAS_RICH:
        print(message)
        time.sleep(seconds)
        return

    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_time = time.time() + seconds
    frame_idx = 0
    text_rendered = False

    while time.time() < end_time:
        frame = f"[yellow]{frames[frame_idx]}[/yellow]"
        markup_content = (
            f"{message} {frame}"
            if position.lower() in ("right", "r")
            else f"{frame} {message}"
        )

        text = render_markup(markup_content)
        if text:
            sys.stdout.write(f"\r\033[K{text}")
            sys.stdout.flush()
            text_rendered = True

        frame_idx = (frame_idx + 1) % len(frames)
        time.sleep(0.08)

    if text_rendered:
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()


class Spinnman:
    def __init__(self, message: str, position: str = "left", speed: float = 0.08, keep_on_exit: bool = True):
        self.message = message
        self.position = position
        self.speed = speed
        self.keep_on_exit = keep_on_exit
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _format_markup(self, msg: str, frame: str = "") -> str:
        if not frame:
            return msg
        if self.position.lower() in ("right", "r"):
            return f"{msg} {frame}"
        return f"{frame} {msg}"

    def _clear_line(self):
        """Helper to clear active line and reset cursor to column 0."""
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def _animate(self):
        frame_idx = 0
        while not self._stop_event.is_set():
            with self._lock:
                if self._stop_event.is_set():
                    break
                if HAS_RICH:
                    frame = f"[yellow]{self.frames[frame_idx]}[/yellow]  "
                    markup = self._format_markup(self.message, frame)
                    text = render_markup(markup)
                    if text:
                        sys.stdout.write(f"\r\033[K{text}")
                        sys.stdout.flush()
            frame_idx = (frame_idx + 1) % len(self.frames)  # Fixed: uses len(self.frames)
            time.sleep(self.speed)

    def print(self, *args, **kwargs):
        """Safely print a line above the active spinner line."""
        with self._lock:
            self._clear_line()
            _print(*args, **kwargs)

    def update(self, new_message: str, keep_printed: bool = False, keep_on_exit: bool = True):
        """Update active spinner text.

        :param new_message: The new text message.
        :param keep_printed: If True, prints the PREVIOUS message permanently above before starting new message.
        :param keep_on_exit: Controls whether the NEW message stays on screen when the with block finishes.
        """
        with self._lock:
            self._clear_line()
            if keep_printed and self.message:
                _print(self.message)

            self.message = new_message
            self.keep_on_exit = keep_on_exit

    def __enter__(self):
        if HAS_RICH:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._animate, daemon=True)
            self._thread.start()
        else:
            _print(self.message)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if HAS_RICH and self._thread:
            # Signal thread to stop first
            self._stop_event.set()
            if self._thread.is_alive():
                self._thread.join()
            
            # Lock & clean up line completely
            with self._lock:
                self._clear_line()
                if self.keep_on_exit and self.message:
                    _print(self.message)
                else:
                    # Explicitly ensure clean carriage position for next print
                    sys.stdout.write("\r")
                    sys.stdout.flush()

# Example Spinnman:
# with Spinnman("Checking local branches [1]...", position="right") as s:
#     time.sleep(1.0)
#     s.update("Checking local branches [2]...", keep_printed=False, keep_on_exit=True)
#     time.sleep(1.5)

# _print("Finished!")

if __name__ == '__main__':
    _log("Downloading '01. mymusic.mp3", s='w')