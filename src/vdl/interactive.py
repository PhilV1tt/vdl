"""Mode interactif avec navigation clavier (questionary).

Flux : coller un lien -> une sonde (probe) -> un écran rapide avec défauts intelligents
(mémorisés côté audio et côté vidéo séparément) -> "Options..." pour tout le reste.
"""

from __future__ import annotations

import sys
from typing import Any

from . import __version__, prefs
from .config import load_config
from .downloader import Downloader, kind, probe
from .i18n import t
from .links import normalize_channel_url
from .tui import (
    BLUE,
    BOLD,
    CYAN,
    DIM,
    RED,
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
    """Propose une mise à jour si une nouvelle version est disponible."""
    from .updater import do_update, get_latest_version

    latest = get_latest_version()
    if not latest:
        return

    print(f"  {BOLD}{YELLOW}↑{RESET}  {t('update_available', version=latest)}")
    print()
    if confirm(t("update_now"), default=True):
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


# ── Saisie de l'URL ─────────────────────────────────────────────────────────


def normalize_input(raw: str) -> str:
    """Normalise une entrée utilisateur : @handle ou domaine nu -> URL complète."""
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        return normalize_channel_url(raw)
    return raw


def _fmt_dur(seconds: int | float | None) -> str:
    if not seconds:
        return ""
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


# ── Options (divulgation progressive) ───────────────────────────────────────

_BROWSERS = ["chrome", "safari", "firefox", "edge", "brave"]


def _ask_metadata(is_audio: bool, strip_default: bool) -> dict[str, object]:
    strip = confirm(t("opt_strip_meta"), default=strip_default)
    title = (text(t("opt_title")) or "").strip() or None
    no_thumb = confirm(t("opt_no_thumb"), default=False) if is_audio else False
    artist = album = None
    if is_audio and not strip:
        artist = (text(t("opt_artist")) or "").strip() or None
        album = (text(t("opt_album")) or "").strip() or None
    return {"title": title, "artist": artist, "album": album, "strip_metadata": strip, "no_thumbnail": no_thumb}


def _default_options(is_audio: bool, state: dict[str, Any], cfg: Any) -> dict[str, object]:
    quality, ext, output_dir = prefs.resolve(None, None, None, is_audio, state, cfg)
    return {
        "quality": quality,
        "ext": ext,
        "output_dir": output_dir,
        "section": None,
        "subs": cfg.subs,
        "sponsorblock": cfg.sponsorblock,
        "title": None,
        "artist": None,
        "album": None,
        "strip_metadata": False,
        "no_thumbnail": False,
        "cookies_browser": None,
        "concurrent_fragments": cfg.concurrent_fragments,
        "use_aria2c": cfg.aria2c,
    }


def _options_screen(o: dict[str, object], is_audio: bool) -> dict[str, object]:
    """Un seul niveau de profondeur : qualité, format, dossier, extrait, subs, sponsorblock, métadonnées, cookies."""
    from . import presets

    yes, no = t("opt_yes"), t("opt_no")

    while True:
        rows = [
            {"name": f"{t('lbl_quality')}  {o['quality']}", "value": "quality"},
            {"name": f"{t('opt_format_label')}  {str(o['ext']).upper()}", "value": "format"},
            {"name": f"{t('lbl_output')}  {o['output_dir']}", "value": "output"},
            {"name": f"{t('opt_section_label')}  {o['section'] or t('opt_section_none')}", "value": "section"},
            {"name": f"{t('lbl_subs')}  {yes if o['subs'] else no}", "value": "subs"},
            {"name": f"{t('lbl_sponsorblock')}  {yes if o['sponsorblock'] else no}", "value": "sponsorblock"},
            {"name": t("opt_metadata_label"), "value": "meta"},
            {"name": f"{t('opt_cookies_label')}  {o['cookies_browser'] or t('opt_cookies_none')}", "value": "cookies"},
            {"name": f"← {t('opt_back')}", "value": "back"},
        ]
        choice = select(t("options_title"), choices=rows)
        if choice is None or choice == "back":
            return o

        if choice == "quality":
            quality_choices = zip(presets.QUALITY_KEYS, presets.VIDEO_QUALITIES)
            picked = select(
                t("video_quality"),
                choices=[{"name": q["label"], "value": k} for k, q in quality_choices],
            )
            if picked:
                o["quality"] = picked
        elif choice == "format":
            table = presets.AUDIO_FORMATS if is_audio else presets.VIDEO_FORMATS
            picked_f = select(t("opt_format_prompt"), choices=[{"name": f["label"], "value": f["ext"]} for f in table])
            if picked_f:
                o["ext"] = picked_f
        elif choice == "output":
            d = text(t("output_dir_prompt"), default=str(o["output_dir"]))
            if d and d.strip():
                o["output_dir"] = d.strip()
        elif choice == "section":
            s = text(t("opt_section_prompt"), default=str(o["section"] or ""))
            if s is not None:
                o["section"] = s.strip() or None
        elif choice == "subs":
            o["subs"] = confirm(t("subs_prompt"), default=bool(o["subs"]))
        elif choice == "sponsorblock":
            o["sponsorblock"] = confirm(t("sponsorblock_prompt"), default=bool(o["sponsorblock"]))
        elif choice == "meta":
            o.update(_ask_metadata(is_audio, bool(o["strip_metadata"])))
        elif choice == "cookies":
            picked_b = select(
                t("opt_cookies_prompt"),
                choices=[{"name": t("opt_cookies_none"), "value": ""}]
                + [{"name": b.title(), "value": b} for b in _BROWSERS],
            )
            o["cookies_browser"] = picked_b or None


# ── Téléchargement ───────────────────────────────────────────────────────────


def _run_download(url: str, is_audio: bool, o: dict[str, object], info: dict[str, Any] | None) -> int:
    from . import presets

    quality_selector, audio_kbps = presets.build_quality_selector(is_audio, str(o["quality"]))
    dl = Downloader(
        output_dir=str(o["output_dir"]),
        embed_thumbnail=not o["no_thumbnail"],
        sponsorblock=bool(o["sponsorblock"]),
        subs=bool(o["subs"]),
        strip_metadata=bool(o["strip_metadata"]),
        custom_title=o["title"],  # type: ignore[arg-type]
        sections=[str(o["section"])] if o["section"] else None,
        cookies_browser=o["cookies_browser"],  # type: ignore[arg-type]
        concurrent_fragments=int(o["concurrent_fragments"]),  # type: ignore[call-overload]
        use_aria2c=bool(o["use_aria2c"]),
    )
    print()
    result = dl.download(url, str(o["ext"]), is_audio, quality_selector, audio_kbps, info=info)
    if result.exit_code == 0:
        prefs.remember(is_audio, quality=str(o["quality"]), fmt=str(o["ext"]), output=str(o["output_dir"]))

    if is_audio and result.exit_code == 0 and result.file_path and not o["strip_metadata"]:
        tags = {k: v for k, v in (("title", o["title"]), ("artist", o["artist"]), ("album", o["album"])) if v}
        if tags:
            from .music import _auto_install_deps, write_tags

            if _auto_install_deps():
                write_tags(result.file_path, tags)

    if is_audio and result.exit_code == 0 and result.file_path and sys.platform == "darwin":
        print()
        if confirm(t("music_import_ask"), default=False):
            from .music import music_pipeline

            music_pipeline(result.file_path, result.info)

    return result.exit_code


def _playlist_flow(url: str, info: dict[str, Any], state: dict[str, Any], cfg: Any) -> int:
    """Playlist/chaîne entière : propose 'toute' + 'cette vidéo' si l'URL cible aussi une vidéo précise."""
    from urllib.parse import parse_qs, urlparse

    from . import presets

    n = len(info.get("entries") or [])
    title = info.get("title") or url
    has_video = "v" in parse_qs(urlparse(url).query)

    rows = [{"name": t("opt_whole_playlist", n=n), "value": "all"}]
    if has_video:
        rows.insert(0, {"name": t("opt_this_video"), "value": "one"})
    rows.append({"name": f"← {t('opt_back')}", "value": "back"})

    choice = select(str(title), choices=rows)
    if choice in (None, "back"):
        return 0

    if choice == "one":
        with Spinner(t("fetching")):
            single = probe(url, single=True)
        if single is None:
            print(t("err_extract"), file=sys.stderr)
            return 1
        return _single_flow(url, single, kind(single) == "live", state, cfg)

    is_audio = confirm(f"{t('opt_audio')} ?", default=False)
    o = _default_options(is_audio, state, cfg)
    print()
    quality_selector, audio_kbps = presets.build_quality_selector(is_audio, str(o["quality"]))
    dl = Downloader(
        output_dir=str(o["output_dir"]),
        playlist=True,
        embed_thumbnail=not o["no_thumbnail"],
        concurrent_fragments=int(o["concurrent_fragments"]),  # type: ignore[call-overload]
        use_aria2c=bool(o["use_aria2c"]),
    )
    result = dl.download(url, str(o["ext"]), is_audio, quality_selector, audio_kbps)
    if result.exit_code == 0:
        prefs.remember(is_audio, quality=str(o["quality"]), fmt=str(o["ext"]), output=str(o["output_dir"]))
    return result.exit_code


def _single_flow(url: str, info: dict[str, Any], is_live: bool, state: dict[str, Any], cfg: Any) -> int:
    """Écran rapide : Télécharger (défauts) / Plutôt l'audio / Options..."""
    title = info.get("title", "Video") or "Video"
    dur = _fmt_dur(info.get("duration")) if not is_live else ""

    header = f"  {BOLD}{title}{RESET}"
    if is_live:
        header += f"  {BOLD}{RED}● LIVE{RESET}"
    elif dur:
        header += f"  {DIM}{dur}{RESET}"
    print(header)
    print()

    video_o = _default_options(False, state, cfg)
    audio_o = _default_options(True, state, cfg)

    choices = []
    if is_live:
        choices.append({"name": t("opt_live_record"), "value": "download"})
    else:
        choices.append(
            {
                "name": f"{t('opt_download')}  ·  Vidéo · {video_o['quality']} · {str(video_o['ext']).upper()} "
                f"· {video_o['output_dir']}",
                "value": "download",
            }
        )
        choices.append(
            {
                "name": f"{t('opt_audio_instead')}  ·  {str(audio_o['ext']).upper()} · {audio_o['quality']} kbps",
                "value": "audio",
            }
        )
    choices.append({"name": t("opt_options"), "value": "options"})

    action = select(" ", choices=choices)  # le titre est déjà affiché au-dessus
    if action is None:
        return 0

    if action == "options":
        is_audio = False if is_live else confirm(f"{t('opt_audio')} ?", default=False)
        chosen = _options_screen(dict(audio_o if is_audio else video_o), is_audio)
        return _run_download(url, is_audio, chosen, info)

    is_audio = action == "audio"
    return _run_download(url, is_audio, audio_o if is_audio else video_o, info)


def _download_flow(url: str) -> int:
    """Sonde l'URL une fois, propose un écran rapide avec défauts intelligents, options une porte plus loin."""
    cfg = load_config()
    state = prefs.recall()

    with Spinner(t("fetching")):
        info = probe(url)
    if info is None:
        print(t("err_extract"), file=sys.stderr)
        return 1

    result_kind = kind(info)
    if result_kind == "upcoming":
        from .downloader import _print_upcoming

        _print_upcoming(info)
        return 0
    if result_kind == "playlist":
        return _playlist_flow(url, info, state, cfg)
    return _single_flow(url, info, result_kind == "live", state, cfg)


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
            raw = text(t("prompt_url"))
            if not raw or not raw.strip():
                print(t("err_empty_url"), file=sys.stderr)
                continue
            url = normalize_input(raw)
            _download_flow(url)
            while True:
                again = text(t("another_link"), default="")
                if not again or not again.strip():
                    break
                _download_flow(normalize_input(again))
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
