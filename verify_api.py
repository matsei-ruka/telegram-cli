#!/usr/bin/env python3
"""Backward-compatible wrapper → `tg status` / `tg login` / `tg bots list`."""
from __future__ import annotations

import sys

from telegram_cli.cli import app

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--login" in args:
        sys.argv = ["tg", "login"]
    elif "--probe" in args:
        sys.argv = ["tg", "bots", "list"]
    else:
        sys.argv = ["tg", "status"]
    app()
