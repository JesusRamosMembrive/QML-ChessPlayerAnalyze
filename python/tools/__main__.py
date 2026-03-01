"""Allow running as: python -m tools.debug_cli"""
from tools.debug_cli import _ensure_utf8_stdout, main

_ensure_utf8_stdout()
main()
