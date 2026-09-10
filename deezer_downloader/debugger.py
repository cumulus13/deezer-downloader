#!/usr/bin/env python3

# File: logger.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-07-01
# Description: 
# License: MIT

import sys
import os
import traceback
from textwrap import wrap

try:
    from .printer import _print, HAS_MAKE_COLORS, HAS_RICH  # type: ignore
except:
    from printer import _print, HAS_MAKE_COLORS, HAS_RICH  # type: ignore

try:
    from . icons import Icons  # type: ignore
except:
    from icons import Icons  # type: ignore  

tprint = None  # type: ignore
print_exception = None  # type: ignore

LOG_LEVEL = os.getenv('LOG_LEVEL', "CRITICAL")
SHOW_LOG = False
if len(sys.argv) > 1 and any('--debug' == arg for arg in sys.argv):
    _print("🐞 Debug mode enabled [GitDate]")
    os.environ["DEBUG"] = "1"
    os.environ['LOGGING'] = "1"
    os.environ.pop('NO_LOGGING', None)
    os.environ['TRACEBACK'] = "1"
    os.environ["LOGGING"] = "1"
    LOG_LEVEL = "DEBUG"
    _print("start load 'pydebugger' module ...")
    from pydebugger.debug import debug  # type: ignore
    _print("finish load 'pydebugger' module ...")
    SHOW_LOG = True
elif str(os.getenv('DEBUG', '0')).lower() in ['1', 'true', 'ok', 'on', 'yes']:
    _print("🐞 Debug mode enabled [GitDate]")
    os.environ['LOGGING'] = "1"
    os.environ.pop('NO_LOGGING', None)
    os.environ['TRACEBACK'] = "1"
    os.environ["LOGGING"] = "1"
    LOG_LEVEL = "DEBUG"
    _print("start load 'pydebugger' module ...")
    from pydebugger.debug import debug  # type: ignore
    _print("finish load 'pydebugger' module ...")
    SHOW_LOG = True
elif len(sys.argv) > 1 and any('--pydebugger' == arg for arg in sys.argv):
    from pydebugger.debug import debug  # type: ignore
    _print("debugging using 'pydebugger' module ...")
else:
    os.environ['NO_LOGGING'] = "1"

    def debug(*args, **kwargs):
        pass

exceptions = ['mardown_it', 'subprocess', 'pika', 'urllib', 'urllib2', 'urllib3', 'git', 'mardown', 'mardown_it.rules_block.blockquote', 'github', 'pygithub', 'requester']

# import richcolorlog
try:
    from richcolorlog import setup_logging, print_exception as tprint  # type: ignore
    logger = setup_logging('gitdate', exceptions=exceptions, level=LOG_LEVEL, show=SHOW_LOG)
except:
    import logging

    for exc in exceptions:
        logging.getLogger(exc).setLevel(logging.CRITICAL)

    try:
        from .custom_logging import get_logger  # type: ignore
    except:
        from custom_logging import get_logger

    LOG_LEVEL = getattr(logging, LOG_LEVEL.upper(), logging.CRITICAL)

    logger = get_logger('gitdate', level=LOG_LEVEL)

logger.debug("finish load richcolorlog")

if not tprint:
    def tprint(*args, **kwargs):
        traceback.print_exc()

def is_debug():
    return str(os.getenv('TRACEBACK', '0')).lower() in ('1', 'true', 'yes', 'ok') or str(os.getenv('GITDATE_DEBUG', '0')).lower() in ('1', 'true', 'yes', 'ok')

def is_verbose():
    return any(i for i in sys.argv[1:] if i in ['--verbose', '--debug'])

def set_debug():
    try:
        from pydebugger.debug import debug
    except:
        _print(f"{Icons.BUG} {Icons.ERROR} [bold #FFFF00]please install 'pydebugger' before ![/]")
        def debug(*args, **kwargs):
            return

def print_wrapped_error(prefix_msg, remotename, exception, prefix_len=None):
    """Helper function to print formatted error messages with proper wrapping"""
    if prefix_len is None:
        # Calculate space based on the actual printed length (excluding color codes)
        import re
        clean_prefix = re.sub(r'\[.*?\]', '', prefix_msg)
        prefix_len = len(clean_prefix) + len(remotename) + 7  # 7 for extra chars like ': '

    space = " " * prefix_len
    terminal_width = os.get_terminal_size()[0]
    _error_wrap = wrap(str(exception), terminal_width - prefix_len,
                       initial_indent=space, subsequent_indent=space)
    error = "\n".join(_error_wrap[1:]) if len(_error_wrap) > 1 else ""

    _print(f"{Icons.ERROR} {prefix_msg} '[bold #00FFFF]{remotename}[/]': ", end='')  
    if len(_error_wrap) > 1:
        _print(f"[bold #FF007F]{_error_wrap[0].strip()}[/]")  
    # else:
    #     _print("\n")  
    if error:
        _print(f"[bold #FF007F]{error}[/]")  

# def dprint(text):
#     if "ghp_" in text:
#         # replace from gph_(????) to ghp_*********,
#     if is_debug():
#         import inspect
#         # Get the caller's stack frame
#         caller_frame = inspect.currentframe().f_back
#         filename = caller_frame.f_code.co_filename
#         line_no = caller_frame.f_lineno

#         lines = f"{filename}:{line_no}"

#         _print(
#           f"[bold #FFAA00]{Icons.BUG}[/] [bold #550000 on #FFAA00]{text}[/] [white on"
#           f" blue]\\[{lines}][/]"
#         )

def dprint(text):
    import inspect
    import re
    # Convert non-string inputs to string for processing
    str_text = str(text) if not isinstance(text, str) else text
    
    # Mask GitHub tokens (both Classic ghp_... and Fine-Grained github_pat_...)
    if "ghp_" in str_text or "github_pat_" in str_text:
        str_text = re.sub(r'(ghp_[A-Za-z0-9_]{36,})', r'ghp_\1', str_text)
        str_text = re.sub(r'ghp_[A-Za-z0-9_]+', 'ghp_***', str_text)
        str_text = re.sub(r'github_pat_[A-Za-z0-9_]+', 'github_pat_***', str_text)

    if is_debug():
        # Get the caller's stack frame
        caller_frame = inspect.currentframe().f_back  # type: ignore
        filename = caller_frame.f_code.co_filename  # type: ignore
        line_no = caller_frame.f_lineno  # type: ignore

        lines = f"{filename}:{line_no}"

        _print(
            f"[bold #FFAA00]{Icons.BUG}[/] [bold #550000 on #FFAA00]{str_text}[/] [white on"
            f" blue]\\[{lines}][/]"
        )

# if not print_exception:
#     if HAS_MAKE_COLORS:
#         from make_colors import make_colors  # type: ignore
#         def print_exception(*args, **kwargs):
#             exc_type, exc_value, exc_tb = sys.exc_info()
#             tb_list = traceback.format_exception(exc_type, exc_value, exc_tb)
#             for line in tb_list:
#                 if line.strip().startswith("File"):
#                     _print(make_colors(line.rstrip(), 'lc'))  
#                 elif exc_type and line.strip().startswith(exc_type.__name__):
#                     _print(make_colors(line.strip(), 'lw', 'r'))  
#                 else:
#                     _print(make_colors(line.strip(), 'b', 'ly'))  
#     elif HAS_RICH:
#         from rich.console import Console
#         console = Console()
#         print_exception = console.print_exception
#     else:
#         def print_exception():
#             exc_type, exc_value, exc_tb = sys.exc_info()
#             return traceback.print_exception(exc_type, exc_value, exc_tb)


# # Initialize print_exception fallback chain safely
# try:
#     print_exception
# except NameError:
#     print_exception = None

if not print_exception:
    if HAS_MAKE_COLORS:
        try:
            from make_colors import make_colors  # type: ignore
        except ImportError:
            make_colors = None

        def print_exception(*args, **kwargs):
            exc_type, exc_value, exc_tb = sys.exc_info()
            if not exc_type:
                return
            tb_list = traceback.format_exception(exc_type, exc_value, exc_tb)
            for line in tb_list:
                line_str = line.rstrip()
                if line_str.strip().startswith("File") and callable(make_colors):
                    _print(make_colors(line_str, 'lc'))  
                elif exc_type and line_str.strip().startswith(exc_type.__name__) and callable(make_colors):
                    _print(make_colors(line_str.strip(), 'lw', 'r'))  
                elif callable(make_colors):
                    _print(make_colors(line_str.strip(), 'b', 'ly'))  
                else:
                    _print(line_str)
                    
    elif HAS_RICH:
        try:
            from rich.console import Console
            console = Console()
            print_exception = console.print_exception
        except ImportError:
            def print_exception(*args, **kwargs):
                exc_type, exc_value, exc_tb = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_tb)
    else:
        def print_exception(*args, **kwargs):
            exc_type, exc_value, exc_tb = sys.exc_info()
            return traceback.print_exception(exc_type, exc_value, exc_tb)