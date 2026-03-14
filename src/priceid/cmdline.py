#!/usr/bin/env python3
import argparse

from priceid.tui import PriceApp


def main():
    parser = argparse.ArgumentParser(description="Nethack Price ID — interactive TUI")
    parser.add_argument("--small", action="store_true", help="Force small-screen mode")
    args = parser.parse_args()
    PriceApp(force_small=args.small).run(mouse=False)
