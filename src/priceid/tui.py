#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from textual.app import App, ComposeResult
from textual import events
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, DataTable, Input
from textual.reactive import reactive
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
    " [bold]b[/]:Buy  [bold]s[/]:Sell  [bold]i[/]:Identify"
    "  [bold]c[/]:Charisma  [bold]d[/]:Discovered"
    "  [bold]R[/]:Reset  [bold]q[/]:Quit"
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

    #size-warning {
        display: none;
        width: 1fr;
        height: 1fr;
        content-align: center middle;
        text-align: center;
    }

    .too-small #main,
    .too-small #status-bar,
    .too-small #mode-input {
        display: none;
    }

    .too-small #size-warning {
        display: block;
    }
    """

    charisma: reactive[int] = reactive(10)

    def __init__(self):
        super().__init__()
        self._active_mode: str | None = None
        self._identified: set[str] = set()
        self._show_identified: bool = True
        self._initial_prompt: bool = False

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
        if self._initial_prompt:
            self._enter_mode(
                "charisma",
                "Enter charisma (1-25), default 10...",
                restrict=r"[0-9]*",
            )

    def on_resize(self, event: events.Resize) -> None:
        self._check_size()

    def _check_size(self) -> None:
        w, h = self.size
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            self.query_one("#size-warning", Static).update(
                f"Terminal too small: {w}x{h}\n\nNeed at least {MIN_WIDTH}x{MIN_HEIGHT}\n\nResize to continue."
            )
            self.add_class("too-small")
        else:
            self.remove_class("too-small")

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
        if self._active_mode in ("buy", "sell"):
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
