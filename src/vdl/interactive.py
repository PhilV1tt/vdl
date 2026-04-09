"""Mode interactif avec navigation clavier (questionary)."""

from __future__ import annotations

import sys
import time

from . import __version__, presets
from .downloader import DEFAULT_OUTPUT, Downloader
from .i18n import t
from .tui import BLUE, BOLD, CYAN, DIM, GREEN, RESET, Spinner, c, confirm, select, text

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
    print(f"  {DIM}{t('banner_sub')}  {RESET}{CYAN}v{__version__}{RESET}")
    print()


# ── Flux téléchargement ────────────────────────────────────────────────────


def _download_flow(url: str) -> int:
    """Collecte les options et lance le téléchargement."""
    # Type
    type_choice = select(
        t("audio_or_video"),
        choices=[
            {"name": t("opt_video"), "value": "video"},
            {"name": t("opt_audio"), "value": "audio"},
        ],
    )
    if type_choice is None:
        return 0
    is_audio = type_choice == "audio"

    if is_audio:
        fmt_choice = select(
            t("audio_format"),
            choices=[{"name": f["label"], "value": f["ext"]} for f in presets.AUDIO_FORMATS],
        )
        if fmt_choice is None:
            return 0
        ext: str = fmt_choice

        q_choice = select(
            t("audio_quality"),
            choices=[{"name": q["label"], "value": q["value"]} for q in presets.AUDIO_QUALITIES],
        )
        if q_choice is None:
            return 0
        audio_kbps: str = q_choice
        quality_selector = "bestaudio/best"
    else:
        fmt_choice = select(
            t("video_format"),
            choices=[{"name": f["label"], "value": f["ext"]} for f in presets.VIDEO_FORMATS],
        )
        if fmt_choice is None:
            return 0
        ext = fmt_choice

        q_choice = select(
            t("video_quality"),
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
        subs = confirm(t("subs_prompt"), default=False)
        if subs:
            lang = text(t("subs_lang_prompt"), default="fr")
            subs_lang = lang if lang else "fr"

    # SponsorBlock
    sponsorblock = False
    if not is_audio:
        sponsorblock = confirm(t("sponsorblock_prompt"), default=False)

    # Dossier de sortie
    output_raw = text(t("output_dir_prompt"), default=DEFAULT_OUTPUT)
    output = output_raw if output_raw else DEFAULT_OUTPUT

    # Récapitulatif
    _B = f"{CYAN}│{RESET}"
    print()
    print(f"  {CYAN}┌─ {t('summary_title')} {'─' * (39 - len(t('summary_title')))}┐{RESET}")
    url_short = (url[:48] + "…") if len(url) > 50 else url
    print(f"  {_B}  {t('lbl_url'):<8}: {DIM}{url_short}{RESET}")
    type_label = c(t("opt_audio"), GREEN) if is_audio else c(t("opt_video"), BLUE)
    print(f"  {_B}  {t('lbl_type'):<8}: {type_label} {BOLD}{ext.upper()}{RESET}")
    if not is_audio:
        q_label = next(
            (q["label"] for q in presets.VIDEO_QUALITIES if q["value"] == quality_selector),
            quality_selector,
        )
        print(f"  {_B}  {t('lbl_quality'):<8}: {q_label}")
    if subs:
        print(f"  {_B}  {t('lbl_subs'):<8}: {c(subs_lang, CYAN)}")
    if sponsorblock:
        print(f"  {_B}  {t('lbl_sponsorblock')}: {c(t('sb_active'), GREEN)}")
    print(f"  {_B}  {t('lbl_output'):<8}: {DIM}{output}{RESET}")
    print(f"  {CYAN}└──────────────────────────────────────────┘{RESET}")
    print()

    if not confirm(t("confirm_dl"), default=True):
        print(c(t("cancelled"), DIM))
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
        return 1

    from .search import _fmt_duration, _fmt_views

    def _label(r: dict[str, object]) -> str:
        title = str(r.get("title", "?"))[:55]
        dur = _fmt_duration(r.get("duration"))  # type: ignore[arg-type]
        views = _fmt_views(r.get("view_count"))  # type: ignore[arg-type]
        meta = "  ".join(filter(None, [dur, views]))
        return f"{title}  [{meta}]" if meta else title

    choices = [{"name": _label(r), "value": str(r["url"])} for r in results]
    choices.append({"name": f"← {t('opt_back')}", "value": "__back__"})

    url_choice = select(t("pick_result"), choices=choices)
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
            "?",
            choices=[
                {"name": t("menu_download"), "value": "download"},
                {"name": t("menu_search"), "value": "search"},
                {"name": t("menu_history"), "value": "history"},
                {"name": t("menu_quit"), "value": "quit"},
            ],
        )

        if action is None or action == "quit":
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
