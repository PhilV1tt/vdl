"""Mode interactif avec navigation clavier (questionary)."""

from __future__ import annotations

import sys
import time

from . import presets
from .downloader import DEFAULT_OUTPUT, Downloader
from .tui import BLUE, BOLD, CYAN, DIM, RESET, c, confirm, select, text

# ── Bannière ───────────────────────────────────────────────────────────────

_ASCII = [
    r" ██╗   ██╗██████╗ ██╗     ",
    r" ██║   ██║██╔══██╗██║     ",
    r" ██║   ██║██║  ██║██║     ",
    r" ╚██╗ ██╔╝██║  ██║██║     ",
    r"  ╚████╔╝ ██████╔╝███████╗",
    r"   ╚═══╝  ╚═════╝ ╚══════╝",
]


def _banner() -> None:
    print()
    for i, line in enumerate(_ASCII):
        color = CYAN if i < 3 else BLUE
        print(f"{BOLD}{color}{line}{RESET}")
        time.sleep(0.04)
    print(f"  {DIM}Telechargeur universel de videos{RESET}")
    print()


# ── Flux téléchargement ────────────────────────────────────────────────────


def _download_flow(url: str) -> int:
    """Collecte les options et lance le téléchargement."""
    # Type
    type_choice = select(
        "Audio ou video ?",
        choices=[
            {"name": "Video", "value": "video"},
            {"name": "Audio", "value": "audio"},
        ],
    )
    if type_choice is None:
        return 0
    is_audio = type_choice == "audio"

    if is_audio:
        fmt_choice = select(
            "Format audio ?",
            choices=[{"name": f["label"], "value": f["ext"]} for f in presets.AUDIO_FORMATS],
        )
        if fmt_choice is None:
            return 0
        ext: str = fmt_choice

        q_choice = select(
            "Qualité audio ?",
            choices=[{"name": q["label"], "value": q["value"]} for q in presets.AUDIO_QUALITIES],
        )
        if q_choice is None:
            return 0
        audio_kbps: str = q_choice
        quality_selector = "bestaudio/best"
    else:
        fmt_choice = select(
            "Format vidéo ?",
            choices=[{"name": f["label"], "value": f["ext"]} for f in presets.VIDEO_FORMATS],
        )
        if fmt_choice is None:
            return 0
        ext = fmt_choice

        q_choice = select(
            "Qualité vidéo ?",
            choices=[{"name": q["label"], "value": q["value"]} for q in presets.VIDEO_QUALITIES],
        )
        if q_choice is None:
            return 0
        quality_selector = q_choice
        audio_kbps = "0"

    # Sous-titres (vidéo uniquement)
    subs = False
    subs_lang = "fr"
    if not is_audio:
        subs = confirm("Télécharger les sous-titres ?", default=False)
        if subs:
            lang = text("Langue des sous-titres ?", default="fr")
            subs_lang = lang if lang else "fr"

    # SponsorBlock
    sponsorblock = False
    if not is_audio:
        sponsorblock = confirm("Supprimer les segments SponsorBlock ?", default=False)

    # Dossier de sortie
    output_raw = text("Dossier de sortie ?", default=DEFAULT_OUTPUT)
    output = output_raw if output_raw else DEFAULT_OUTPUT

    # Récapitulatif
    print()
    print("  ┌─ Récapitulatif ──────────────────────────┐")
    url_short = (url[:48] + "…") if len(url) > 50 else url
    print(f"  │  URL     : {url_short}")
    print(f"  │  Type    : {'audio' if is_audio else 'vidéo'} {ext.upper()}")
    if not is_audio:
        q_label = next(
            (q["label"] for q in presets.VIDEO_QUALITIES if q["value"] == quality_selector),
            quality_selector,
        )
        print(f"  │  Qualité : {q_label}")
    if subs:
        print(f"  │  Subs    : {subs_lang}")
    if sponsorblock:
        print("  │  SponsorBlock : activé")
    print(f"  │  Sortie  : {output}")
    print("  └──────────────────────────────────────────┘")
    print()

    if not confirm("Confirmer le telechargement ?", default=True):
        print(c("Annule.", DIM))
        return 0

    print()
    dl = Downloader(
        output_dir=output,
        subs=subs,
        subs_lang=subs_lang,
        sponsorblock=sponsorblock,
    )
    return dl.download(url, ext, is_audio, quality_selector, audio_kbps)


def _search_flow() -> int:
    """Flux recherche avec sélection du résultat."""
    from .search import SOURCES, search_videos

    source_choice = select(
        "Chercher sur ?",
        choices=[
            {"name": "YouTube", "value": "youtube"},
            {"name": "SoundCloud", "value": "soundcloud"},
        ],
    )
    if source_choice is None:
        return 0

    query = text("Rechercher :")
    if not query or not query.strip():
        return 0

    source_name = next((k for k in SOURCES if k == source_choice), "youtube")
    print(f"\n{c('Recherche en cours sur ' + source_name.title() + '...', CYAN)}")

    results = search_videos(query.strip(), source=source_name)
    if not results:
        print("Aucun resultat.", file=sys.stderr)
        return 1

    from .search import _fmt_duration, _fmt_views

    def _label(r: dict[str, object]) -> str:
        title = str(r.get("title", "?"))[:55]
        dur = _fmt_duration(r.get("duration"))  # type: ignore[arg-type]
        views = _fmt_views(r.get("view_count"))  # type: ignore[arg-type]
        meta = "  ".join(filter(None, [dur, views]))
        return f"{title}  [{meta}]" if meta else title

    choices = [{"name": _label(r), "value": str(r["url"])} for r in results]
    choices.append({"name": "← Retour", "value": "__back__"})

    url_choice = select("Choisir un résultat :", choices=choices)
    if url_choice is None or url_choice == "__back__":
        return 0

    return _download_flow(url_choice)


def _history_flow() -> int:
    """Affiche l'historique."""
    from .history import show_history

    show_history()
    return 0


# ── Point d'entrée principal ───────────────────────────────────────────────


def run_interactive() -> None:
    _banner()

    while True:
        action = select(
            "Que voulez-vous faire ?",
            choices=[
                {"name": "Telecharger depuis une URL", "value": "download"},
                {"name": "Rechercher sur YouTube / SoundCloud", "value": "search"},
                {"name": "Historique", "value": "history"},
                {"name": "Quitter", "value": "quit"},
            ],
        )

        if action is None or action == "quit":
            sys.exit(0)

        if action == "download":
            url = text("Lien de la video :")
            if not url or not url.strip():
                print("URL vide.", file=sys.stderr)
                continue
            url = url.strip()
            if not url.startswith(("http://", "https://")):
                print("L'URL doit commencer par http:// ou https://", file=sys.stderr)
                continue
            rc = _download_flow(url)
            sys.exit(rc)

        elif action == "search":
            rc = _search_flow()
            if rc != 0:
                sys.exit(rc)
            # Retour au menu après search

        elif action == "history":
            _history_flow()
            print()
