"""Print filter tests - cases drawn from real scraped titles."""

import pytest

from agents.trend_scout.filter import is_plain, theme_slug


class TestIsPlain:
    @pytest.mark.parametrize(
        "title",
        [
            "T- Shirt Blusa Gola Alta 100% Algodao Femenina",
            "Kit 3 Camisetas Basicas Masculina Slim Algodao",
            "Camiseta Feminina Lisa 100% Algodao Premium Conforto Streetwear",
            "Camiseta Masculina Basica Preta 100% Algodao Premium Lisa Oferta",
            "Kit 5 Camisetas DryFitnes Masculina Casual Treino Academia",
            "4 Camisetas Masculinas Kit Malha Fria Dry Fit Treino Academia",
            "Kit 3 Camisetas Poliester DryFit Masculina Lisa Academia Corrida",
            "Kit 2 Blusas T-Shirt Feminina Gola O Basica 100% Algodao Lisa Premium",
            "Camiseta Masculina Canelada Com 3 Academia Casual Conforto",
            "kit com 10 camisetas pretas 100% algodao basica",
        ],
    )
    def test_plain_titles(self, title: str) -> None:
        assert is_plain(title) is True

    @pytest.mark.parametrize(
        "title",
        [
            # print hint wins over plain hint
            "Camiseta Basica Feminina Manga Curta com Estampa Grafica Laco Numero Slogan",
            "Kit 3 Camiseta Feminina Estampada Yoga T-Shirt 100% Algodao Fitness",
            "Kit 10 Blusa Bordada T shirt Feminina 100% Algodao Premium",
            # clear prints
            "Coringa Caveira Ogabel Camisa Camiseta Blusa Ogabel",
            "Camiseta Los Angeles Unissex Streetwear Casual Estampa estilo urbano",
            "Camiseta Stray Kids Giant Kpop Unissex",
            "Camiseta Alien Stage Blusa Anime Manga Unissex",
            "Camiseta Ursinho Pooh Feminina",
            "Camiseta Meme Engracada Frases Divertidas",
            # no hints at all -> keep
            "Camiseta Oversized Streetwear Masculina 100% Algodao Padrao Americano",
            "Daily T-shirt Insider",
            "Camiseta Manfinity UNITED STATES Urban Camisa Street Wear",
            "Camiseta Feminina Algodao 30.1 Premium Moda Gringa Blusinha",
        ],
    )
    def test_printed_or_unknown_titles_are_kept(self, title: str) -> None:
        assert is_plain(title) is False

    def test_sistema_does_not_trigger_tema(self) -> None:
        # word-boundary guard: "sistema" must not match "tema"
        assert is_plain("Camiseta Lisa Sistema Conforto") is True


class TestThemeSlug:
    @pytest.mark.parametrize(
        ("theme", "expected"),
        [
            ("basica/lisa", "basica-lisa"),
            ("academia/fitness", "academia-fitness"),
            ("nostalgia anos 80/90", "nostalgia-anos-80-90"),
            ("evangelicas", "evangelicas"),
            ("Kits Variados", "kits-variados"),
            ("cristã", "crista"),
            ("  ", "sem-tema"),
        ],
    )
    def test_slugs(self, theme: str, expected: str) -> None:
        assert theme_slug(theme) == expected
