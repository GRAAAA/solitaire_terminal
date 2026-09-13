#!/bin/sh

set -eu

repo="GRAAAA/solitaire_terminal"
branch="main"
install_dir="${XDG_DATA_HOME:-$HOME/.local/share}/solitaire_terminal"
bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
command_path="$bin_dir/solitaire_terminal"
raw_url="https://raw.githubusercontent.com/$repo/$branch"

download() {
    source_file=$1
    destination=$2

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$raw_url/$source_file" -o "$destination"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$raw_url/$source_file" -O "$destination"
    else
        echo "solitaire_terminal needs curl or wget to download files." >&2
        exit 1
    fi
}

install_game() {
    mode=$1
    mkdir -p "$install_dir" "$bin_dir"

    script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    if [ "$mode" = "install" ] && [ "$script_dir" != "$install_dir" ] && \
       [ -f "$script_dir/solitaire.py" ] && [ -f "$script_dir/play" ]; then
        cp "$script_dir/solitaire.py" "$install_dir/solitaire.py"
        cp "$script_dir/play" "$install_dir/play"
        cp "$script_dir/install.sh" "$install_dir/install.sh"
    else
        download solitaire.py "$install_dir/solitaire.py"
        download play "$install_dir/play"
        download install.sh "$install_dir/install.sh"
    fi

    chmod +x "$install_dir/play" "$install_dir/install.sh"
    ln -sf "$install_dir/play" "$command_path"

    echo "solitaire_terminal installed. Run it with: solitaire_terminal"
    case ":$PATH:" in
        *":$bin_dir:"*) ;;
        *) echo "Add $bin_dir to your PATH if the command is not found." ;;
    esac
}

uninstall_game() {
    rm -f "$command_path"
    rm -rf "$install_dir"
    echo "solitaire_terminal has been uninstalled."
}

case "${1:-install}" in
    install)
        install_game install
        ;;
    update)
        install_game update
        echo "solitaire_terminal is up to date."
        ;;
    uninstall)
        uninstall_game
        ;;
    *)
        echo "Usage: install.sh [install|update|uninstall]" >&2
        exit 2
        ;;
esac
