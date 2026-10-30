#!/bin/sh
# Install P.A.R.O.L.A. from this folder (decision 0029): check the tools, install the Python
# packages, build the app and the capture helper, and optionally copy the app to /Applications.
# The speech models (about 4.2 GB) are not downloaded here: the app asks on its first start.
#
#   ./install.sh          asks before installing anything
#   ./install.sh --yes    answers yes to every question (for scripts and coding agents)
set -eu

yes=0
for arg in "$@"; do
    case $arg in
        --yes|-y) yes=1 ;;
        -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

repo=$(cd "$(dirname "$0")" && pwd)
cd "$repo"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
ok() { printf '    ok: %s\n' "$1"; }
fail() { printf '\n\033[31merror:\033[0m %s\n' "$1" >&2; exit 1; }
ask() {
    # ask "question": 0 for yes. Without a terminal and without --yes, the answer is no.
    if [ "$yes" = 1 ]; then printf '%s [y/N] y\n' "$1"; return 0; fi
    if [ ! -t 0 ]; then printf '%s [y/N] n (no terminal: rerun with --yes)\n' "$1"; return 1; fi
    printf '%s [y/N] ' "$1"
    read -r answer
    case $answer in [yY]|[yY][eE][sS]|[sS]|[sS][iI]|[sS]ì) return 0 ;; *) return 1 ;; esac
}

# Homebrew's folders, in case this runs from a shell that does not have them yet.
for dir in /opt/homebrew/bin /usr/local/bin; do
    case ":$PATH:" in *":$dir:"*) ;; *) [ -d "$dir" ] && PATH="$dir:$PATH" ;; esac
done
export PATH

step "Checking this Mac"
[ "$(uname -s)" = Darwin ] || fail "P.A.R.O.L.A. runs on macOS only."
[ "$(uname -m)" = arm64 ] || fail "P.A.R.O.L.A. needs an Apple Silicon Mac (M1 or later)."
# Recording system audio uses Core Audio process taps, which came with macOS 14.2.
release=$(sw_vers -productVersion)
major=$(echo "$release" | cut -d. -f1)
minor=$(echo "$release" | cut -d. -f2)
if [ "$major" -lt 14 ] || { [ "$major" -eq 14 ] && [ "${minor:-0}" -lt 2 ]; }; then
    fail "macOS 14.2 or later is needed to record calls (this is $release): update macOS first."
fi
ok "macOS $release on Apple Silicon"

# A transcription peaks at about 6 GB: fine on 16 GB, tight on 8 GB.
memory=$(( $(sysctl -n hw.memsize) / 1073741824 ))
if [ "$memory" -lt 16 ]; then
    printf '    \033[33mnote:\033[0m this Mac has %s GB of memory. A transcription uses about 6 GB at its\n' "$memory"
    echo "          peak: close other apps while it runs (the call is over by then), and expect it"
    echo "          to be slower than on 16 GB."
else
    ok "$memory GB of memory"
fi

step "Checking the tools"
if xcode-select -p >/dev/null 2>&1 && command -v swift >/dev/null 2>&1; then
    ok "Swift ($(swift --version 2>/dev/null | head -1 | sed 's/.*version \([0-9.]*\).*/\1/'))"
else
    echo "    missing: the Xcode Command Line Tools (Swift, to build the app; about 1 GB from Apple)"
    if ask "    Open Apple's installer now?"; then
        xcode-select --install || true
    fi
    fail "Install the Command Line Tools (or run: xcode-select --install), then run ./install.sh again."
fi

missing=""
command -v uv >/dev/null 2>&1 || missing="$missing uv"
command -v ffmpeg >/dev/null 2>&1 || missing="$missing ffmpeg"
if [ -n "$missing" ]; then
    echo "    missing:$missing"
    if ! command -v brew >/dev/null 2>&1; then
        echo "    missing: Homebrew (https://brew.sh), the package manager that installs$missing"
        if ask "    Install Homebrew now? (its installer asks for your macOS password)"; then
            # Homebrew's own installer, from its official repository. NONINTERACTIVE skips
            # its "press RETURN" prompt under --yes; the password question remains the person's.
            if [ "$yes" = 1 ]; then
                NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            else
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            for dir in /opt/homebrew/bin /usr/local/bin; do
                case ":$PATH:" in *":$dir:"*) ;; *) [ -d "$dir" ] && PATH="$dir:$PATH" ;; esac
            done
            command -v brew >/dev/null 2>&1 \
                || fail "Homebrew did not install; see the messages above, then run ./install.sh again."
        else
            fail "Install Homebrew (https://brew.sh), then run ./install.sh again."
        fi
    fi
    if ask "    Install them with Homebrew (brew install$missing)?"; then
        # shellcheck disable=SC2086
        brew install $missing
    else
        fail "Install them (brew install$missing), then run ./install.sh again."
    fi
fi
ok "uv $(uv --version | cut -d' ' -f2)"
ok "ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)"

step "Installing the Python packages (uv sync: about 1.3 GB, the first time)"
uv sync --inexact  # adds what is missing, removes nothing (e.g. the optional baselines)
ok "packages in .venv"

# The Italian part-of-speech tagger makes the suggested titles cleaner, but its license is
# non-commercial (CC BY-NC-SA 3.0), so it is asked, never assumed. Titles work without it.
if ask "Install the Italian tagger for better suggested titles? (it_core_news_sm 13 MB, CC BY-NC-SA: non-commercial use only)"; then
    uv sync --inexact --group titles
    ok "Italian tagger in .venv"
fi

step "Building the capture helper and the app"
uv run --no-sync python -c "from parola.capture.recorder import build_helper; print('    ok:', build_helper())"
"$repo/app/build.sh" >/dev/null
ok "$repo/dist/PAROLA.app"

app="$repo/dist/PAROLA.app"
if ask "Copy P.A.R.O.L.A. to /Applications (Launchpad, Spotlight, Dock)?"; then
    if [ -d /Applications/PAROLA.app ]; then
        osascript -e 'quit app id "dev.parola.app"' >/dev/null 2>&1 || true
        rm -rf /Applications/PAROLA.app
    fi
    cp -R "$app" /Applications/PAROLA.app
    app=/Applications/PAROLA.app
    ok "$app"
fi

cat <<EOF

P.A.R.O.L.A. is installed. It uses this folder ($repo): keep it where it is.
Your calls stay in $repo/data/private/calls (never sent anywhere, ignored by git).

On the first start the app asks to download the speech models (about 4.2 GB, once).
The first recording asks for the microphone and for system audio: allow both.

To open it: open "$app"
EOF

if ask "Open it now?"; then
    open "$app"
fi
