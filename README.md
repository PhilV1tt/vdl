# vdl - Universal video downloader

Made with love for Julien :))))

Download video and audio from YouTube, Vimeo, TikTok, SoundCloud and [1000+ other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

## Installation

### macOS

Paste this command into Terminal and press Enter:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/PhilV1tt/vdl/main/install-mac.sh)
```

### Linux

```bash
# 1. Install pipx if needed
sudo apt install pipx        # Debian/Ubuntu
sudo dnf install pipx        # Fedora
sudo pacman -S python-pipx   # Arch

pipx ensurepath

# 2. Install ffmpeg
sudo apt install ffmpeg      # Debian/Ubuntu
sudo dnf install ffmpeg      # Fedora
sudo pacman -S ffmpeg        # Arch

# 3. Install vdl
pipx install git+https://github.com/PhilV1tt/vdl.git
```

### Windows

Paste this command into PowerShell (as administrator):

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/PhilV1tt/vdl/main/install-windows.ps1 | iex"
```

The script installs Python, ffmpeg and vdl through winget.

## Usage

### Interactive mode (the easiest)

Run:

```bash
vdl
```

Paste a link: the download starts at once with the settings shown on screen.
Paste the next link while it runs; up to 3 items download in parallel and each one
has its own progress line. Pasting several links at once queues them all.
Finished items are printed above the screen with their path.

```
  vdl 0.9.0    VIDEO   AUDIO   Tab
  format    mp4   mkv   webm   avi   mov    ↑↓
  quality   best   2160   1440   1080   720   480   360    ←→
  folder    ~/Downloads  ^O
  ⠴ Big Buck Bunny 60fps 4K   █░░░░░░░░░  13%  25.6 MB/s  0:24
  >
```

| Key | Action (the arrows and Tab act on settings while the input line is empty) |
|-----|--------|
| Tab | Switch video / audio |
| ↑ ↓ | Format |
| ← → | Quality |
| Ctrl-O | Change the folder |
| Ctrl-E | Apple Music import on/off (Mac, audio) |
| Enter on an empty line | Download the link in the clipboard (Mac) |
| Ctrl-R | Show the last file in Finder |
| Ctrl-D / Ctrl-C | Quit (twice if something is still downloading) |

Type text and press Enter to search YouTube; `1` to `9` queue results, several allowed, Esc closes the list.
Drop a local file into Terminal and press Enter to convert it next to the source, to the format on screen.
Add an excerpt after a link: `https://youtu.be/xxx 12:00-14:30`.
`/history` shows past downloads. Settings are remembered for the next run.
Subtitles, SponsorBlock and the other rare options are set once in the config file (see below).
`NO_COLOR=1` turns colors off, `VDL_REDUCED_MOTION=1` turns animations off.

A video link targets that video, even if YouTube adds a playlist or a radio to it.
A playlist-only or channel link downloads the whole playlist. On a live stream in progress,
vdl records from the start.

### Command mode

```bash
vdl https://youtu.be/xxx                   # MP4 video, best quality
vdl https://youtu.be/xxx -a                # MP3 audio
vdl https://youtu.be/xxx -a -f flac        # FLAC audio
vdl https://youtu.be/xxx -q 1080           # 1080p video
vdl -m https://youtu.be/xxx                # MP3 + Apple Music import
vdl -b links.txt                           # Download a list of URLs
vdl convert film.mkv -f mp3                # Convert a local file
vdl film.mov -f mp3                        # Direct conversion, no subcommand
vdl convert                                # Open the screen, drop a file
vdl https://youtu.be/xxx -s 12:00-14:30    # Only this excerpt
vdl <ongoing YouTube live>                 # Record the live from its start
```

### Convert a local file

`convert` transforms a file already on disk, without going through a site. The output
keeps the source name; `-o` changes the folder.
The `convert` subcommand is optional: `vdl film.mkv -f mp3` works too.
With no argument, `vdl convert` asks for a file and an output format.

```bash
vdl convert film.mkv -f mp3             # MP3 320 kbps
vdl convert podcast.wav -f flac         # FLAC, lossless
vdl convert reel.mov -f mp4 -q 1080     # MP4 scaled to 1080p
vdl convert *.mp4 -f mp3 -o ~/Music     # several files at once
```

| Option | Description |
|--------|-------------|
| `-f FORMAT` | Output: `mp3` `m4a` `aac` `flac` `wav` `ogg` `opus` (video: `mp4` `mkv` `webm` `avi` `mov`) |
| `-q Q` | Audio: `320` `256` `192` `128` kbps.  Video: height `2160` `1440` `1080` `720` `480` `360` |
| `-o DIR` | Output folder (default: next to the source) |

Without `-f`, the output is the last audio format chosen, or MP3. Encoding is h264 + AAC,
VP9 + Opus for WebM. If the output name exists, vdl adds a suffix (`film (1).mp3`).
The source is always kept, including when converting to the same format.
A failure leaves no partial file.

In interactive mode, paste a path or use `/convert`.

### Options

| Option | Description |
|--------|-------------|
| `-a` / `--audio` | Extract the audio (MP3 by default) |
| `-q QUALITY` | Video quality: `best`, `1080`, `720`, `480`, `360` |
| `-f FORMAT` | Format: `mp3`, `m4a`, `flac`, `wav`, `mp4`, `mkv`... |
| `-o DIR` | Destination folder (default: `~/Downloads`) |
| `-p` / `--playlist` | Download a whole playlist / channel |
| `-b FILE` | File of URLs, one per line (`-` = standard input) |
| `--links` | List the links of a channel/playlist, without downloading |
| `-m` / `--music` | MP3 + import into Apple Music |
| `-s START-END` | Excerpt, e.g. `12:00-14:30` (repeatable) |
| `--cookies-from-browser BROWSER` | Cookies from chrome/safari/firefox/edge/brave (private / members-only / age-restricted content) |
| `--live-from-start` / `--no-live-from-start` | Force or disable recording a live stream from its start (default: auto-detected) |
| `-F` / `--list-formats` | List the formats available for a URL |
| `--format-id ID` | Download a specific yt-dlp format (see `-F`) |
| `--subs [LANG]` | Subtitles (optional language) |
| `--sponsorblock` / `--no-sponsorblock` | Force or disable SponsorBlock |
| `--list-sites` | Show the 1000+ supported sites |

### Live streams

vdl detects a live stream in progress and records it from its start. There is no built-in way to stop automatically at the current moment: Ctrl-C is the only stop point, and vdl then joins the fragments already received into a playable file.

On a live stream that has been running for a long time (a 24/7 camera, for example), "from the start" can mean a huge amount of data. Check that this is what you want before starting a long recording, and let it run as long as needed before pressing Ctrl-C.

### Get every link of a channel

`--links` prints one URL per line on standard output, without downloading anything.
A bare `@handle` is completed automatically.

```bash

```

### Persistent settings

vdl remembers the last quality and format, separately for audio and video.
The folder chosen in interactive mode is remembered for next time as well. `vdl config`
shows the effective values and where they come from (memory or config);
`vdl config reset` forgets the memory.

On the command line, `-o` changes the folder for that run only.

Less common options are set once in `~/.config/vdl/config.toml`
(instead of a flag on every command):

```toml
subs = true              # Download and embed subtitles
subs_lang = "fr"         # Subtitle language
sponsorblock = true      # Remove SponsorBlock segments
embed_thumbnail = true   # Embed the thumbnail
output_template = "%(title)s.%(ext)s"
concurrent_fragments = 4 # Fragments downloaded in parallel (long videos/lives)
aria2c = false           # Hand the download to aria2c (brew install aria2)
```

On long videos and live streams, vdl already downloads 4 fragments in parallel
by default (faster than one at a time). To go further, install
`aria2c` and set `aria2c = true`: yt-dlp hands the download to it, usually
the fastest option.

## Updates

yt-dlp updates itself: at most once every 24 hours, at launch, vdl compares the installed
yt-dlp with PyPI and upgrades it silently (with `pip`, or `uv pip` when the environment has
no pip, as with `uv tool`). If the network or the install fails, vdl keeps the installed
version and prints nothing. Set `VDL_NO_AUTO_UPDATE=1` to turn this off.

To update vdl itself and yt-dlp by hand:

```bash
vdl --update
```

## Uninstall

```bash
pipx uninstall vdl        # macOS / Linux
```
