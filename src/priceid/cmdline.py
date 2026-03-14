#!/usr/bin/env python3
import argparse


def main():
    parser = argparse.ArgumentParser(description="Nethack Price ID")
    parser.add_argument(
        "--print",
        type=int,
        nargs="?",
        const=10,
        default=None,
        metavar="CHA",
        help="Print static price table and exit (default charisma: 10)",
    )
    parser.add_argument("--svg", type=str, metavar="FILE", help="Export --print output as SVG")
    parser.add_argument("--small", action="store_true", help="Force small-screen mode")
    args = parser.parse_args()

    if args.print is not None:
        from priceid.pid import print_prices

        print_prices(args.print, svg=args.svg)
    else:
        from priceid.tui import PriceApp

        PriceApp(force_small=args.small).run(mouse=False)
