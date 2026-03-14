#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import re
import struct
import termios
from pathlib import Path

from textual.app import App, ComposeResult
from textual import events
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, DataTable, Input
from textual.reactive import reactive
from rich.table import Table as RichTable
from rich.text import Text

from priceid.pid import (
    BASES,
    SCROLLS,
    POTIONS,
    RINGS,
    WANDS,
    TOOLS,
    BOOTS,
    buy_prices,
    sell_prices,
)

HINTS = (
    " [bold]p[/]:Price  [bold]b[/]:Buy  [bold]s[/]:Sell"
    "  [bold]i[/]:Identify  [bold]c[/]:Charisma  [bold]d[/]:Discovered"
    "  [bold]?[/]:Legend  [bold]R[/]:Reset  [bold]q[/]:Quit"
)

MIN_WIDTH = 105
MIN_HEIGHT = 35

STATE_PATH = Path.home() / ".config" / "priceid" / "state.json"

PANELS = {
    "scrolls-panel": SCROLLS,
    "potions-panel": POTIONS,
    "rings-panel": RINGS,
    "wands-panel": WANDS,
    "tools-panel": TOOLS,
    "boots-panel": BOOTS,
}

def _query_terminal_size() -> tuple[int, int]:
    """Query actual terminal dimensions via /dev/tty, bypassing fd redirections."""
    try:
        with open("/dev/tty", "r") as tty:
            result = fcntl.ioctl(tty.fileno(), termios.TIOCGWINSZ, b"\x00" * 8)
            rows, cols, _, _ = struct.unpack("HHHH", result)
            return cols, rows
    except OSError:
        return 80, 24


LEGEND: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("Scrolls", (
        ("amnesia", "Amnesia"),
        ("c.monster", "Create Monster"),
        ("charge", "Charging"),
        ("conf", "Confuse Monster"),
        ("d.armor", "Destroy Armor"),
        ("e.armor", "Enchant Armor"),
        ("e.weapon", "Enchant Weapon"),
        ("earth", "Earth"),
        ("fdet", "Food Detection"),
        ("fire", "Fire"),
        ("gdet", "Gold Detection"),
        ("geno", "Genocide"),
        ("identify", "Identify"),
        ("light", "Light"),
        ("map", "Magic Mapping"),
        ("punish", "Punishment"),
        ("r.curse", "Remove Curse"),
        ("scare", "Scare Monster"),
        ("stink", "Stinking Cloud"),
        ("tame", "Taming"),
        ("tport", "Teleportation"),
    )),
    ("Potions", (
        ("acid", "Acid"),
        ("blind", "Blindness"),
        ("booze", "Booze"),
        ("conf", "Confusion"),
        ("enlight", "Enlightenment"),
        ("fheal", "Full Healing"),
        ("fruit", "Fruit Juice"),
        ("g.able", "Gain Ability"),
        ("g.energy", "Gain Energy"),
        ("g.level", "Gain Level"),
        ("hall", "Hallucination"),
        ("heal", "Healing"),
        ("holy", "Holy Water"),
        ("inv", "Invisibility"),
        ("lev", "Levitation"),
        ("mdet", "Monster Detection"),
        ("odet", "Object Detection"),
        ("oil", "Oil"),
        ("paralysis", "Paralysis"),
        ("poly", "Polymorph"),
        ("r.able", "Restore Ability"),
        ("s.inv", "See Invisible"),
        ("sick", "Sickness"),
        ("sleep", "Sleeping"),
        ("speed", "Speed"),
        ("uncursed water", "Uncursed Water"),
        ("unholy", "Unholy Water"),
        ("xheal", "Extra Healing"),
    )),
    ("Rings", (
        ("conflict", "Conflict"),
        ("f.action", "Free Action"),
        ("fire", "Fire Resistance"),
        ("lev", "Levitation"),
        ("poly", "Polymorph"),
        ("poly.ctrl", "Polymorph Control"),
        ("regen", "Regeneration"),
        ("s.digest", "Slow Digestion"),
        ("search", "Searching"),
        ("tport", "Teleportation"),
        ("tport.ctrl", "Teleport Control"),
    )),
    ("Wands", (
        ("c.monster", "Create Monster"),
        ("cancel", "Cancellation"),
        ("death", "Death"),
        ("poly", "Polymorph"),
        ("tport", "Teleportation"),
        ("wish", "Wishing"),
    )),
    ("Tools", (
        ("holding", "Bag of Holding"),
        ("magic lamp", "Magic Lamp"),
        ("oil lamp", "Oil Lamp"),
        ("oilskin", "Oilskin Sack"),
        ("sack", "Sack"),
        ("tricks", "Bag of Tricks"),
    )),
    ("Boots", (
        ("elven", "Elven Boots"),
        ("fumble", "Boots of Fumbling"),
        ("jump", "Jumping Boots"),
        ("kick", "Kicking Boots"),
        ("lev", "Levitation Boots"),
        ("speed", "Speed Boots"),
        ("water", "Water Walking Boots"),
    )),
)

_LINE_BASES_RE = re.compile(r"^[?!=/(\[]\s+(\d+(?:/\d+)*)")


def parse_line_bases(line: str) -> list[int]:
    """Extract base price(s) from a panel line like '? 60/80 \\[items]'.

    Handles shorthand: when a later part has fewer digits than the first,
    it represents the leading digits at the same magnitude.
    E.g. '150/2' -> [150, 200]  (2 * 10^(3-1) = 200)
         '60/80' -> [60, 80]    (same length, no expansion)
    """
    m = _LINE_BASES_RE.match(line)
    if not m:
        return []
    parts = m.group(1).split("/")
    first = parts[0]
    result = [int(first)]
    for p in parts[1:]:
        if len(p) < len(first):
            result.append(int(p) * 10 ** (len(first) - len(p)))
        else:
            result.append(int(p))
    return result


def parse_line_parts(line: str) -> tuple[str, list[str]]:
    """Split a panel line into (prefix, [items]).

    '? 100   \\[conf/d.armor]'  ->  ('? 100   ', ['conf', 'd.armor'])
    '= 100 others'              ->  ('= 100 others', [])
    """
    idx = line.find("\\[")
    if idx == -1:
        return line.replace("\\[", "["), []
    close = line.find("]", idx + 2)
    if close == -1:
        return line.replace("\\[", "["), []
    return line[:idx], line[idx + 2 : close].split("/")


def _highlighted_line_indices(
    lines: list[str], matching_bases: set[int]
) -> set[int]:
    """Determine which panel lines to highlight using maximal matching.

    A line is a candidate if ALL of its bases are in matching_bases.
    Among candidates, only keep maximal ones -- drop any line whose base set
    is a strict subset of another candidate's base set.  This ensures that
    e.g. when both base 60 and 80 match, only the '60/80' line highlights
    (not the standalone '60' or '80' lines).
    """
    line_bases = [set(parse_line_bases(line)) for line in lines]
    candidates = {
        i for i, bases in enumerate(line_bases) if bases and bases <= matching_bases
    }
    return {
        i
        for i in candidates
        if not any(line_bases[i] < line_bases[j] for j in candidates if j != i)
    }


ALL_ITEMS: set[str] = set()
for _raw in PANELS.values():
    for _line in _raw.strip().splitlines():
        _, _items = parse_line_parts(_line)
        ALL_ITEMS.update(_items)


def build_panel_text(
    raw_text: str,
    highlighted_bases: set[int] | None = None,
    identified: set[str] | None = None,
    show_identified: bool = True,
    identify_filter: str = "",
) -> Text:
    """Build a Rich Text object for an item panel with full styling."""
    lines = raw_text.strip().splitlines()
    hl = (
        _highlighted_line_indices(lines, highlighted_bases)
        if highlighted_bases
        else set()
    )
    identified = identified or set()
    result = Text()
    first_visible = True

    for i, line in enumerate(lines):
        if not line.strip():
            if not first_visible:
                result.append("\n")
            continue

        prefix, items = parse_line_parts(line)
        line_hl = i in hl

        if items:
            visible = [
                it for it in items if it not in identified or show_identified
            ]
            if not visible:
                continue

            if not first_visible:
                result.append("\n")
            first_visible = False

            base_style = "bold reverse" if line_hl else ""
            result.append(prefix + "[", style=base_style)
            for j, item in enumerate(visible):
                if j > 0:
                    result.append("/", style=base_style)
                if identify_filter and item.startswith(identify_filter):
                    style = "bold reverse"
                elif line_hl:
                    style = (
                        "bold reverse dim strike"
                        if item in identified
                        else "bold reverse"
                    )
                elif item in identified:
                    style = "dim strike"
                else:
                    style = base_style
                result.append(item, style=style)
            result.append("]", style=base_style)
        else:
            if not first_visible:
                result.append("\n")
            first_visible = False
            display = line.replace("\\[", "[")
            result.append(display, style="bold reverse" if line_hl else "")

    return result


LEGEND_COL_WIDTH = 40


def build_legend(width: int) -> RichTable:
    """Build a multi-column Rich Table renderable for the item legend."""
    num_cols = max(1, width // LEGEND_COL_WIDTH)

    col_width = min(LEGEND_COL_WIDTH, width // num_cols) if num_cols > 1 else width
    separator = "─" * (col_width - 2)

    col_cats: list[list[int]] = [[] for _ in range(num_cols)]
    col_heights = [0] * num_cols
    for i, (_, items) in enumerate(LEGEND):
        shortest = min(range(num_cols), key=lambda c: col_heights[c])
        col_cats[shortest].append(i)
        col_heights[shortest] += 1 + len(items) + 2

    col_texts: list[Text] = []
    for cats in col_cats:
        text = Text()
        for j, cat_idx in enumerate(cats):
            if j > 0:
                text.append(f" {separator}\n", style="dim")
            category, items = LEGEND[cat_idx]
            text.append(" ")
            text.append(category, style="bold cyan")
            text.append("\n")
            for short, full in items:
                text.append(f"   {short:<16}", style="bold")
                text.append(f"{full}\n")
        col_texts.append(text)

    table = RichTable(box=None, show_header=False, padding=(0, 2), expand=True)
    for _ in range(num_cols):
        table.add_column(vertical="top")
    table.add_row(*col_texts)
    return table


class PriceApp(App):
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #main {
        height: 1fr;
    }

    #left-col {
        width: 1fr;
        min-width: 30;
    }

    #right-col {
        width: 2fr;
        min-width: 55;
    }

    #price-table {
        height: auto;
        border: solid $accent;
        background: transparent;
    }

    #price-table > .datatable--header {
        background: transparent;
    }

    .item-panel {
        height: auto;
        border: solid $accent;
        padding: 0 1;
    }

    #status-bar {
        height: 1;
        dock: bottom;
        background: $boost;
        padding: 0 1;
    }

    #mode-input {
        dock: bottom;
        display: none;
    }

    #legend {
        display: none;
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
    }

    #size-warning {
        display: none;
        width: 1fr;
        height: 1fr;
        content-align: center middle;
        text-align: center;
    }

    .too-small #main,
    .too-small #status-bar,
    .too-small #mode-input,
    .too-small #legend {
        display: none;
    }

    .too-small #size-warning {
        display: block;
    }
    """

    charisma: reactive[int] = reactive(10)

    def bell(self) -> None:
        pass

    def __init__(self):
        super().__init__()
        self._active_mode: str | None = None
        self._identified: set[str] = set()
        self._show_identified: bool = True
        self._initial_prompt: bool = False
        self._last_term_size: tuple[int, int] = (0, 0)

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            with Vertical(id="left-col"):
                yield DataTable(id="price-table", show_cursor=False)
                tools = Static("", id="tools-panel", classes="item-panel")
                tools.border_title = "Tools"
                yield tools
                boots = Static("", id="boots-panel", classes="item-panel")
                boots.border_title = "Boots"
                yield boots
            with Vertical(id="right-col"):
                scrolls = Static("", id="scrolls-panel", classes="item-panel")
                scrolls.border_title = "Scrolls"
                yield scrolls
                potions = Static("", id="potions-panel", classes="item-panel")
                potions.border_title = "Potions"
                yield potions
                rings = Static("", id="rings-panel", classes="item-panel")
                rings.border_title = "Rings"
                yield rings
                wands = Static("", id="wands-panel", classes="item-panel")
                wands.border_title = "Wands"
                yield wands
        legend = VerticalScroll(Static(id="legend-content"), id="legend")
        legend.border_title = "Legend"
        legend.border_subtitle = (
            "Scroll: [bold]j[/]/[bold]k[/]  [bold]^D[/]/[bold]^U[/]"
            "  Close: [bold]?[/]/[bold]ESC[/]"
        )
        yield legend
        yield Input(id="mode-input")
        yield Static(HINTS, id="status-bar")
        yield Static("", id="size-warning")

    def on_mount(self) -> None:
        state = self._load_state()
        if state:
            self._identified = set(state.get("identified", []))
            self._show_identified = state.get("show_identified", True)
            self.charisma = state.get("charisma", 10)
        else:
            self.charisma = 10
            self._initial_prompt = True
        self._build_table()
        self._update_panels()
        self._refresh_status_bar()
        self._check_size()
        self.set_interval(0.25, self._check_size)
        if self._initial_prompt:
            self._enter_mode(
                "charisma",
                "Enter charisma (1-25), default 10...",
                restrict=r"[0-9]*",
            )

    def _check_size(self) -> None:
        w, h = _query_terminal_size()
        current = (w, h)
        if current == self._last_term_size:
            return
        self._last_term_size = current
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            self.query_one("#size-warning", Static).update(
                f"Terminal too small: {w}x{h}\n\nNeed at least {MIN_WIDTH}x{MIN_HEIGHT}\n\nResize to continue."
            )
            self.add_class("too-small")
        else:
            self.remove_class("too-small")
        if self._active_mode == "legend":
            self._rebuild_legend()

    def _load_state(self) -> dict | None:
        if not STATE_PATH.exists():
            return None
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _save_state(self) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "charisma": self.charisma,
            "identified": sorted(self._identified),
            "show_identified": self._show_identified,
        }
        STATE_PATH.write_text(json.dumps(data, indent=2) + "\n")

    def _reset_state(self) -> None:
        self._identified.clear()
        self._show_identified = True
        self.charisma = 10
        self._build_table()
        self._update_panels()
        STATE_PATH.unlink(missing_ok=True)
        self._initial_prompt = True
        self._enter_mode(
            "charisma",
            "Enter charisma (1-25), default 10...",
            restrict=r"[0-9]*",
        )

    def _build_table(self, highlighted_bases: set[int] | None = None) -> None:
        table = self.query_one("#price-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Base", "Buy", "Sell")
        for base in BASES:
            buy = ", ".join(str(p) for p in sorted(buy_prices(self.charisma, base)))
            sell = ", ".join(str(p) for p in sorted(sell_prices(self.charisma, base)))
            if highlighted_bases and base in highlighted_bases:
                hl = "bold reverse"
                table.add_row(
                    Text(str(base), style=hl),
                    Text(buy, style=hl),
                    Text(sell, style=hl),
                )
            else:
                table.add_row(
                    Text(str(base), style="cyan"),
                    Text(buy, style="magenta"),
                    Text(sell, style="green"),
                )
        table.border_title = f"Prices for Charisma [bold red]{self.charisma}[/]"

    def _update_panels(
        self,
        highlighted_bases: set[int] | None = None,
        identify_filter: str = "",
    ) -> None:
        for panel_id, raw_text in PANELS.items():
            self.query_one(f"#{panel_id}", Static).update(
                build_panel_text(
                    raw_text,
                    highlighted_bases=highlighted_bases,
                    identified=self._identified,
                    show_identified=self._show_identified,
                    identify_filter=identify_filter,
                )
            )

    def _refresh_status_bar(self) -> None:
        text = HINTS
        if not self._show_identified:
            text += f"  [dim]| {len(self._identified)} hidden[/]"
        self.query_one("#status-bar", Static).update(text)

    def watch_charisma(self, new_value: int) -> None:
        if self.is_mounted:
            self._build_table()

    def _enter_mode(
        self, mode: str, placeholder: str, restrict: str | None = None
    ) -> None:
        self._active_mode = mode
        inp = self.query_one("#mode-input", Input)
        inp.placeholder = placeholder
        inp.value = ""
        inp.restrict = restrict
        inp.display = True
        self.query_one("#status-bar").display = False
        inp.focus()

    def _exit_mode(self) -> None:
        was_initial = self._initial_prompt and self._active_mode == "charisma"
        if self._active_mode in ("buy", "sell", "base"):
            self._build_table()
        self._active_mode = None
        self._initial_prompt = False
        inp = self.query_one("#mode-input", Input)
        inp.display = False
        inp.value = ""
        self._update_panels()
        self.query_one("#status-bar").display = True
        self._refresh_status_bar()
        if was_initial:
            self._save_state()

    def _show_legend(self) -> None:
        self._active_mode = "legend"
        self.query_one("#main").display = False
        self.query_one("#status-bar").display = False
        legend = self.query_one("#legend", VerticalScroll)
        legend.display = True
        self.call_after_refresh(self._rebuild_legend)
        legend.scroll_home(animate=False)
        legend.focus()

    def _rebuild_legend(self) -> None:
        content_width = _query_terminal_size()[0] - 4
        self.query_one("#legend-content", Static).update(
            build_legend(content_width)
        )

    def _hide_legend(self) -> None:
        self._active_mode = None
        self.query_one("#legend").display = False
        self.query_one("#main").display = True
        self.query_one("#status-bar").display = True
        self._refresh_status_bar()

    def _do_base_search(self, value: str) -> None:
        if not value:
            self._build_table()
            self._update_panels()
            return
        try:
            price = int(value)
        except ValueError:
            return
        matching_bases = {b for b in BASES if b == price}
        self._build_table(highlighted_bases=matching_bases)
        self._update_panels(highlighted_bases=matching_bases)

    def _do_price_search(self, value: str) -> None:
        if not value:
            self._build_table()
            self._update_panels()
            return
        try:
            price = int(value)
        except ValueError:
            return
        matching_bases: set[int] = set()
        for base in BASES:
            if self._active_mode == "buy":
                prices = buy_prices(self.charisma, base)
            else:
                prices = sell_prices(self.charisma, base)
            if price in prices:
                matching_bases.add(base)
        self._build_table(highlighted_bases=matching_bases)
        self._update_panels(highlighted_bases=matching_bases)

    def _toggle_identified(self, text: str) -> None:
        if text in ALL_ITEMS:
            self._identified.symmetric_difference_update({text})
            return
        matches = [item for item in ALL_ITEMS if item.startswith(text)]
        if len(matches) == 1:
            self._identified.symmetric_difference_update(matches)

    def on_key(self, event: events.Key) -> None:
        if self._active_mode == "legend":
            legend = self.query_one("#legend", VerticalScroll)
            match event.key:
                case "escape" | "question_mark":
                    self._hide_legend()
                    event.stop()
                case "j":
                    legend.scroll_down(animate=False)
                    event.stop()
                case "k":
                    legend.scroll_up(animate=False)
                    event.stop()
                case "ctrl+d":
                    legend.scroll_relative(
                        y=legend.size.height // 2, animate=False
                    )
                    event.stop()
                case "ctrl+u":
                    legend.scroll_relative(
                        y=-(legend.size.height // 2), animate=False
                    )
                    event.stop()
            return

        if self._active_mode == "reset_confirm":
            if event.key == "y":
                self._reset_state()
            else:
                self._active_mode = None
                self._refresh_status_bar()
            event.stop()
            return

        if self._active_mode:
            if event.key == "escape":
                self._exit_mode()
                event.stop()
            return

        match event.key:
            case "p":
                self._enter_mode("base", "Base price...", restrict=r"[0-9]*")
                event.stop()
            case "b":
                self._enter_mode("buy", "Buy price...", restrict=r"[0-9]*")
                event.stop()
            case "s":
                self._enter_mode("sell", "Sell price...", restrict=r"[0-9]*")
                event.stop()
            case "i":
                self._enter_mode("identify", "Item name...")
                event.stop()
            case "c":
                self._enter_mode(
                    "charisma", "Enter charisma (1-25)...", restrict=r"[0-9]*"
                )
                event.stop()
            case "d":
                self._show_identified = not self._show_identified
                self._update_panels()
                self._refresh_status_bar()
                self._save_state()
                event.stop()
            case "question_mark":
                self._show_legend()
                event.stop()
            case "R":
                self._active_mode = "reset_confirm"
                self.query_one("#status-bar", Static).update(
                    " Reset all state? [bold]y[/]:Yes  [bold]n[/]/[bold]ESC[/]:Cancel"
                )
                event.stop()
            case "q":
                self.exit()
                event.stop()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._active_mode in ("buy", "sell"):
            self._do_price_search(event.value)
        elif self._active_mode == "base":
            self._do_base_search(event.value)
        elif self._active_mode == "identify":
            self._update_panels(identify_filter=event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        save = False
        if self._active_mode == "charisma" and event.value:
            try:
                val = int(event.value)
                if 1 <= val <= 25:
                    self.charisma = val
                    save = True
            except ValueError:
                pass
        elif self._active_mode == "identify" and event.value:
            before = len(self._identified)
            self._toggle_identified(event.value)
            save = len(self._identified) != before
        self._exit_mode()
        if save:
            self._save_state()
