"""Interactive downloads and conversions. Run: vdl.

Uses yt-dlp for metadata and downloads, prompt-toolkit for inline choices.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from . import __version__, prefs
from .config import load_config
from .downloader import Downloader, kind, probe
from .i18n import t
from .links import normalize_channel_url
from .tui import (
    BOLD,
    CYAN,
    DIM,
    RESET,
    Spinner,
    c,
    confirm,
    select,
    text,
)


def _banner() -> None:
    print(f"\n{c('  ▸ vdl', BOLD + CYAN)}  {c(__version__, DIM)}")
    print("  Un lien à télécharger, un fichier à convertir, un titre à rechercher.")
    print(c("  /convert  /search  /history  /quit", DIM))
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
        "playlist": False,
        "music": cfg.music,
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


def _options_screen(o: dict[str, object], is_audio: bool) -> dict[str, object] | None:
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
            {"name": "Télécharger avec ces réglages", "value": "back"},
            {"name": "Annuler", "value": "cancel"},
        ]
        choice = select(t("options_title"), choices=rows)
        if choice in (None, "cancel"):
            return None
        if choice == "back":
            return o

        if choice == "quality":
            keys = [q["value"] for q in presets.AUDIO_QUALITIES] if is_audio else presets.QUALITY_KEYS
            rows = presets.AUDIO_QUALITIES if is_audio else presets.VIDEO_QUALITIES
            quality_choices = zip(keys, rows)
            picked = select(
                t("audio_quality") if is_audio else t("video_quality"),
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
        playlist=bool(o["playlist"]),
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
    mode = "AUDIO" if is_audio else "VIDÉO"
    print(c(f"\n  ↓ {mode} · {str(o['ext']).upper()} · lancement du téléchargement", BOLD + CYAN))
    result = dl.download(url, str(o["ext"]), is_audio, quality_selector, audio_kbps, info=info)
    if result.exit_code == 0:
        prefs.remember(is_audio, quality=str(o["quality"]), fmt=str(o["ext"]), output=str(o["output_dir"]))

    if is_audio and result.exit_code == 0 and result.file_path and not o["strip_metadata"]:
        tags = {k: v for k, v in (("title", o["title"]), ("artist", o["artist"]), ("album", o["album"])) if v}
        if tags:
            from .music import _auto_install_deps, write_tags

            if _auto_install_deps():
                write_tags(result.file_path, tags)

    if is_audio and result.exit_code == 0 and result.file_path and o["music"]:
        from .music import music_pipeline

        music_pipeline(result.file_path, result.info)

    return result.exit_code


def _single_flow(
    url: str, info: dict[str, Any], is_live: bool, state: dict[str, Any], cfg: Any, *, playlist: bool = False
) -> int:
    """Choose and adjust the download on one keyboard-driven screen."""
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.output import ColorDepth

    from . import presets

    title = info.get("title") or "Video"
    detail = "LIVE" if is_live else "playlist" if playlist else _fmt_dur(info.get("duration"))
    print(c("\n  ✓ Lien reconnu", CYAN))
    print(f"  {c(str(title), BOLD)}  {c(detail, DIM)}")
    video_o = _default_options(False, state, cfg)
    audio_o = _default_options(True, state, cfg)
    for options in (video_o, audio_o):
        options["playlist"] = playlist
    is_audio = state.get("mode") == "audio"
    keys = KeyBindings()
    changed = ""
    changed_at = 0.0
    notice = "Tes derniers réglages sont prêts."
    reduced_motion = "VDL_REDUCED_MOTION" in os.environ or "NO_COLOR" in os.environ

    def render() -> list[tuple[str, str]]:
        o = audio_o if is_audio else video_o
        quality = str(o["quality"])
        if is_audio:
            quality = "sans perte" if o["ext"] in ("flac", "wav") else f"{quality} kbps"
        else:
            quality = "qualité max" if quality == "best" else f"{quality}p"
        flags = []
        if o["section"]:
            flags.append(f"extrait {o['section']}")
        if o["subs"]:
            flags.append("sous-titres")
        if o["sponsorblock"]:
            flags.append("SponsorBlock")
        details = f" · {', '.join(flags)}" if flags else ""
        accent = "fg:ansicyan bold"
        active = "bg:ansicyan fg:ansiblack bold"
        hint = "fg:ansibrightblack"
        flash = "reverse bold" if not reduced_motion and time.monotonic() - changed_at < 0.2 else accent
        fragments = [
            ("", "\n  "),
            (active if not is_audio else hint, " ▸ VIDÉO " if not is_audio else "   VIDÉO "),
            ("", "  "),
            (active if is_audio else hint, " ▸ AUDIO " if is_audio else "   AUDIO "),
            (hint, "   Tab pour basculer\n\n  "),
            (hint, "FORMAT   "),
            (flash if changed == "ext" else accent, f"[ {str(o['ext']).upper()} ]"),
            (hint, "  ↑ ↓    QUALITÉ   "),
            (flash if changed == "quality" else accent, f"[ {quality} ]"),
            (hint, "  ← →\n"),
            ("", f"  → {o['output_dir']}{details}\n\n  "),
            ("fg:ansigreen", f"✓ {notice}\n\n  "),
            (active, " ↵ Télécharger "),
            ("", "   "),
            (accent, "a"),
            ("", " audio direct   "),
            (accent, "v"),
            ("", " vidéo directe"),
        ]
        if sys.platform == "darwin":
            fragments += [(accent, "   m"), ("", " Apple Music")]
        fragments += [(hint, "\n\n  d dossier   e extrait   o options   Échap retour\n")]
        return fragments

    @keys.add("tab")
    def toggle(event: KeyPressEvent) -> None:
        nonlocal is_audio, changed, changed_at, notice
        is_audio = not is_audio
        changed, changed_at = "mode", time.monotonic()
        notice = "Audio sélectionné." if is_audio else "Vidéo sélectionnée."

    @keys.add("left")
    @keys.add("right")
    @keys.add("up")
    @keys.add("down")
    def adjust(event: KeyPressEvent) -> None:
        nonlocal changed, changed_at, notice
        key = event.key_sequence[-1].key
        o = audio_o if is_audio else video_o
        if key in (Keys.Left, Keys.Right):
            if is_audio and o["ext"] in ("flac", "wav"):
                notice = "Format sans perte : aucun débit à régler."
                return
            values = [q["value"] for q in presets.AUDIO_QUALITIES] if is_audio else presets.QUALITY_KEYS
            field = "quality"
        else:
            values = [f["ext"] for f in (presets.AUDIO_FORMATS if is_audio else presets.VIDEO_FORMATS)]
            field = "ext"
        step = 1 if key in (Keys.Right, Keys.Down) else -1
        o[field] = values[(values.index(str(o[field])) + step) % len(values)]
        changed, changed_at = field, time.monotonic()
        notice = f"{'Format' if field == 'ext' else 'Qualité'} : {str(o[field]).upper()}."
        if event.app.loop is not None and not reduced_motion:
            event.app.loop.call_later(0.2, event.app.invalidate)

    @keys.add("enter")
    @keys.add("a")
    @keys.add("v")
    @keys.add("m")
    @keys.add("d")
    @keys.add("e")
    @keys.add("o")
    @keys.add("escape", eager=True)
    @keys.add("c-c")
    @keys.add("c-d")
    def choose(event: KeyPressEvent) -> None:
        event.app.exit(result=str(event.key_sequence[-1].key))

    app: Application[str] = Application(
        layout=Layout(Window(FormattedTextControl(render), dont_extend_height=True, always_hide_cursor=True)),
        key_bindings=keys,
        erase_when_done=True,
        color_depth=ColorDepth.DEPTH_1_BIT if "NO_COLOR" in os.environ else None,
    )
    while True:
        try:
            action = app.run()
        except EOFError:
            return 0
        if action in (str(Keys.Escape), str(Keys.ControlC), str(Keys.ControlD)):
            return 0
        if action in ("a", "m", "v"):
            is_audio = action != "v"
        o = audio_o if is_audio else video_o
        if action in ("d", "e"):
            field = "output_dir" if action == "d" else "section"
            value = text("Dossier" if action == "d" else "Extrait (ex. 12:00-14:30)", default=str(o[field] or ""))
            if value is not None and (value.strip() or field == "section"):
                o[field] = value.strip() or None
                notice = "Dossier modifié." if field == "output_dir" else "Extrait modifié."
        elif action == "o":
            chosen = _options_screen(o, is_audio)
            if chosen is None:
                continue
            return _run_download(url, is_audio, chosen, info)
        else:
            o["music"] = action == "m" or cfg.music
            return _run_download(url, is_audio, o, info)


def _download_flow(url: str) -> int:
    """Probe the URL once, then choose download settings on one screen."""
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
    return _single_flow(url, info, result_kind == "live", state, cfg, playlist=result_kind == "playlist")


def _search_flow(query: str = "", source: str | None = None) -> int:
    """Flux recherche avec sélection du résultat."""
    from .search import SOURCES, search_videos

    source_choice = source or select(
        t("search_on"),
        choices=[
            {"name": "YouTube", "value": "youtube"},
            {"name": "SoundCloud", "value": "soundcloud"},
        ],
    )
    if source_choice is None:
        return 0

    query = query or text(t("search_query")) or ""
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


def _convert_flow(path: str | None = None) -> None:
    """Convertit un fichier local : chemin -> audio/video -> format -> qualite."""
    from . import presets
    from .convert import local_path, run_convert

    path = path or text(t("convert_prompt_file"))
    if not path or not path.strip():
        return

    src = local_path(path)
    if not src.is_file():
        print(t("err_no_file", name=src), file=sys.stderr)
        return
    ext = select(
        "Convertir en…",
        choices=[f["label"] for f in presets.AUDIO_FORMATS + presets.VIDEO_FORMATS],
    )
    if not ext:
        return
    run_convert([str(src), "-f", ext.lower()])


# ── Point d'entrée principal ───────────────────────────────────────────────


def run_interactive() -> None:
    _banner()
    from .convert import is_local_target, local_path

    while True:
        raw = text("Lien, fichier ou recherche (Entrée pour quitter)")
        if not raw or not raw.strip() or raw.strip() == "/quit":
            return
        raw = raw.strip()
        command, _, argument = raw.partition(" ")
        if command == "/convert":
            _convert_flow(argument or None)
        elif command == "/search":
            _search_flow(query=argument)
        elif command == "/history":
            _history_flow()
        elif raw.startswith("/") and "/" not in raw[1:] and "." not in raw and not local_path(raw).exists():
            print("Commande inconnue. Utilise /convert, /search, /history ou /quit.", file=sys.stderr)
        elif is_local_target(raw):
            _convert_flow(raw)
        elif raw.startswith(("http://", "https://", "@")) or ("." in raw.split("/")[0] and " " not in raw):
            _download_flow(normalize_input(raw))
        else:
            _search_flow(query=raw, source="youtube")
        print()
