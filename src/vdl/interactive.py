"""Mode interactif avec navigation clavier (questionary)."""

from __future__ import annotations

import sys

from . import __version__
from .downloader import DEFAULT_OUTPUT, Downloader
from .i18n import t
from .tui import (
    BLUE,
    BOLD,
    CYAN,
    DIM,
    RESET,
    YELLOW,
    Spinner,
    animate_separator,
    clear_screen,
    confirm,
    fade_out,
    select,
    text,
    type_print,
)

# ── Bannière ───────────────────────────────────────────────────────────────

_ASCII = [
    r" ██╗   ██╗██████╗ ██╗     ",
    r" ██║   ██║██╔══██╗██║     ",
    r" ██║   ██║██║  ██║██║     ",
    r" ╚██╗ ██╔╝██║  ██║██║     ",
    r"  ╚████╔╝ ██████╔╝███████╗",
    r"   ╚═══╝  ╚═════╝ ╚══════╝",
]


def _auto_update() -> None:
    """Met à jour automatiquement si une nouvelle version est disponible."""
    from .updater import do_update, get_latest_version

    latest = get_latest_version()
    if not latest:
        return

    print(f"  {BOLD}{YELLOW}↑{RESET}  {t('update_available', version=latest)}  {DIM}— mise à jour...{RESET}")
    print()
    do_update()
    print()
    animate_separator(color=CYAN)
    print()


def _banner() -> None:
    clear_screen()
    print()
    # ASCII art affiché d'un coup, sans délai ligne par ligne
    for i, line in enumerate(_ASCII):
        color = CYAN if i < 3 else BLUE
        print(f"{BOLD}{color}{line}{RESET}")
    print()
    # Seul le sous-titre a un effet typewriter (rapide)
    type_print(t("banner_sub"), prefix=f"  {DIM}", delay=0.015)
    print(f"  {CYAN}v{__version__}{RESET}")
    print()
    animate_separator(color=CYAN)
    print()


# ── Flux téléchargement ────────────────────────────────────────────────────


def _download_flow(url: str) -> int:
    """Demande Audio ou Vidéo, télécharge, propose Apple Music si audio sur macOS."""
    type_choice = select(
        t("audio_or_video"),
        choices=[
            {"name": t("opt_video") + "  (MP4)", "value": "video"},
            {"name": t("opt_audio") + "  (MP3)", "value": "audio"},
        ],
    )
    if type_choice is None:
        return 0

    is_audio = type_choice == "audio"
    ext = "mp3" if is_audio else "mp4"
    from . import presets

    quality_selector, audio_kbps = presets.build_quality_selector(is_audio)

    print()
    dl = Downloader(output_dir=DEFAULT_OUTPUT)
    result = dl.download(url, ext, is_audio, quality_selector, audio_kbps)

    if is_audio and result.exit_code == 0 and result.file_path and sys.platform == "darwin":
        print()
        if confirm(t("music_import_ask"), default=False):
            from .music import music_pipeline

            music_pipeline(result.file_path, result.info)

    return result.exit_code


def _search_flow() -> int:
    """Flux recherche avec sélection du résultat."""
    from .search import SOURCES, search_videos

    source_choice = select(
        t("search_on"),
        choices=[
            {"name": "YouTube", "value": "youtube"},
            {"name": "SoundCloud", "value": "soundcloud"},
        ],
    )
    if source_choice is None:
        return 0

    query = text(t("search_query"))
    if not query or not query.strip():
        return 0

    source_name = next((k for k in SOURCES if k == source_choice), "youtube")
    print()
    with Spinner(t("searching", source=source_name.title())):
        results = search_videos(query.strip(), source=source_name)
    if not results:
        print(t("no_results"), file=sys.stderr)
        return 0

    from .search import _fmt_duration, _fmt_views

    def _label(r: dict[str, object]) -> str:
        title = str(r.get("title", "?"))[:55]
        dur = _fmt_duration(r.get("duration"))  # type: ignore[arg-type]
        views = _fmt_views(r.get("view_count"))  # type: ignore[arg-type]
        meta = "  ".join(filter(None, [dur, views]))
        return f"{title}  {DIM}[{meta}]{RESET}" if meta else title

    choices = [{"name": _label(r), "value": str(r["url"])} for r in results]
    choices.append({"name": f"← {t('opt_back')}", "value": "__back__"})

    url_choice = select(t("pick_result"), choices=choices)
    if url_choice is None or url_choice == "__back__":
        return 0

    return _download_flow(url_choice)


def _history_flow() -> None:
    """Affiche l'historique."""
    from .history import show_history

    show_history()


# ── Point d'entrée principal ───────────────────────────────────────────────


def run_interactive() -> None:
    _banner()
    _auto_update()

    while True:
        action = select(
            t("menu_prompt"),
            choices=[
                {"name": t("menu_download"), "value": "download"},
                {"name": t("menu_search"), "value": "search"},
                {"name": t("menu_history"), "value": "history"},
                {"name": t("menu_quit"), "value": "quit"},
            ],
        )

        if action is None or action == "quit":
            print()
            fade_out("bye", color=CYAN)
            print()
            sys.exit(0)

        if action == "download":
            url = text(t("prompt_url"))
            if not url or not url.strip():
                print(t("err_empty_url"), file=sys.stderr)
                continue
            url = url.strip()
            if not url.startswith(("http://", "https://")):
                print(t("err_bad_url"), file=sys.stderr)
                continue
            _download_flow(url)
            print()
            animate_separator()
            print()

        elif action == "search":
            _search_flow()
            print()
            animate_separator()
            print()

        elif action == "history":
            _history_flow()
            print()
            animate_separator()
            print()
