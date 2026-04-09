"""Internationalisation minimale : détection automatique FR/EN."""

from __future__ import annotations

import locale


def _detect_lang() -> str:
    try:
        code = locale.getlocale()[0] or ""
    except Exception:
        code = ""
    return "fr" if code.lower().startswith("fr") else "en"


LANG = _detect_lang()

_S: dict[str, dict[str, str]] = {
    "fr": {
        # Banner
        "banner_sub": "Telechargeur universel de videos",
        # Menu principal
        "menu_prompt": "Que veux-tu faire ?",
        "menu_download": "Telecharger depuis une URL",
        "menu_search": "Rechercher sur YouTube / SoundCloud",
        "menu_history": "Historique",
        "menu_quit": "Quitter",
        # Download flow
        "prompt_url": "Lien de la video :",
        "err_empty_url": "URL vide.",
        "err_bad_url": "URL invalide (doit commencer par http:// ou https://)",
        "audio_or_video": "Audio ou video ?",
        "opt_video": "Video",
        "opt_audio": "Audio",
        "audio_format": "Format audio ?",
        "audio_quality": "Qualite audio ?",
        "video_format": "Format video ?",
        "video_quality": "Qualite video ?",
        "subs_prompt": "Telecharger les sous-titres ?",
        "subs_lang_prompt": "Langue des sous-titres ?",
        "sponsorblock_prompt": "Supprimer les segments SponsorBlock ?",
        "output_dir_prompt": "Dossier de sortie ?",
        "summary_title": "Recapitulatif",
        "lbl_url": "URL",
        "lbl_type": "Type",
        "lbl_quality": "Qualite",
        "lbl_subs": "Subs",
        "lbl_sponsorblock": "SponsorBlock",
        "lbl_output": "Sortie",
        "sb_active": "actif",
        "confirm_dl": "Confirmer le telechargement ?",
        "cancelled": "Annule.",
        # Search flow
        "search_on": "Chercher sur ?",
        "search_query": "Rechercher :",
        "searching": "Recherche sur {source}...",
        "no_results": "Aucun resultat.",
        "pick_result": "Choisir un resultat :",
        "opt_back": "Retour",
        # Downloader
        "fetching": "Recuperation des infos...",
        "saved": "Sauvegarde dans {path}/",
        "retry": "Erreur reseau. Nouvel essai {attempt}/{max} dans {wait}s...",
        "err_unsupported": "Site non supporte : {url}",
        "err_unsupported_hint": "  vdl --list-sites pour voir les sites supportes.",
        "err_private": "Video privee. Verifie l'URL ou tes permissions.",
        "err_unavailable": "Video indisponible (supprimee ou geo-restreinte).",
        "err_429": "Trop de requetes (429). Attends quelques minutes.",
        "err_extract": "Impossible d'extraire. Essaie : yt-dlp -U",
        "converting": "Conversion en cours...",
        "err_interrupted": "Annule.",
        "missing_deps": "Dependances manquantes :",
        # History
        "history_title": "Derniers {n} telechargements",
        "no_history": "Aucun historique.",
        # Update
        "update_pipx": "Mise a jour via pipx...",
        "update_pip": "Mise a jour via pip...",
        "update_yt_dlp": "Pour mettre a jour yt-dlp aussi :\n  pipx upgrade yt-dlp",
        "update_available": "Nouvelle version disponible : v{version}",
        "update_now": "Mettre a jour maintenant ?",
        # Search views
        "views": "vues",
    },
    "en": {
        # Banner
        "banner_sub": "Universal video downloader",
        # Main menu
        "menu_prompt": "What do you want to do?",
        "menu_download": "Download from a URL",
        "menu_search": "Search on YouTube / SoundCloud",
        "menu_history": "History",
        "menu_quit": "Quit",
        # Download flow
        "prompt_url": "Video URL:",
        "err_empty_url": "Empty URL.",
        "err_bad_url": "Invalid URL (must start with http:// or https://)",
        "audio_or_video": "Audio or video?",
        "opt_video": "Video",
        "opt_audio": "Audio",
        "audio_format": "Audio format?",
        "audio_quality": "Audio quality?",
        "video_format": "Video format?",
        "video_quality": "Video quality?",
        "subs_prompt": "Download subtitles?",
        "subs_lang_prompt": "Subtitle language?",
        "sponsorblock_prompt": "Remove SponsorBlock segments?",
        "output_dir_prompt": "Output folder?",
        "summary_title": "Summary",
        "lbl_url": "URL",
        "lbl_type": "Type",
        "lbl_quality": "Quality",
        "lbl_subs": "Subs",
        "lbl_sponsorblock": "SponsorBlock",
        "lbl_output": "Output",
        "sb_active": "active",
        "confirm_dl": "Confirm download?",
        "cancelled": "Cancelled.",
        # Search flow
        "search_on": "Search on?",
        "search_query": "Search:",
        "searching": "Searching on {source}...",
        "no_results": "No results.",
        "pick_result": "Pick a result:",
        "opt_back": "Back",
        # Downloader
        "fetching": "Fetching info...",
        "saved": "Saved to {path}/",
        "retry": "Network error. Retry {attempt}/{max} in {wait}s...",
        "err_unsupported": "Unsupported site: {url}",
        "err_unsupported_hint": "  vdl --list-sites to see supported sites.",
        "err_private": "Private video. Check the URL or your permissions.",
        "err_unavailable": "Video unavailable (deleted or geo-restricted).",
        "err_429": "Too many requests (429). Wait a few minutes.",
        "err_extract": "Cannot extract. Try: yt-dlp -U",
        "converting": "Converting...",
        "err_interrupted": "Cancelled.",
        "missing_deps": "Missing dependencies:",
        # History
        "history_title": "Last {n} downloads",
        "no_history": "No download history.",
        # Update
        "update_pipx": "Updating via pipx...",
        "update_pip": "Updating via pip...",
        "update_yt_dlp": "To also update yt-dlp:\n  pipx upgrade yt-dlp",
        "update_available": "New version available: v{version}",
        "update_now": "Update now?",
        # Search views
        "views": "views",
    },
}


def t(key: str, **kwargs: object) -> str:
    """Retourne la chaîne traduite pour la langue détectée."""
    s = _S.get(LANG, _S["en"]).get(key, key)
    return s.format(**kwargs) if kwargs else s
