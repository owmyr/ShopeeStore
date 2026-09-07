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


class TestSearchUrl:
    def test_quotes_keyword(self) -> None:
        url = scraper.search_url("camiseta estampada")
        assert url == ("https://shopee.com.br/search?keyword=camiseta%20estampada&sortBy=sales")

    def test_single_word(self) -> None:
        assert scraper.search_url("camiseta") == (
            "https://shopee.com.br/search?keyword=camiseta&sortBy=sales"
        )


class TestWallDetection:
    def test_captcha_wall(self) -> None:
        assert scraper._is_captcha_wall("https://shopee.com.br/verify/captcha?x=1")
        assert not scraper._is_captcha_wall("https://shopee.com.br/verify/traffic/error")
        assert not scraper._is_captcha_wall("https://shopee.com.br/search?keyword=x")

    def test_auth_wall_does_not_match_captcha(self) -> None:
        assert not scraper._is_auth_wall("https://shopee.com.br/verify/captcha?x=1")
        assert scraper._is_auth_wall("https://shopee.com.br/verify/traffic/error")


class TestPageUrl:
    def test_appends_param(self) -> None:
        assert scraper.page_url("https://x/search?keyword=camiseta", 2) == (
            "https://x/search?keyword=camiseta&page=2"
        )

    def test_replaces_existing(self) -> None:
        assert scraper.page_url("https://x/search?keyword=camiseta&page=0", 3) == (
            "https://x/search?keyword=camiseta&page=3"
        )

    def test_no_query_string(self) -> None:
        assert scraper.page_url("https://x/Camisetas-cat.1.2", 1) == (
            "https://x/Camisetas-cat.1.2?page=1"
        )


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


class TestNetworkParsing:
    def test_parse_network_items(self) -> None:
        class MockResponse:
            def __init__(self, url, data):
                self.url = url
                self._data = data

            def json(self):
                return self._data

        # valid data
        resp = MockResponse(
            url="https://shopee.com.br/api/v4/search/search_items?keyword=camiseta",
            data={
                "items": [
                    {
                        "item_basic": {
                            "itemid": 123,
                            "shopid": 456,
                            "name": "Camiseta Teste",
                            "price": 2500000,
                            "historical_sold": 100,
                            "item_rating": {"rating_star": 4.5},
                            "image": "img123",
                        }
                    }
                ]
            },
        )

        prods = scraper._parse_network_items(resp)
        assert len(prods) == 1
        assert prods[0].item_id == 123
        assert prods[0].shop_id == 456
        assert prods[0].title == "Camiseta Teste"
        assert prods[0].price_cents == 25
        assert prods[0].sold_count == 100
        assert prods[0].rating == 4.5
        assert prods[0].image_url == "https://down-br.img.susercontent.com/file/img123"
        assert "camiseta-teste" in prods[0].url

    def test_parse_network_items_ignores_other_urls(self) -> None:
        class MockResponse:
            def __init__(self, url, data):
                self.url = url
                self._data = data

            def json(self):
                return self._data

        resp = MockResponse(url="https://shopee.com.br/api/v4/other", data={"items": []})
        prods = scraper._parse_network_items(resp)
        assert len(prods) == 0


class TestExtractProductsMaxItems:
    def test_extract_products_respects_max_items(self) -> None:
        class DummyPage:
            def evaluate(self, js):
                return [
                    {
                        "href": "https://shopee.com.br/Camiseta-A-i.1.101",
                        "text": "Camiseta A\nR$ 25,00",
                        "img": "img1",
                    },
                    {
                        "href": "https://shopee.com.br/Camiseta-B-i.1.102",
                        "text": "Camiseta B\nR$ 30,00",
                        "img": "img2",
                    },
                    {
                        "href": "https://shopee.com.br/Camiseta-C-i.1.103",
                        "text": "Camiseta C\nR$ 35,00",
                        "img": "img3",
                    },
                ]

        seen: dict[int, scraper.ScrapedProduct] = {}
        scraper._extract_products(DummyPage(), seen, max_items=2)
        assert len(seen) == 2
        assert set(seen.keys()) == {101, 102}


class TestPerKeywordCap:
    def test_scrape_respects_max_per_keyword(self, tmp_path, monkeypatch) -> None:
        auth_file = tmp_path / "shopee_auth.json"
        auth_file.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("SHOPEE_AUTH_PATH", str(auth_file))
        monkeypatch.setenv("SCRAPE_MAX_PER_KEYWORD", "2")
        monkeypatch.setenv("SCRAPE_MAX_PRODUCTS", "10")
        monkeypatch.setattr(scraper.time, "sleep", lambda _: None)

        get_settings.cache_clear()
        settings = get_settings()
        monkeypatch.setattr(settings, "scrape_keywords", ["niche-alpha", "niche-beta"])

        class MockResponse:
            def __init__(self, url: str, data: dict):
                self.url = url
                self._data = data

            def json(self):
                return self._data

        class MockMouse:
            def wheel(self, dx, dy):
                pass

        class MockPage:
            def __init__(self):
                self.url = "https://shopee.com.br/"
                self._handlers = {}
                self.mouse = MockMouse()

            def on(self, event, handler):
                self._handlers[event] = handler

            def goto(self, url, **kwargs):
                self.url = url
                if "search" in url and "response" in self._handlers:
                    kw = "alpha" if "niche-alpha" in url else "beta"
                    items = [
                        {
                            "item_basic": {
                                "itemid": (100 if kw == "alpha" else 200) + i,
                                "shopid": 1,
                                "name": f"Camiseta {kw} {i}",
                                "price": 2500000,
                                "historical_sold": 50,
                            }
                        }
                        for i in range(1, 6)
                    ]
                    resp = MockResponse(
                        url=f"https://shopee.com.br/api/v4/search/search_items?keyword={kw}",
                        data={"items": items},
                    )
                    self._handlers["response"](resp)

            def wait_for_timeout(self, ms):
                pass

            def evaluate(self, js):
                return []

        class MockContext:
            def __init__(self, page):
                self._page = page

            def new_page(self):
                return self._page

        class MockBrowser:
            def close(self):
                pass

        class MockPWContext:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_page = MockPage()
        monkeypatch.setattr(scraper, "sync_playwright", lambda: MockPWContext())
        monkeypatch.setattr(
            scraper, "_new_context", lambda pw, **kwargs: (MockBrowser(), MockContext(mock_page))
        )

        try:
            products = scraper.scrape_best_sellers()
            assert len(products) == 4
            alpha_ids = [p.item_id for p in products if "alpha" in p.title]
            beta_ids = [p.item_id for p in products if "beta" in p.title]
            # Each keyword yielded exactly 2 items despite 5 being available
            assert alpha_ids == [101, 102]
            assert beta_ids == [201, 202]
        finally:
            get_settings.cache_clear()

    def test_dry_run_caps_at_five(self, tmp_path, monkeypatch) -> None:
        auth_file = tmp_path / "shopee_auth.json"
        auth_file.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("SHOPEE_AUTH_PATH", str(auth_file))
        monkeypatch.setattr(scraper.time, "sleep", lambda _: None)

        get_settings.cache_clear()

        class MockPage:
            def __init__(self):
                self.url = "https://shopee.com.br/"
                self.mouse = type("M", (), {"wheel": lambda self, dx, dy: None})()

            def on(self, event, handler):
                self._handler = handler

            def goto(self, url, **kwargs):
                self.url = url
                if "search" in url:
                    items = [
                        {
                            "item_basic": {
                                "itemid": 300 + i,
                                "shopid": 1,
                                "name": f"Camiseta Teste {i}",
                                "price": 2500000,
                                "historical_sold": 50,
                            }
                        }
                        for i in range(1, 10)
                    ]
                    resp = type(
                        "R",
                        (),
                        {
                            "url": "https://shopee.com.br/api/v4/search/search_items",
                            "json": lambda self: {"items": items},
                        },
                    )()
                    self._handler(resp)

            def wait_for_timeout(self, ms):
                pass

            def evaluate(self, js):
                return []

        class MockPWContext:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_page = MockPage()
        monkeypatch.setattr(scraper, "sync_playwright", lambda: MockPWContext())
        monkeypatch.setattr(
            scraper,
            "_new_context",
            lambda pw, **kwargs: (
                type("B", (), {"close": lambda self: None})(),
                type("C", (), {"new_page": lambda self: mock_page})(),
            ),
        )

        try:
            products = scraper.scrape_best_sellers(dry_run=True)
            assert len(products) == 5
        finally:
            get_settings.cache_clear()
