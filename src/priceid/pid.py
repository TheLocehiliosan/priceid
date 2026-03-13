#!/usr/bin/env python3
from rich.console import Console
from rich.layout import Layout
from rich.table import Table
from rich.panel import Panel
import argparse

BASES = [2, 8, 10, 20, 30, 50, 60, 80, 100, 150, 200, 250, 300, 400, 500, 600, 700]

SCROLLS = """
? 20    \\[identify]
? 50    \\[light]
? 60    \\[e.weapon]
? 60/80 \\[e.armor/r.curse/e.weapon]
? 80    \\[e.armor/r.curse]
? 100   \\[conf/d.armor/fire/fdet/gdet/map/scare/tport]
? 200   \\[amnesia/c.monster/earth/tame]
? 300   \\[charge/geno/punish/stink]
"""

POTIONS = """
! 50    \\[booze/fruit/s.inv/sick]
! 100   \\[conf/xheal/hall/heal/r.able/sleep]
! 150   \\[blind/g.energy/inv/mdet/odet]
! 150/2 \\[blind/g.energy/inv/mdet/odet/enlight/fheal/lev/poly/speed]
! 200   \\[enlight/fheal/lev/poly/speed]
! 250   \\[acid/oil]
! 300   \\[g.able/g.level/paralysis]

! 0     \\[uncursed water]
! 100   \\[holy/unholy]
"""

RINGS = """
= 100 others
= 150 others
= 200 \\[fire/f.action/lev/regen/search/s.digest/tport]
= 300 \\[conflict/poly/poly.ctrl/tport.ctrl]
"""

WANDS = """
/ 200 \\[cancel/c.monster/poly/tport]
/ 500 \\[death/wish]
"""

TOOLS = """
( 10 \\[oil lamp]
( 50 \\[magic lamp]

( 2   \\[sack]
( 100 \\[oilskin/tricks/holding]
"""

BOOTS = """
[ 8  \\[elven/kick]
[ 30 \\[fumble/lev]
[ 50 \\[jump/speed/water]
"""

PANEL_OVERHEAD = 4


def rendered_len(line: str) -> int:
    return len(line.replace("\\[", "["))


def max_content_width(*texts: str) -> int:
    return max(
        rendered_len(line)
        for text in texts
        for line in text.strip().splitlines()
        if line.strip()
    )


def modifier(char: int) -> float:
    """Modifier based on charisma"""
    if char <= 5:
        return 2.0
    if char <= 7:
        return 1 + (1 / 2)
    if char <= 10:
        return 1 + (1 / 3)
    if char <= 15:
        return 1.0
    if char <= 17:
        return 3 / 4
    if char == 18:
        return 2 / 3
    return 1 / 2


def buy_prices(char: int, base: int) -> set[int]:
    """Return set of purchase prices"""
    m = modifier(char)
    prices = set()
    prices.add(int((base * m) + 0.5))
    prices.add(int((base * m * (1 + (1 / 3))) + 0.5))
    return prices


def sell_prices(char: int, base: int) -> set[int]:
    """Return set of sale prices"""
    prices = set()
    prices.add(int((base * (1 / 2)) + 0.5))
    prices.add(int((base * (1 / 2) * (3 / 4)) + 0.5))
    return prices


def panel_height(text: str) -> int:
    return text.count("\n") + 3


def main():
    """Main entrypoint"""

    parser = argparse.ArgumentParser(description="Nethack Price ID")
    parser.add_argument("-c", "--cha", type=int, default=10, help="Charisma")
    args = parser.parse_args()

    table = Table(caption=f"Prices for Charisma [bold][red]{args.cha}")

    table.add_column("Base", justify="right", style="cyan", no_wrap=True)
    table.add_column("Buy", style="magenta")
    table.add_column("Sell", justify="right", style="green")

    for base in BASES:
        table.add_row(
            str(base),
            ", ".join(str(p) for p in sorted(buy_prices(args.cha, base))),
            ", ".join(str(p) for p in sorted(sell_prices(args.cha, base))),
        )
    left_width = max_content_width(TOOLS, BOOTS) + PANEL_OVERHEAD
    right_width = max_content_width(SCROLLS, POTIONS, RINGS, WANDS) + PANEL_OVERHEAD

    total_height = sum(panel_height(t) for t in [SCROLLS, POTIONS, RINGS, WANDS])

    console = Console(width=left_width + right_width, height=total_height)

    layout = Layout()
    layout.split_row(
        Layout(name="left", size=left_width), Layout(name="right", size=right_width)
    )
    layout["left"].split_column(
        Layout(table, name="price_table"),
        Layout(
            Panel(TOOLS, title="Tools", title_align="left"),
            name="tools",
            size=TOOLS.count("\n") + 3,
        ),
        Layout(
            Panel(BOOTS, title="Boots", title_align="left"),
            name="boots",
            size=BOOTS.count("\n") + 3,
        ),
    )
    layout["right"].split_column(
        Layout(
            Panel(SCROLLS, title="Scrolls", title_align="left"),
            name="scrolls",
            size=SCROLLS.count("\n") + 3,
        ),
        Layout(
            Panel(POTIONS, title="Potions", title_align="left"),
            name="potions",
            size=POTIONS.count("\n") + 3,
        ),
        Layout(
            Panel(RINGS, title="Rings", title_align="left"),
            name="rings",
            size=RINGS.count("\n") + 3,
        ),
        Layout(
            Panel(WANDS, title="Wands", title_align="left"),
            name="wands",
            size=WANDS.count("\n") + 3,
        ),
    )

    console.print(layout)
