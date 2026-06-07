# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

A local Python suite and 5-step interactive web wizard for creating synchronized karaoke/lyrics videos from audio, lyrics, and background images or videos. Uses Whisper for word-level transcription and FFmpeg for efficient video assembly.

## Prerequisites

- Python 3.10+ with virtual environment at `.venv/`
- FFmpeg installed and on PATH
- Dependencies: `pillow faster-whisper whisper-timestamped soundfile librosa`
- Optional (audio separation): `audio-separator[gpu]`

## Running the Application

```powershell
# Activate venv
.venv\Scripts\Activate.ps1

# Start the web wizard (recommended)
python karaoke_web_server.py --port 8080
# Open http://localhost:8080
```

## CLI Usage

```powershell
# Transcription (word-level timing via Whisper)
python karaoke_timing.py path/to/audio.mp3 --model medium --language es --output path/to/output_dir

# Generate image map from silences
python karaoke_assembler.py --generate-map --images ./images --srt output/words.srt --audio audio.mp3

# Assemble video with image backgrounds
python karaoke_assembler.py --images ./images --srt output/words.srt --audio audio.mp3 --map output/map.json --output video.mp4 --mode karaoke --style neon --font C:/Windows/Fonts/georgia.ttf

# Assemble video with looping video backgrounds
python karaoke_assembler.py --images ./images --srt output/words.srt --audio audio.mp3 --output video.mp4 --background-type video --video-bg "base_videos/v1.mp4,loop_videos/v2.mp4" --mode lyrics

# 30-second preview render
python karaoke_assembler.py ... --preview

# Audio stem separation (vocal/instrumental)
python karaoke_separator.py <audio_path> <project_dir>

# All-in-one CLI pipeline
python karaoke_maker.py init "Song Name" --audio song.mp3
python karaoke_maker.py build "Song Name/"
python karaoke_maker.py preview "Song Name/"
```

## Architecture

### Pipeline (5-step web wizard)
1. **Step 1 – Config**: Create/load project, upload audio, set title/artist/font/style → writes `<project>/config.json`
2. **Step 2 – Transcription**: Runs `karaoke_timing.py` via `karaoke_web_server.py` background task; produces `output/words.json` + `output/words.srt`; then auto-generates `output/map.json` via `karaoke_assembler.py --generate-map`
3. **Step 3 – Backgrounds**: Upload images (stored in `<project>/images/`) or select/upload video loops (stored in `loop_videos/`)
4. **Step 4 – Mapping** (image mode only): Visual timeline editor; saves `output/map.json` with time-range → image assignments
5. **Step 5 – Render**: Calls `karaoke_assembler.py` as background subprocess; serves result via `/api/video`

### Key Files

| File | Role |
|---|---|
| `karaoke_web_server.py` | HTTP server (stdlib only), serves `web_ui/` and all REST APIs; runs Whisper/assembler as subprocesses via `TaskManager` |
| `karaoke_assembler.py` | Core render engine — reads SRT/JSON/map, draws Pillow frames (only on state changes, ~300 total), composes via FFmpeg |
| `karaoke_timing.py` | Wrapper around `faster-whisper` / `whisper-timestamped`; outputs `*_words.json`, `*_words.srt`, `*_karaoke.csv` |
| `karaoke_separator.py` | Vocal/instrumental stem separation via `audio-separator` + RoFormer model |
| `karaoke_maker.py` | CLI orchestrator (`init`/`build`/`preview`/`info`/`clean` subcommands) |
| `web_ui/` | Vanilla JS + CSS frontend; no build step needed |

### Project Directory Structure (runtime)
Each project lives at `<workspace>/<project_name>/`:
```
<project>/
├── config.json         ← all settings (title, artist, style, mode, font, etc.)
├── audio.mp3           ← uploaded audio (name from config["audio"])
├── vocals.mp3          ← optional: vocal stem from separator
├── instrumental.mp3    ← optional: instrumental stem (used as audio in karaoke mode)
├── images/             ← background images
└── output/
    ├── words.json      ← transcription data
    ├── words.srt       ← word-level SRT
    ├── map.json        ← time range → image segment map
    └── *.mp4           ← rendered video(s)
```

### Render Modes
- `karaoke` — word-by-word highlight; uses `instrumental.mp3` if available
- `lyrics` — full line appears at once (classic lyrics video)

### Visual Styles
`minimal` | `dark` | `neon` | `vintage` — defined as color palettes in `karaoke_assembler.py::STYLES`

### Background Types
- **Images (timeline)**: 1–12 images distributed by musical silence gaps; editable via map timeline UI
- **Video loop**: sequential video clips from `base_videos/` or `loop_videos/`; audio is silenced automatically
- **Solid color**: extracted from style palette when no backgrounds provided

### TaskManager (web server)
`TaskManager` in `karaoke_web_server.py` runs Whisper and assembler as daemon threads, streams stdout line by line, and parses progress (`%` for assembler/separator; timestamp format `[MM:SS.ss ->` for Whisper). Poll via `GET /api/status?project=<name>`.

### Output Naming Convention
Output filenames are sanitized and dynamic: `<Artist>-<Title>-karaoke.mp4` or `<Artist>-<Title>-Lyrics.mp4`. Computed by `get_dynamic_output_name()` in the web server.

### Asset Directories
- `base_images/` — sample background images (PNG/JPEG)
- `base_videos/` — short default background video clips (~5s)
- `loop_videos/` — user-uploaded loop videos (persisted across projects)
- `audio_separator_models/` — RoFormer model cache (auto-created by separator)
