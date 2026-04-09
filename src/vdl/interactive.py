from __future__ import annotations

import sys

from . import presets
from .downloader import DEFAULT_OUTPUT, Downloader

# ── Couleurs ANSI (désactivées si non-TTY) ─────────────────────────────────


def _c(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(text: str) -> str:
    return _c(text, "1")


def _cyan(text: str) -> str:
    return _c(text, "96")


def _green(text: str) -> str:
    return _c(text, "92")


def _yellow(text: str) -> str:
    return _c(text, "93")


# ── Helpers interactifs ────────────────────────────────────────────────────


def _pick(items: list[dict[str, str]], label_key: str, default: int = 1) -> int:
    for i, item in enumerate(items, 1):
        marker = _cyan(" ←") if i == default else ""
        print(f"  {i}. {item[label_key]}{marker}")
    raw = input(_bold(f"→ Choix [{default}] : ")).strip()
    if not raw:
        return default - 1
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(items):
            return idx
    except ValueError:
        pass
    return default - 1


# ── Mode interactif principal ──────────────────────────────────────────────


def run_interactive() -> None:
    print()
    print(_cyan("╔══════════════════════════════════════════╗"))
    print(_cyan("║") + _bold("   vdl — Téléchargeur universel           ") + _cyan("║"))
    print(_cyan("╚══════════════════════════════════════════╝"))
    print()

    # URL
    try:
        url = input(_bold("🔗 Lien de la vidéo : ")).strip()
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
        typ = input(_bold("🎬 Audio ou vidéo ? [a/v] (défaut: v) : ")).strip().lower()
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
        audio_kbps = "0"

    # Sous-titres (vidéo uniquement)
    subs = False
    subs_lang = "fr"
    if not is_audio:
        print()
        try:
            subs_ans = input(_bold("💬 Télécharger les sous-titres ? [o/N] : ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if subs_ans == "o":
            subs = True
            try:
                lang_ans = input(_bold("   Langue des sous-titres [fr] : ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                sys.exit(0)
            subs_lang = lang_ans or "fr"

    # Dossier de sortie
    print()
    try:
        out_input = input(_bold(f"📂 Dossier de sortie [{DEFAULT_OUTPUT}] : ")).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    output = out_input or DEFAULT_OUTPUT

    # Résumé + confirmation
    print()
    print(_bold("  Récapitulatif :"))
    print(f"    URL     : {url}")
    print(f"    Type    : {'audio' if is_audio else 'vidéo'}")
    print(f"    Format  : {ext.upper()}")
    if not is_audio:
        quality_label = presets.VIDEO_QUALITIES[q_idx]["label"]
        print(f"    Qualité : {quality_label}")
    if subs:
        print(f"    Subs    : {subs_lang}")
    print(f"    Sortie  : {output}")
    print()
    try:
        confirm = input(_bold("Confirmer ? [O/n] : ")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    if confirm == "n":
        print("🛑  Annulé.")
        sys.exit(0)

    print()
    dl = Downloader(output_dir=output, subs=subs, subs_lang=subs_lang)
    sys.exit(dl.download(url, ext, is_audio, quality_selector, audio_kbps))
