"""Tests for closed-circuit adaptive seed feedback loop."""

from agents.trend_scout.adaptive_seeds import (
    format_theme_search_keyword,
    get_adaptive_scrape_keywords,
)
from core.config import get_settings


class TestFormatThemeSearchKeyword:
    """Verify theme string normalization and high-intent query mapping."""

    def test_known_mappings_exact(self) -> None:
        """Ensure curated theme niches map to high-intent Shopee search terms."""
        expected_mappings = {
            "anime e geek": "camiseta anime geek",
            "religioso e cristao": "camiseta gospel crista",
            "religioso e cristão": "camiseta gospel crista",
            "country e sertanejo": "camiseta country agro",
            "rock e musica": "camiseta rock vintage",
            "rock e música": "camiseta rock vintage",
            "academia e fitness": "camiseta gym academia",
            "automotivo e motorsport": "camiseta automotiva moto",
            "geek e super-herois": "camiseta geek",
            "geek e super-heróis": "camiseta geek",
            "pets e animais": "camiseta pets",
            "memes e humor": "camiseta memes",
            "k-pop": "camiseta kpop",
            "vintage e retro": "camiseta vintage",
            "vintage e retrô": "camiseta vintage",
        }
        for theme, expected in expected_mappings.items():
            assert format_theme_search_keyword(theme) == expected

    def test_diacritics_and_casing_and_punctuation(self) -> None:
        """Verify normalization handles mixed casing, diacritics, and punctuation."""
        assert format_theme_search_keyword("  Rock e Música!  ") == "camiseta rock vintage"
        assert format_theme_search_keyword("K-POP") == "camiseta kpop"
        assert format_theme_search_keyword("ANIME E GEEK") == "camiseta anime geek"
        assert format_theme_search_keyword("Religioso e Cristão...") == "camiseta gospel crista"

    def test_fallback_with_camiseta_prefix(self) -> None:
        """Verify themes already prefixed with 'camiseta' preserve their prefix."""
        assert format_theme_search_keyword("camiseta minimalista") == "camiseta minimalista"
        assert (
            format_theme_search_keyword("Camiseta Oversized Floral")
            == "camiseta oversized floral"
        )

    def test_fallback_without_camiseta_prefix(self) -> None:
        """Verify unmapped themes receive the 'camiseta' search prefix."""
        assert format_theme_search_keyword("minimalista") == "camiseta minimalista"
        assert format_theme_search_keyword("floral vintage") == "camiseta floral vintage"

    def test_empty_and_punctuation_fallback(self) -> None:
        """Verify degenerate inputs fall back gracefully to base 'camiseta'."""
        assert format_theme_search_keyword("") == "camiseta"
        assert format_theme_search_keyword("   ") == "camiseta"
        assert format_theme_search_keyword("!!!") == "camiseta"


class TestGetAdaptiveScrapeKeywords:
    """Verify adaptive seed resolution, deduplication, filtering, and backfill."""

    def test_high_velocity_report_payload(self) -> None:
        """Verify high velocity themes populate dynamic slots and invalid themes are omitted."""
        payload = {
            "theme_velocities": [
                ["anime e geek", 3000.0],
                ["k-pop", 2500.0],
                ["nao-estampada", 1000.0],
                ["pets e animais", 800.0],
                ["memes e humor", 600.0],
                ["rock e música", 400.0],
            ]
        }
        keywords = get_adaptive_scrape_keywords(report_payload=payload, max_total=8)
        settings = get_settings()

        # 3 permanent anchors must be first
        assert keywords[:3] == settings.scrape_anchor_keywords
        assert len(keywords) == 8

        # nao-estampada must be ignored, dynamic slots filled in order
        dynamic_part = keywords[3:]
        assert "camiseta anime geek" in dynamic_part
        assert "camiseta kpop" in dynamic_part
        assert "camiseta pets" in dynamic_part
        assert "camiseta memes" in dynamic_part
        assert "camiseta rock vintage" in dynamic_part
        assert not any("nao-estampada" in kw for kw in keywords)
        assert not any("nao estampada" in kw for kw in keywords)

    def test_theme_counts_fallback(self) -> None:
        """Verify fallback to theme_counts when theme_velocities is absent."""
        payload = {
            "theme_counts": [
                ["k-pop", 50],
                ["anime e geek", 40],
                ["geral", 30],
                ["pets e animais", 20],
            ]
        }
        keywords = get_adaptive_scrape_keywords(report_payload=payload, max_total=6)
        settings = get_settings()
        assert keywords[:3] == settings.scrape_anchor_keywords
        assert len(keywords) == 6
        assert keywords[3] == "camiseta kpop"
        assert keywords[4] == "camiseta anime geek"
        assert keywords[5] == "camiseta pets"  # "geral" is ignored

    def test_cold_start_fallback(self, tmp_path) -> None:
        """Verify cold start gracefully backfills dynamic slots from static scrape_keywords."""
        empty_dir = tmp_path / "empty_reports"
        empty_dir.mkdir()
        keywords = get_adaptive_scrape_keywords(
            report_payload=None,
            reports_dir=empty_dir,
            max_total=8,
        )
        settings = get_settings()
        assert len(keywords) == 8
        assert keywords[:3] == settings.scrape_anchor_keywords
        # All keywords must be unique
        assert len(set(keywords)) == 8

    def test_max_total_capping(self) -> None:
        """Verify max_total constraints are strictly respected."""
        settings = get_settings()
        # Cap smaller than anchors
        res_2 = get_adaptive_scrape_keywords(report_payload=None, max_total=2)
        assert res_2 == settings.scrape_anchor_keywords[:2]

        # Cap equal to anchors
        res_3 = get_adaptive_scrape_keywords(report_payload=None, max_total=3)
        assert res_3 == settings.scrape_anchor_keywords[:3]

        # Cap between anchors and total
        res_5 = get_adaptive_scrape_keywords(report_payload=None, max_total=5)
        assert len(res_5) == 5
        assert res_5[:3] == settings.scrape_anchor_keywords

    def test_themes_overlapping_with_anchors(self) -> None:
        """Ensure themes already present in permanent anchors do not duplicate."""
        payload = {
            "theme_velocities": [
                ["streetwear", 5000.0],  # resolves to "camiseta streetwear" (matches anchor)
                ["camiseta estampada", 4000.0],  # exact anchor match
                ["k-pop", 3000.0],
                ["anime e geek", 2000.0],
                ["pets e animais", 1000.0],
            ]
        }
        keywords = get_adaptive_scrape_keywords(report_payload=payload, max_total=6)
        settings = get_settings()
        assert keywords[:3] == settings.scrape_anchor_keywords
        # Only non-anchor themes should occupy dynamic slots
        assert keywords[3] == "camiseta kpop"
        assert keywords[4] == "camiseta anime geek"
        assert keywords[5] == "camiseta pets"
        assert len(keywords) == 6
        assert len(set(keywords)) == 6

    def test_filesystem_report_discovery(self, tmp_path) -> None:
        """Verify loading report.json from timestamped run subdirectories."""
        reports_dir = tmp_path / "reports"
        older_run = reports_dir / "20260901T000000Z"
        newer_run = reports_dir / "20260907T000000Z"
        older_run.mkdir(parents=True)
        newer_run.mkdir(parents=True)

        (older_run / "report.json").write_text(
            '{"theme_velocities": [["vintage e retro", 1000.0]]}',
            encoding="utf-8",
        )
        (newer_run / "report.json").write_text(
            '{"theme_velocities": [["k-pop", 4000.0]]}',
            encoding="utf-8",
        )

        keywords = get_adaptive_scrape_keywords(
            report_payload=None,
            reports_dir=reports_dir,
            max_total=4,
        )
        assert len(keywords) == 4
        # Dynamic slot must come from the latest run (k-pop -> camiseta kpop)
        assert keywords[3] == "camiseta kpop"

    def test_filesystem_direct_report_json(self, tmp_path) -> None:
        """Verify loading report.json directly from the reports directory."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir(parents=True)
        (reports_dir / "report.json").write_text(
            '{"theme_velocities": [["memes e humor", 2500.0]]}',
            encoding="utf-8",
        )
        keywords = get_adaptive_scrape_keywords(
            report_payload=None,
            reports_dir=reports_dir,
            max_total=4,
        )
        assert len(keywords) == 4
        assert keywords[3] == "camiseta memes"
