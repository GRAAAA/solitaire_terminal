# solitaire_terminal

I made solitaire_terminal because I wanted a small solitaire game that I could open and play without leaving the terminal. It is a complete Klondike game written in Python, with no packages to install.

Version 1.0.0

## Install

Python 3 is the only requirement. On macOS or Linux, run:

```bash
curl -fsSL https://raw.githubusercontent.com/GRAAAA/solitaire_terminal/main/install.sh | sh
```

Make sure `~/.local/bin` is in your `PATH`, then start the game from any terminal:

```bash
solitaire_terminal
```

You can also clone the repository and run it without installing:

```bash
git clone https://github.com/GRAAAA/solitaire_terminal.git
cd solitaire_terminal
./play
```

## Manage the installation

```bash
solitaire_terminal update
solitaire_terminal --version
solitaire_terminal uninstall
```

To install again from a cloned copy, use `./play install`.

## Controls

| Key | What it does |
| --- | --- |
| Arrow keys | Move between cards and piles |
| Enter | Select or place a card |
| `D` or Space | Draw from the stock |
| `A` | Move the current card to its foundation |
| `H` | Show a possible move |
| `U` | Undo the last move |
| `N` | Start a new game |
| Escape | Clear the selection |
| `Q` | Quit |

The game needs a terminal at least 42 columns wide and 24 rows tall. Unicode and colour support are recommended.

Empty tableau columns only accept kings, and empty foundations only accept aces.
