#!/usr/bin/env python3
"""A dependency-free Klondike solitaire game for the terminal."""

from __future__ import annotations

import copy
import curses
import os
import random
import sys
import time
from dataclasses import dataclass


SUITS = ("♠", "♥", "♦", "♣")
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
RED_SUITS = {"♥", "♦"}
CARD_W, CARD_H, GAP, DOWN_STEP, UP_STEP = 5, 5, 1, 1, 1
APP_VERSION = "1.0.0"
APP_CREATOR = "GRAAAA"
APP_NAME = "solitaire_terminal"
TERMINAL_WIDTH, TERMINAL_HEIGHT = 42, 24


def first_run_marker() -> str:
    """Return the per-user marker used to remember that help was shown."""
    state_home = os.environ.get("XDG_STATE_HOME")
    if not state_home:
        state_home = os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(state_home, APP_NAME, "help_seen")


def is_first_run() -> bool:
    return not os.path.exists(first_run_marker())


def remember_help_seen() -> None:
    marker = first_run_marker()
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "a", encoding="utf-8"):
            pass
    except OSError:
        # A read-only home directory should not prevent the game from starting.
        pass


def request_terminal_size() -> None:
    """Ask compatible terminal emulators to resize to the game's canvas."""
    if sys.stdout.isatty():
        sys.stdout.write(f"\033[8;{TERMINAL_HEIGHT};{TERMINAL_WIDTH}t")
        sys.stdout.flush()


@dataclass
class Card:
    suit: str
    rank: str
    value: int
    face_up: bool = False

    @property
    def red(self) -> bool:
        return self.suit in RED_SUITS

    @property
    def label(self) -> str:
        return f"{self.rank}{self.suit}"


class Game:
    def __init__(self) -> None:
        self.history: list[tuple] = []
        self.new()

    def new(self) -> None:
        deck = [Card(s, r, n + 1) for s in SUITS for n, r in enumerate(RANKS)]
        random.shuffle(deck)
        self.tableau: list[list[Card]] = [[] for _ in range(7)]
        for col in range(7):
            for row in range(col + 1):
                card = deck.pop()
                card.face_up = row == col
                self.tableau[col].append(card)
        self.stock = deck
        self.waste: list[Card] = []
        self.foundations: list[list[Card]] = [[] for _ in range(4)]
        self.score = self.moves = 0
        self.started = time.monotonic()
        self.history.clear()
        self.message = "New deal ready. Press D to draw."

    def save(self) -> None:
        snap = (
            copy.deepcopy(self.stock), copy.deepcopy(self.waste),
            copy.deepcopy(self.foundations), copy.deepcopy(self.tableau),
            self.score, self.moves, self.message,
        )
        self.history.append(snap)
        if len(self.history) > 100:
            self.history.pop(0)

    def undo(self) -> None:
        if not self.history:
            self.message = "Nothing to undo."
            return
        (self.stock, self.waste, self.foundations, self.tableau,
         self.score, self.moves, _) = self.history.pop()
        self.message = "Last move reverted."

    def draw(self) -> None:
        if self.stock:
            self.save()
            card = self.stock.pop()
            card.face_up = True
            self.waste.append(card)
            self.moves += 1
            self.message = f"Drew {card.label}."
        elif self.waste:
            self.save()
            self.stock = list(reversed(self.waste))
            for card in self.stock:
                card.face_up = False
            self.waste.clear()
            self.score = max(0, self.score - 20)
            self.moves += 1
            self.message = "Waste returned to stock."
        else:
            self.message = "No cards left in the stock."

    def expose(self, col: int) -> None:
        if self.tableau[col] and not self.tableau[col][-1].face_up:
            self.tableau[col][-1].face_up = True
            self.score += 5

    def can_tableau(self, card: Card, col: int) -> bool:
        if not self.tableau[col]:
            return card.value == 13
        top = self.tableau[col][-1]
        return top.face_up and top.red != card.red and top.value == card.value + 1

    def can_foundation(self, card: Card, foundation: int) -> bool:
        pile = self.foundations[foundation]
        return card.suit == SUITS[foundation] and card.value == len(pile) + 1

    def move_tableau(self, src: tuple[str, int, int], dest: int) -> bool:
        kind, pile, index = src
        if kind == "tableau":
            cards = self.tableau[pile][index:]
            if pile == dest:
                return False
        elif kind == "waste" and self.waste:
            cards = [self.waste[-1]]
        elif kind == "foundation" and self.foundations[pile]:
            cards = [self.foundations[pile][-1]]
        else:
            return False
        if not cards or not self.can_tableau(cards[0], dest):
            return False
        self.save()
        if kind == "tableau":
            del self.tableau[pile][index:]
            self.expose(pile)
        elif kind == "waste":
            self.waste.pop()
            self.score += 5
        else:
            self.foundations[pile].pop()
            self.score = max(0, self.score - 5)
        self.tableau[dest].extend(cards)
        self.moves += 1
        self.message = f"Moved {cards[0].label} to column {dest + 1}."
        return True

    def move_foundation(self, src: tuple[str, int, int], dest: int) -> bool:
        kind, pile, index = src
        if kind == "waste" and self.waste:
            card = self.waste[-1]
        elif kind == "tableau" and self.tableau[pile] and index == len(self.tableau[pile]) - 1:
            card = self.tableau[pile][-1]
        else:
            return False
        if not self.can_foundation(card, dest):
            return False
        self.save()
        if kind == "waste":
            self.waste.pop()
        else:
            self.tableau[pile].pop()
            self.expose(pile)
        self.foundations[dest].append(card)
        self.score += 10
        self.moves += 1
        self.message = f"Filed {card.label} to its foundation."
        return True

    def auto_foundation(self, src: tuple[str, int, int]) -> bool:
        kind, pile, index = src
        card = None
        if kind == "waste" and self.waste:
            card = self.waste[-1]
        elif kind == "tableau" and self.tableau[pile] and index == len(self.tableau[pile]) - 1:
            card = self.tableau[pile][-1]
        if card:
            return self.move_foundation(src, SUITS.index(card.suit))
        return False

    @property
    def won(self) -> bool:
        return all(len(pile) == 13 for pile in self.foundations)


class UI:
    def __init__(self, screen, first_run: bool = False) -> None:
        self.s = screen
        self.game = Game()
        self.zone = "tableau"
        self.cursor = 0
        self.depth = 0
        self.selected: tuple[str, int, int] | None = None
        self.deal_progress: int | None = None
        self.help_visible = False
        self.first_run = first_run
        self.running = True
        self.init_screen()

    def init_screen(self) -> None:
        curses.curs_set(0)
        self.s.timeout(250)
        self.s.keypad(True)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_RED, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)
            curses.init_pair(4, curses.COLOR_RED, curses.COLOR_WHITE)
            curses.init_pair(5, curses.COLOR_GREEN, -1)

    def safe_add(self, y: int, x: int, text: str, attr=0) -> None:
        h, w = self.s.getmaxyx()
        if 0 <= y < h and x < w:
            try:
                self.s.addnstr(y, max(0, x), text, max(0, w - max(0, x) - 1), attr)
            except curses.error:
                pass

    def box(self, y: int, x: int, title: str = "", active=False, dashed=False) -> None:
        attr = (curses.color_pair(2) | curses.A_BOLD) if active else curses.A_DIM
        top = "╭" + "─" * (CARD_W - 2) + "╮"
        self.safe_add(y, x, top, attr)
        for n in range(1, CARD_H - 1):
            self.safe_add(y + n, x, "│" + " " * (CARD_W - 2) + "│", attr)
        self.safe_add(y + CARD_H - 1, x, "╰" + "─" * (CARD_W - 2) + "╯", attr)
        if title:
            self.safe_add(y + 2, x + (CARD_W - len(title)) // 2, title, attr)

    def card(self, y: int, x: int, card: Card, active=False, selected=False, partial=False) -> None:
        border = (curses.color_pair(2) | curses.A_BOLD) if selected else (
            curses.A_BOLD if active else curses.A_DIM
        )
        ink = curses.color_pair(1) if card.red else curses.A_NORMAL
        if active or selected:
            ink |= curses.A_BOLD
        if partial:
            self.safe_add(y, x, "╭───╮", border)
            if card.face_up:
                self.safe_add(y, x + 1, card.label, ink)
            return
        if not card.face_up:
            rows = ["╭───╮", "│╱╱╱│", "│╱╱╱│", "│╱╱╱│", "╰───╯"]
            for n, row in enumerate(rows):
                self.safe_add(y + n, x, row, border)
        else:
            rows = ["╭───╮", "│   │", "│   │", "│   │", "╰───╯"]
            for n, row in enumerate(rows):
                self.safe_add(y + n, x, row, border)
            self.safe_add(y + 1, x + 1, card.label, ink)
            self.safe_add(y + 3, x + 1, f"{card.suit}{card.rank}".rjust(3), ink)

    def selected_here(self, kind: str, pile: int, index: int) -> bool:
        if not self.selected:
            return False
        sk, sp, si = self.selected
        return sk == kind and sp == pile and index >= si

    def draw(self) -> None:
        self.s.erase()
        h, w = self.s.getmaxyx()
        if h < TERMINAL_HEIGHT or w < TERMINAL_WIDTH:
            self.safe_add(1, 1, f"Solitaire needs a terminal at least {TERMINAL_WIDTH} x {TERMINAL_HEIGHT}.", curses.A_BOLD)
            self.safe_add(3, 2, f"Current size: {w} x {h}. Resize the window or press Q to quit.")
            self.s.refresh()
            return
        board_w = 7 * CARD_W + 6 * GAP
        ox = max(0, (w - board_w) // 2)
        top_y = 0
        stock_active = self.zone == "top" and self.cursor == 0
        if self.game.stock:
            self.card(top_y, ox, self.game.stock[-1], stock_active, False)
        else:
            self.box(top_y, ox, "↻", stock_active, True)
        wx = ox + CARD_W + GAP
        waste_active = self.zone == "top" and self.cursor == 1
        if self.game.waste:
            self.card(top_y, wx, self.game.waste[-1], waste_active,
                      self.selected_here("waste", 0, len(self.game.waste) - 1))
        else:
            self.box(top_y, wx, "", waste_active, True)
        fx = ox + board_w - (CARD_W * 4 + GAP * 3)
        for i, suit in enumerate(SUITS):
            x = fx + i * (CARD_W + GAP)
            active = self.zone == "top" and self.cursor == i + 2
            if self.game.foundations[i]:
                idx = len(self.game.foundations[i]) - 1
                self.card(top_y, x, self.game.foundations[i][-1], active,
                          self.selected_here("foundation", i, idx))
            else:
                self.box(top_y, x, suit, active, True)

        base_y = 6
        for col, pile in enumerate(self.game.tableau):
            x = ox + col * (CARD_W + GAP)
            shown = len(pile)
            if self.deal_progress is not None:
                first = col * (col + 1) // 2
                shown = max(0, min(len(pile), self.deal_progress - first))
            if shown == 0 and self.deal_progress is not None:
                continue
            if not pile:
                self.box(base_y, x, "K", self.zone == "tableau" and self.cursor == col, True)
                continue
            y = base_y
            chosen = self.tableau_index(col)
            for idx, card in enumerate(pile[:shown]):
                last = idx == shown - 1
                active = self.zone == "tableau" and self.cursor == col and idx == chosen
                partial = not last
                self.card(y, x, card, active, self.selected_here("tableau", col, idx), partial)
                y += DOWN_STEP if not card.face_up else UP_STEP

        tallest = max((len(pile) for pile in self.game.tableau), default=0)
        tableau_bottom = base_y + max(0, tallest - 1) + CARD_H - 1
        if tableau_bottom < h - 2:
            elapsed = int(time.monotonic() - self.game.started)
            footer_y = h - 2
            if w < 65:
                self.safe_add(footer_y, ox, ("> " + self.game.message)[:board_w], curses.A_DIM)
                compact = f"{self.game.score:03}p {elapsed//60:02}:{elapsed%60:02} {self.game.moves:03}m | ↵ d:draw ?:help q:quit"
                self.safe_add(footer_y + 1, ox, compact[:board_w], curses.A_DIM)
            else:
                prompt = "> "
                self.safe_add(footer_y, ox, prompt, curses.A_DIM)
                self.safe_add(footer_y, ox + len(prompt), self.game.message, curses.A_DIM)
                stats = f"{self.game.score:03}pts {elapsed//60:02}:{elapsed%60:02} {self.game.moves:03}mv"
                self.safe_add(footer_y, ox + board_w - len(stats), stats, curses.A_DIM)
                self.safe_add(footer_y + 1, ox, "arrows move · enter select · d draw · ? keys · q quit", curses.A_DIM)
        if self.help_visible:
            self.draw_help()
        self.s.refresh()

    def show_intro(self) -> None:
        """Fade the title in and out, followed by the creator credit."""
        frames = (
            ("solitaire terminal", curses.A_DIM),
            ("solitaire terminal", curses.A_NORMAL),
            ("solitaire terminal", curses.A_BOLD),
            ("solitaire terminal", curses.A_NORMAL),
            ("solitaire terminal", curses.A_DIM),
            ("", curses.A_NORMAL),
            (f"by {APP_CREATOR}", curses.A_DIM),
            (f"by {APP_CREATOR}", curses.A_NORMAL),
            (f"by {APP_CREATOR}", curses.A_BOLD),
            (f"by {APP_CREATOR}", curses.A_NORMAL),
            (f"by {APP_CREATOR}", curses.A_DIM),
            ("", curses.A_NORMAL),
        )
        for line, attr in frames:
            self.s.erase()
            h, w = self.s.getmaxyx()
            self.safe_add(h // 2, max(0, (w - len(line)) // 2), line, attr)
            self.s.refresh()
            curses.napms(130)

    def animate_deal(self) -> None:
        """Cascade a fresh deal onto the tableau."""
        h, w = self.s.getmaxyx()
        if h < TERMINAL_HEIGHT or w < TERMINAL_WIDTH:
            return
        self.selected = None
        for count in range(1, 29):
            self.deal_progress = count
            self.draw()
            curses.napms(14)
        self.deal_progress = None
        self.draw()

    def tableau_index(self, col: int) -> int:
        pile = self.game.tableau[col]
        if not pile:
            return 0
        face = [i for i, c in enumerate(pile) if c.face_up]
        if not face:
            return len(pile) - 1
        return max(face[0], len(pile) - 1 - self.depth)

    def current_source(self) -> tuple[str, int, int] | None:
        if self.zone == "tableau":
            pile = self.game.tableau[self.cursor]
            if not pile:
                return None
            idx = self.tableau_index(self.cursor)
            return ("tableau", self.cursor, idx) if pile[idx].face_up else None
        if self.cursor == 1 and self.game.waste:
            return ("waste", 0, len(self.game.waste) - 1)
        if 2 <= self.cursor <= 5 and self.game.foundations[self.cursor - 2]:
            f = self.cursor - 2
            return ("foundation", f, len(self.game.foundations[f]) - 1)
        return None

    def board_origin(self) -> int:
        _, w = self.s.getmaxyx()
        return max(0, (w - (7 * CARD_W + 6 * GAP)) // 2)

    def source_cards(self, source: tuple[str, int, int]) -> list[Card]:
        kind, pile, index = source
        if kind == "tableau":
            return self.game.tableau[pile][index:]
        if kind == "waste" and self.game.waste:
            return [self.game.waste[-1]]
        if kind == "foundation" and self.game.foundations[pile]:
            return [self.game.foundations[pile][-1]]
        return []

    def pile_position(self, kind: str, pile: int, index: int = 0) -> tuple[int, int]:
        ox = self.board_origin()
        if kind == "tableau":
            return 6 + index, ox + pile * (CARD_W + GAP)
        if kind == "waste":
            return 0, ox + CARD_W + GAP
        foundation_x = ox + (7 * CARD_W + 6 * GAP) - (CARD_W * 4 + GAP * 3)
        return 0, foundation_x + pile * (CARD_W + GAP)

    def animate_motion(self, cards: list[Card], start: tuple[int, int], end: tuple[int, int]) -> None:
        """Move a card or sequence smoothly between two piles."""
        h, w = self.s.getmaxyx()
        if not cards or h < TERMINAL_HEIGHT or w < TERMINAL_WIDTH:
            return
        dy, dx = end[0] - start[0], end[1] - start[1]
        steps = max(3, min(9, max(abs(dx), abs(dy))))
        old_selection = self.selected
        self.selected = None
        for step in range(1, steps + 1):
            eased = 1 - (1 - step / steps) ** 2
            y = round(start[0] + dy * eased)
            x = round(start[1] + dx * eased)
            self.draw()
            for i, card in enumerate(cards):
                self.card(y + i, x, card, partial=i < len(cards) - 1)
            self.s.refresh()
            curses.napms(24)
        self.selected = old_selection

    def animate_flip(self, col: int) -> None:
        """Give a newly exposed tableau card a quick flip effect."""
        pile = self.game.tableau[col]
        h, w = self.s.getmaxyx()
        if not pile or h < TERMINAL_HEIGHT or w < TERMINAL_WIDTH:
            return
        y, x = self.pile_position("tableau", col, len(pile) - 1)
        old_selection = self.selected
        self.selected = None
        shapes = [
            (x + 1, ["╭─╮", "│ │", "│ │", "│ │", "╰─╯"]),
            (x + 2, ["│", "│", "│", "│", "│"]),
            (x + 1, ["╭─╮", "│ │", "│ │", "│ │", "╰─╯"]),
        ]
        for sx, rows in shapes:
            self.draw()
            for row in range(CARD_H):
                self.safe_add(y + row, x, " " * CARD_W)
                self.safe_add(y + row, sx, rows[row], curses.A_BOLD)
            self.s.refresh()
            curses.napms(35)
        self.selected = old_selection
        self.draw()

    def animated_draw(self) -> None:
        """Slide a card between stock and waste, then reveal or recycle it."""
        h, w = self.s.getmaxyx()
        if h < TERMINAL_HEIGHT or w < TERMINAL_WIDTH or (not self.game.stock and not self.game.waste):
            self.game.draw()
            self.selected = None
            return
        stock_x = self.board_origin()
        waste_x = stock_x + CARD_W + GAP
        recycling = not self.game.stock
        moving = copy.deepcopy(self.game.waste[-1] if recycling else self.game.stock[-1])
        self.selected = None
        start_x, end_x = (waste_x, stock_x) if recycling else (stock_x, waste_x)
        direction = 1 if end_x > start_x else -1
        for x in range(start_x + direction, end_x + direction, direction):
            if recycling and abs(x - start_x) > abs(end_x - start_x) // 2:
                moving.face_up = False
            self.draw()
            self.card(0, x, moving)
            self.s.refresh()
            curses.napms(28)
        self.game.draw()
        self.draw()

    def activate(self) -> None:
        if self.zone == "top" and self.cursor == 0:
            self.animated_draw()
            return
        if self.selected:
            moved = False
            if self.zone == "tableau":
                cards = self.source_cards(self.selected)
                kind, pile, index = self.selected
                legal = bool(cards) and not (kind == "tableau" and pile == self.cursor) and self.game.can_tableau(cards[0], self.cursor)
                will_expose = kind == "tableau" and index > 0 and not self.game.tableau[pile][index - 1].face_up
                if legal:
                    start = self.pile_position(kind, pile, index)
                    end = self.pile_position("tableau", self.cursor, len(self.game.tableau[self.cursor]))
                    self.animate_motion(cards, start, end)
                moved = self.game.move_tableau(self.selected, self.cursor)
                if moved and will_expose:
                    self.animate_flip(pile)
            elif self.cursor >= 2:
                cards = self.source_cards(self.selected)
                kind, pile, index = self.selected
                legal = len(cards) == 1 and kind != "foundation" and self.game.can_foundation(cards[0], self.cursor - 2)
                will_expose = kind == "tableau" and index > 0 and not self.game.tableau[pile][index - 1].face_up
                if legal:
                    start = self.pile_position(kind, pile, index)
                    end = self.pile_position("foundation", self.cursor - 2)
                    self.animate_motion(cards, start, end)
                moved = self.game.move_foundation(self.selected, self.cursor - 2)
                if moved and will_expose:
                    self.animate_flip(pile)
            if moved:
                self.selected = None
                self.depth = 0
            else:
                source = self.current_source()
                if source == self.selected:
                    self.selected = None
                    self.game.message = "Selection cleared."
                else:
                    self.game.message = "That move is not allowed."
            return
        source = self.current_source()
        if source:
            self.selected = source
            kind, pile, idx = source
            card = (self.game.waste[-1] if kind == "waste" else
                    self.game.foundations[pile][-1] if kind == "foundation" else
                    self.game.tableau[pile][idx])
            self.game.message = f"Selected {card.label}. Choose a destination."
        else:
            self.game.message = "There is no playable card here."

    def auto(self) -> None:
        source = self.selected or self.current_source()
        cards = self.source_cards(source) if source else []
        kind, pile, index = source if source else ("", 0, 0)
        legal = bool(cards) and len(cards) == 1 and kind != "foundation" and self.game.can_foundation(
            cards[0], SUITS.index(cards[0].suit)
        )
        will_expose = legal and kind == "tableau" and index > 0 and not self.game.tableau[pile][index - 1].face_up
        if legal:
            self.animate_motion(
                cards,
                self.pile_position(kind, pile, index),
                self.pile_position("foundation", SUITS.index(cards[0].suit)),
            )
        if source and self.game.auto_foundation(source):
            self.selected = None
            self.depth = 0
            if will_expose:
                self.animate_flip(pile)
        else:
            self.game.message = "That card cannot go to a foundation yet."

    def hint(self) -> None:
        if self.game.waste:
            c = self.game.waste[-1]
            if self.game.can_foundation(c, SUITS.index(c.suit)):
                self.game.message = f"Hint: send {c.label} to its foundation."
                return
            for col in range(7):
                if self.game.can_tableau(c, col):
                    self.game.message = f"Hint: move {c.label} to column {col + 1}."
                    return
        for src, pile in enumerate(self.game.tableau):
            for idx, c in enumerate(pile):
                if not c.face_up:
                    continue
                if idx == len(pile) - 1 and self.game.can_foundation(c, SUITS.index(c.suit)):
                    self.game.message = f"Hint: send {c.label} from column {src + 1} to its foundation."
                    return
                for dest in range(7):
                    if dest != src and self.game.can_tableau(c, dest):
                        self.game.message = f"Hint: move {c.label} from column {src + 1} to {dest + 1}."
                        return
        self.game.message = "Hint: draw a card." if self.game.stock or self.game.waste else "No move found."

    def draw_help(self) -> None:
        h, w = self.s.getmaxyx()
        rows = [
            ("ARROWS", "move / choose stack"),
            ("ENTER", "select / place"),
            ("D · SPACE", "draw / recycle"),
            ("A", "send to foundation"),
            ("H", "show a hint"),
            ("U", "undo move"),
            ("N", "new deal"),
            ("ESC", "clear selection"),
            ("?", "hide this help"),
            ("Q", "quit"),
        ]
        self.s.erase()
        panel_w = min(40, w - 2)
        panel_h = len(rows) + 7
        x = max(0, (w - panel_w) // 2)
        y = max(0, (h - panel_h) // 2)
        self.safe_add(y, x, "╭" + "─" * (panel_w - 2) + "╮", curses.A_DIM)
        self.safe_add(y + 1, x, "│" + " " * (panel_w - 2) + "│", curses.A_DIM)
        title = f"{APP_NAME}  v{APP_VERSION}"
        self.safe_add(y + 1, x + 2, title[:panel_w - 4], curses.A_BOLD)
        self.safe_add(y + 2, x, "├" + "─" * (panel_w - 2) + "┤", curses.A_DIM)
        for i, (key, action) in enumerate(rows):
            line = f"  {key:<10}{action}"[:panel_w - 2].ljust(panel_w - 2)
            self.safe_add(y + 3 + i, x, "│" + line + "│", curses.A_DIM)
            self.safe_add(y + 3 + i, x + 3, key, curses.A_BOLD)
        foot_y = y + 3 + len(rows)
        self.safe_add(foot_y, x, "├" + "─" * (panel_w - 2) + "┤", curses.A_DIM)
        credit = f"  Created by {APP_CREATOR}"[:panel_w - 2].ljust(panel_w - 2)
        footer = "  press ? to return"[:panel_w - 2].ljust(panel_w - 2)
        self.safe_add(foot_y + 1, x, "│" + credit + "│", curses.A_DIM)
        self.safe_add(foot_y + 1, x + 3, f"Created by {APP_CREATOR}"[:panel_w - 4], curses.A_BOLD)
        self.safe_add(foot_y + 2, x, "│" + footer + "│", curses.A_DIM)
        self.safe_add(foot_y + 3, x, "╰" + "─" * (panel_w - 2) + "╯", curses.A_DIM)

    def confirm_new(self) -> None:
        self.game.message = "Start a new deal? Press Y to confirm."
        self.draw()
        if self.s.getch() in (ord("y"), ord("Y")):
            self.game.new()
            self.selected = None
            self.zone, self.cursor, self.depth = "tableau", 0, 0
            self.animate_deal()
        else:
            self.game.message = "New deal cancelled."

    def win_screen(self) -> None:
        h, w = self.s.getmaxyx()
        elapsed = int(time.monotonic() - self.game.started)
        lines = ["PROCESS COMPLETE", "", "STACK CLEARED.", "",
                 f"{self.game.moves} moves  •  {elapsed//60:02}:{elapsed%60:02}  •  {self.game.score} points",
                 "", "Press N for another deal or Q to quit"]
        self.s.erase()
        y = max(1, h // 2 - len(lines) // 2)
        for i, line in enumerate(lines):
            self.safe_add(y + i, max(0, (w - len(line)) // 2), line,
                          curses.color_pair(2) | (curses.A_BOLD if i == 2 else 0))
        self.s.refresh()

    def handle(self, key: int) -> None:
        if key == -1:
            return
        if key == ord("?"):
            self.help_visible = not self.help_visible
            if self.help_visible:
                remember_help_seen()
            elif self.first_run:
                self.first_run = False
                self.animate_deal()
            return
        if self.help_visible:
            return
        if key in (ord("q"), ord("Q")):
            self.running = False
        elif key in (ord("n"), ord("N")):
            self.confirm_new()
        elif key in (ord("u"), ord("U")):
            self.game.undo()
            self.selected = None
        elif key in (ord("d"), ord("D"), ord(" ")):
            self.animated_draw()
        elif key in (ord("a"), ord("A")):
            self.auto()
        elif key in (ord("h"), ord("H")):
            self.hint()
        elif key in (10, 13, curses.KEY_ENTER):
            self.activate()
        elif key == 27:
            self.selected = None
            self.game.message = "Selection cleared."
        elif key in (curses.KEY_UP, ord("k")):
            if self.zone == "tableau":
                pile = self.game.tableau[self.cursor]
                face_count = sum(c.face_up for c in pile)
                if self.depth < max(0, face_count - 1): self.depth += 1
                else: self.zone, self.cursor, self.depth = "top", min(self.cursor, 5), 0
        elif key in (curses.KEY_DOWN, ord("j")):
            if self.zone == "top": self.zone, self.cursor, self.depth = "tableau", min(self.cursor, 6), 0
            elif self.depth > 0: self.depth -= 1
        elif key in (curses.KEY_LEFT, ord("h")):
            self.cursor = max(0, self.cursor - 1)
            self.depth = 0
        elif key in (curses.KEY_RIGHT, ord("l")):
            limit = 5 if self.zone == "top" else 6
            self.cursor = min(limit, self.cursor + 1)
            self.depth = 0

    def run(self) -> None:
        self.show_intro()
        if self.first_run:
            self.help_visible = True
            remember_help_seen()
        else:
            self.animate_deal()
        while self.running:
            if self.game.won:
                self.win_screen()
                key = self.s.getch()
                if key in (ord("n"), ord("N")):
                    self.game.new()
                    self.selected = None
                elif key in (ord("q"), ord("Q")):
                    break
                continue
            self.draw()
            self.handle(self.s.getch())


def main() -> None:
    if len(sys.argv) > 1:
        if sys.argv[1] in ("-v", "--version"):
            print(f"{APP_NAME} {APP_VERSION}")
            return

        print(f"Unknown option: {sys.argv[1]}", file=sys.stderr)
        print("Usage: solitaire [--version]", file=sys.stderr)
        raise SystemExit(2)

    try:
        first_run = is_first_run()
        request_terminal_size()
        # Give the terminal a moment to report its new dimensions to curses.
        time.sleep(0.08)
        curses.wrapper(lambda screen: UI(screen, first_run).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
