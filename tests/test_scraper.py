"""Scraper parsing tests (pure functions - no browser)."""

import pytest

from agents.trend_scout import scraper
from core.config import get_settings


class TestAuthRequired:
    def test_scrape_raises_without_auth_state(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("SHOPEE_AUTH_PATH", str(tmp_path / "missing.json"))
        get_settings.cache_clear()
        try:
            with pytest.raises(scraper.ShopeeAuthError, match="--login"):
                scraper.scrape_best_sellers(dry_run=True)
        finally:
            get_settings.cache_clear()


class TestParsePriceCents:
    def test_simple(self) -> None:
        assert scraper.parse_price_cents("R$ 29,99") == 2999

    def test_thousands_separator(self) -> None:
        assert scraper.parse_price_cents("R$ 1.234,56") == 123456

    def test_embedded_in_text(self) -> None:
        assert scraper.parse_price_cents("por apenas R$ 45,90 cada") == 4590

    def test_no_match(self) -> None:
        assert scraper.parse_price_cents("sem preco aqui") is None


class TestParseSoldCount:
    def test_plain(self) -> None:
        assert scraper.parse_sold_count("50 vendidos") == 50

    def test_mil_multiplier(self) -> None:
        assert scraper.parse_sold_count("1,2 mil vendidos") == 1200

    def test_mil_no_space(self) -> None:
        assert scraper.parse_sold_count("10mil vendidos") == 10000

    def test_mil_plus(self) -> None:
        assert scraper.parse_sold_count("10 mil+ vendidos") == 10000

    def test_singular(self) -> None:
        assert scraper.parse_sold_count("1 vendido") == 1

    def test_no_match(self) -> None:
        assert scraper.parse_sold_count("novo") is None


class TestParseRating:
    def test_comma(self) -> None:
        assert scraper.parse_rating("4,8") == 4.8

    def test_dot(self) -> None:
        assert scraper.parse_rating("4.9") == 4.9

    def test_rejects_non_rating(self) -> None:
        assert scraper.parse_rating("29,99") is None
        assert scraper.parse_rating("vendidos") is None
        assert scraper.parse_rating("6,5") is None


class TestParseItemHref:
    def test_standard(self) -> None:
        url = "https://shopee.com.br/Camiseta-Oversized-i.123456789.987654321?xpt=1"
        assert scraper.parse_item_href(url) == (123456789, 987654321)

    def test_no_match(self) -> None:
        assert scraper.parse_item_href("https://shopee.com.br/search?keyword=camiseta") is None


class TestParseCardText:
    def test_full_card(self) -> None:
        text = (
            "Camiseta Oversized Streetwear Masculina Algodao\n"
            "R$ 39,99\n"
            "4,8\n"
            "1,2 mil vendidos\n"
            "Sao Paulo"
        )
        title, price, sold, rating = scraper.parse_card_text(text)
        assert title == "Camiseta Oversized Streetwear Masculina Algodao"
        assert price == 3999
        assert sold == 1200
        assert rating == 4.8

    def test_card_without_rating_or_sold(self) -> None:
        text = "Camiseta Basica Lisa\nR$ 25,00"
        title, price, sold, rating = scraper.parse_card_text(text)
        assert title == "Camiseta Basica Lisa"
        assert price == 2500
        assert sold is None
        assert rating is None

    def test_real_shopee_layout_split_price_and_discount(self) -> None:
        """Layout observed live 2026-07: discount badge, title, 'R$' alone,
        price on the next line, sold count last."""
        text = (
            "-33%\n"
            "Camiseta Streetwear Tshirt 100% Algodao Ctrz Dead Preezy\n"
            "R$\n"
            "33,44\n"
            "160 vendidos"
        )
        title, price, sold, rating = scraper.parse_card_text(text)
        assert title == "Camiseta Streetwear Tshirt 100% Algodao Ctrz Dead Preezy"
        assert price == 3344
        assert sold == 160
        assert rating is None

    def test_discount_badge_never_becomes_title(self) -> None:
        text = "-48%\nCamiseta Basica\nR$\n25,00"
        title, _, _, _ = scraper.parse_card_text(text)
        assert title == "Camiseta Basica"
