# Installing P.A.R.O.L.A.

P.A.R.O.L.A. runs from its own folder: you download the folder, one script builds the app on
your Mac, and the app keeps using that folder. Nothing leaves your Mac: the only downloads are
the tools, the Python packages and, once, the speech models.

## What you need

- A Mac with Apple Silicon (M1 or later) and macOS 14 Sonoma or later.
- About 6 GB of free space: 4.2 GB of speech models, the rest for the app and its packages.
- 16 GB of memory is comfortable; a transcription uses about 6 GB at its peak.
- [Homebrew](https://brew.sh), if `uv` or `ffmpeg` are not installed yet.

## Install it yourself

```bash
git clone https://github.com/jacopo-grandi/P.A.R.O.L.A..git
cd P.A.R.O.L.A.
./install.sh
```

The script asks before installing anything. It:

1. checks the Mac and the tools: the Xcode Command Line Tools (Swift), `uv` and `ffmpeg`. If
   one is missing, it offers to install it (Homebrew, or Apple's installer for Swift);
2. installs the Python packages into `.venv` with `uv sync`;
3. builds the capture helper and the app, `dist/PAROLA.app`;
4. offers to copy the app to /Applications, then to open it.

On the first start the app asks to download the speech models (about 4.2 GB, once), with a
progress bar. The first recording asks for the microphone and for system audio: allow both.

The app is built on your Mac, so macOS opens it without the "unidentified developer" warning.
Keep the folder where it is: the app runs the engine from there, and your calls stay in
`data/private/calls`, ignored by git.

## Let a coding agent install it

Paste this into Claude Code, Codex or a similar agent running on your Mac:

> Install P.A.R.O.L.A. on this Mac: clone https://github.com/jacopo-grandi/P.A.R.O.L.A. into my
> home folder and follow the "Instructions for coding agents" in its INSTALL.md.

## Updating

```bash
cd P.A.R.O.L.A.
git pull
./install.sh
```

Your calls, corrections and learned terms are in `data/private/` and are not touched.

## Removing it

Quit the app (menu bar icon → Esci), then delete:

- the app: `/Applications/PAROLA.app`, if you copied it there;
- the folder you cloned. **This deletes your calls too** (`data/private/calls`): copy them first
  if you want to keep them;
- the models: `~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo`,
  `~/.cache/huggingface/hub/models--mlx-community--parakeet-tdt-0.6b-v3` and
  `~/.cache/parola`.

## If something goes wrong

- **"ffmpeg not found"**: install it with `brew install ffmpeg`, then quit and reopen the app.
- **The "Altri" meter stays empty while recording**: system audio is not allowed. System
  Settings → Privacy & Security → Screen & System Audio Recording → System Audio Recording Only:
  turn on P.A.R.O.L.A. (or parola-capture).
- **The model download fails**: check the connection and press Riprova. What was already
  downloaded is kept.
- **The app does not start** ("Motore non trovato"): run `./install.sh` again from the folder.

---

## Instructions for coding agents

You are installing P.A.R.O.L.A. for the person you are working with, on their Mac. Follow these
steps in order and report back in their language.

1. **Check** that this is macOS 14 or later on Apple Silicon (`sw_vers`, `uname -m` = `arm64`).
   If not, stop and say why it cannot be installed.
2. **Clone** the repository, unless it is already there (then `git pull` in it):
   `git clone https://github.com/jacopo-grandi/P.A.R.O.L.A..git ~/P.A.R.O.L.A.`
   Use another folder only if the person asks.
3. **Ask the person before installing tools.** Check `xcode-select -p`, `uv --version` and
   `ffmpeg -version`. If any is missing, tell them what is missing and its size, and ask:
   - Command Line Tools: `xcode-select --install` opens Apple's installer, which the person has
     to confirm on screen; wait until it is done.
   - `uv` / `ffmpeg`: `brew install uv ffmpeg` (if Homebrew itself is missing, point them to
     https://brew.sh; do not install it for them without asking).
4. **Run the installer** from the repository folder: `./install.sh --yes`. With `--yes` it also
   copies the app to /Applications and opens it: if the person does not want that, run it
   without `--yes` in a terminal they can answer, or skip those steps.
5. **Verify**: `dist/PAROLA.app` exists and `.venv/bin/parola --help` runs.
6. **Tell the person** that on the first start the app asks to download the speech models
   (about 4.2 GB) and that the first recording asks for microphone and system audio
   permissions.

Rules:

- Do not download the speech models yourself: the app asks the person first.
- Do not use `sudo`, and do not change system or privacy settings: the person grants the
  permissions when macOS asks.
- Never read, move or upload anything under `data/private/`: it holds their recordings.
- If a step fails, show the error and stop; do not work around it by editing the code.
