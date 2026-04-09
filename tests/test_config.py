from pathlib import Path

from vdl.config import VdlConfig, load_config


class TestVdlConfigDefaults:
    def test_default_output_dir_is_downloads(self):
        cfg = VdlConfig()
        assert "Downloads" in cfg.output_dir

    def test_default_quality_is_best(self):
        assert VdlConfig().default_quality == "best"

    def test_default_embed_thumbnail(self):
        assert VdlConfig().embed_thumbnail is True

    def test_default_sponsorblock_off(self):
        assert VdlConfig().sponsorblock is False

    def test_default_subs_off(self):
        assert VdlConfig().subs is False

    def test_default_subs_lang(self):
        assert VdlConfig().subs_lang == "fr"

    def test_default_retries(self):
        assert VdlConfig().retries == 3


class TestLoadConfig:
    def test_no_config_file_returns_defaults(self, tmp_path: Path):
        cfg = load_config(tmp_path / "nonexistent.toml")
        assert isinstance(cfg, VdlConfig)

    def test_config_override_output_dir(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('output_dir = "/tmp/videos"\n')
        cfg = load_config(config_file)
        assert cfg.output_dir == "/tmp/videos"

    def test_config_override_quality(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('default_quality = "1080"\n')
        cfg = load_config(config_file)
        assert cfg.default_quality == "1080"

    def test_config_sponsorblock_true(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("sponsorblock = true\n")
        cfg = load_config(config_file)
        assert cfg.sponsorblock is True

    def test_config_subs(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('subs = true\nsubs_lang = "en"\n')
        cfg = load_config(config_file)
        assert cfg.subs is True
        assert cfg.subs_lang == "en"

    def test_config_retries(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("retries = 5\n")
        cfg = load_config(config_file)
        assert cfg.retries == 5

    def test_unknown_keys_ignored(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('unknown_key = "value"\n')
        cfg = load_config(config_file)
        assert isinstance(cfg, VdlConfig)
