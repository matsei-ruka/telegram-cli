#!/usr/bin/env python3
"""Backward-compatible wrapper → `tg bots create`."""
from __future__ import annotations

import sys

from telegram_cli.cli import app

if __name__ == "__main__":
    # Map old flags: --name --username --photo
    # Prefer: tg bots create -n … -u … -p …
    sys.argv = ["tg", "bots", "create", *sys.argv[1:]]
    # normalize long options already match
    app()
