#!/bin/sh

set -eu

repo="GRAAAA/solitaire_terminal"
branch="main"
install_dir="${XDG_DATA_HOME:-$HOME/.local/share}/solitaire_terminal"
bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
command_path="$bin_dir/solitaire_terminal"
# GitHub's branch-based raw-content CDN can briefly serve an older revision.
# This route resolves the branch through github.com before downloading the file.
raw_url="https://github.com/$repo/raw/refs/heads/$branch"

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
        staging_dir=$(mktemp -d "${TMPDIR:-/tmp}/solitaire_terminal.XXXXXX")
        trap 'rm -rf "$staging_dir"' EXIT HUP INT TERM

        download solitaire.py "$staging_dir/solitaire.py"
        download play "$staging_dir/play"
        download install.sh "$staging_dir/install.sh"

        mv "$staging_dir/solitaire.py" "$install_dir/solitaire.py"
        mv "$staging_dir/play" "$install_dir/play"
        mv "$staging_dir/install.sh" "$install_dir/install.sh"
        rmdir "$staging_dir"
        trap - EXIT HUP INT TERM
    fi

    chmod +x "$install_dir/play" "$install_dir/install.sh"
    ln -sf "$install_dir/play" "$command_path"

    if [ "$mode" = "install" ]; then
        echo "solitaire_terminal installed. Run it with: solitaire_terminal"
        case ":$PATH:" in
            *":$bin_dir:"*) ;;
            *) echo "Add $bin_dir to your PATH if the command is not found." ;;
        esac
    fi
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
