import sys

from . import presets
from .downloader import DEFAULT_OUTPUT, Downloader


def _pick(items: list, label_key: str, default: int = 1) -> int:
    for i, item in enumerate(items, 1):
        marker = " ←" if i == default else ""
        print(f"  {i}. {item[label_key]}{marker}")
    raw = input(f"→ Choix [{default}] : ").strip()
    if not raw:
        return default - 1
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(items):
            return idx
    except ValueError:
        pass
    return default - 1


def run_interactive():
    print()
    print("╔══════════════════════════════════════════╗")
    print("║   vdl — Téléchargeur universel           ║")
    print("╚══════════════════════════════════════════╝")
    print()

    # URL
    try:
        url = input("🔗 Lien de la vidéo : ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)

    if not url:
        print("❌ Aucune URL fournie.", file=sys.stderr)
        sys.exit(1)
    if not url.startswith(("http://", "https://")):
        print("❌ L'URL doit commencer par http:// ou https://", file=sys.stderr)
        sys.exit(1)

    # Type audio ou vidéo
    print()
    try:
        typ = input("🎬 Audio ou vidéo ? [a/v] (défaut: v) : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    is_audio = typ == "a"

    if is_audio:
        print("\n  Format audio :")
        fmt_idx = _pick(presets.AUDIO_FORMATS, "label")
        ext = presets.AUDIO_FORMATS[fmt_idx]["ext"]

        print("\n  Qualité audio :")
        q_idx = _pick(presets.AUDIO_QUALITIES, "label")
        audio_kbps = presets.AUDIO_QUALITIES[q_idx]["value"]
        quality_selector = "bestaudio/best"
    else:
        print("\n  Format vidéo :")
        fmt_idx = _pick(presets.VIDEO_FORMATS, "label")
        ext = presets.VIDEO_FORMATS[fmt_idx]["ext"]

        print("\n  Qualité vidéo :")
        q_idx = _pick(presets.VIDEO_QUALITIES, "label")
        quality_selector = presets.VIDEO_QUALITIES[q_idx]["value"]
        audio_kbps = "320"

    # Dossier de sortie
    print()
    try:
        out_input = input(f"📂 Dossier de sortie [{DEFAULT_OUTPUT}] : ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    output = out_input or DEFAULT_OUTPUT

    print()
    dl = Downloader(output_dir=output)
    sys.exit(dl.download(url, ext, is_audio, quality_selector, audio_kbps))
