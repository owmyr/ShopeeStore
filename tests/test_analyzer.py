"""Analyzer tests (fake LLM client - no Ollama needed)."""

import json

import pytest

from agents.trend_scout import analyzer
from agents.trend_scout.prompts import NAO_ESTAMPADA
from agents.trend_scout.scraper import ScrapedProduct
from tests.conftest import FakeLLM


def _product(
    item_id: int, title: str, price: int = 5000, sold: int = 100, shop_id: int = 1
) -> ScrapedProduct:
    return ScrapedProduct(
        item_id=item_id,
        shop_id=shop_id,
        title=title,
        url=f"https://x/i.{shop_id}.{item_id}",
        price_cents=price,
        sold_count=sold,
        rating=None,
    )


class TestPercentile:
    def test_median_odd(self) -> None:
        assert analyzer.percentile([10, 20, 30], 0.5) == 20

    def test_interpolates(self) -> None:
        assert analyzer.percentile([10, 20], 0.5) == 15

    def test_empty(self) -> None:
        assert analyzer.percentile([], 0.5) == 0

    def test_p25(self) -> None:
        assert analyzer.percentile([100, 200, 300, 400], 0.25) == 175


class TestDedupe:
    def test_first_occurrence_wins(self) -> None:
        a = _product(1, "camiseta A", sold=50)
        dup = _product(1, "camiseta A", sold=999)
        b = _product(2, "camiseta B")
        out = analyzer.dedupe([a, dup, b])
        assert len(out) == 2
        assert out[0].sold_count == 50


class TestClusterTitles:
    def test_batches_of_25(self) -> None:
        import agents.trend_scout.analyzer

        agents.trend_scout.analyzer.BATCH_SIZE = 25
        titles = [f"camiseta tema {i}" for i in range(26)]
        # batch 1: 25 titles -> indices 1..25; batch 2: 1 title -> index 1
        responses = [
            json.dumps({"clusters": [{"theme": "memes", "indices": [1, 25], "why": "x"}]}),
            json.dumps({"clusters": [{"theme": "pets", "indices": [1], "why": "y"}]}),
        ]
        client = FakeLLM(responses)
        mapping = analyzer.cluster_titles(titles, client=client)

        assert len(client.user_prompts) == 2  # 26 titles -> 2 batches
        assert mapping[0] == "memes"  # batch 1, local index 1
        assert mapping[24] == "memes"  # batch 1, local index 25
        assert mapping[25] == "pets"  # batch 2, local index 1 -> global 25

    def test_invalid_json_leaves_batch_unclustered(self) -> None:
        # chat_json retries once by default -> two garbage responses needed
        client = FakeLLM(["totalmente invalido", "ainda invalido"])
        mapping = analyzer.cluster_titles(["a", "b"], client=client)
        assert mapping == {}

    def test_out_of_range_indices_ignored(self) -> None:
        client = FakeLLM([json.dumps({"clusters": [{"theme": "x", "indices": [99]}]})])
        mapping = analyzer.cluster_titles(["a"], client=client)
        assert mapping == {}


class TestNormalizeThemes:
    def test_merges_synonyms(self) -> None:
        client = FakeLLM(
            [
                json.dumps(
                    {
                        "mapping": [
                            {"original": "academia", "canonical": "academia/fitness"},
                            {"original": "academia/fitness", "canonical": "academia/fitness"},
                            {"original": "basica", "canonical": "basica/lisa"},
                            {"original": "basica/lisa", "canonical": "basica/lisa"},
                        ]
                    }
                )
            ]
        )
        mapping = analyzer.normalize_themes(
            ["basica", "basica/lisa", "academia", "academia/fitness"], client=client
        )
        assert mapping["basica"] == "basica/lisa"
        assert mapping["academia"] == "academia/fitness"
        assert mapping["basica/lisa"] == "basica/lisa"

    def test_identity_for_small_lists(self) -> None:
        mapping = analyzer.normalize_themes(["a", "b"], client=None)
        assert mapping == {"a": "a", "b": "b"}

    def test_fallback_on_garbage(self) -> None:
        client = FakeLLM(["lixo", "lixo denovo"])
        mapping = analyzer.normalize_themes(["a", "b", "c", "d"], client=client)
        assert mapping == {"a": "a", "b": "b", "c": "c", "d": "d"}


class TestPrintExclusion:
    def test_plains_excluded_from_report(self) -> None:
        products = [
            _product(1, "Camiseta Basica Lisa 100% Algodao", sold=1000),
            _product(2, "Camiseta Estampada Anime Manga", sold=100),
            _product(3, "Kit 3 Camisetas Dry Fit Treino", sold=500),
        ]
        client = FakeLLM([json.dumps({"clusters": []})])
        report = analyzer.analyze(products, client=client)

        assert report.printed_count == 1
        assert report.excluded_plain_count == 2
        assert [p.product.item_id for p in report.products] == [2]
        # price bands computed over printed only
        assert report.price_p50_cents == 5000

    def test_nao_estampada_theme_excluded_from_counts(self) -> None:
        products = [
            _product(1, "Camiseta Estampada X", sold=100),
            _product(2, "Camiseta Premium Conforto", sold=50),  # no regex hint
        ]
        # LLM tags product 2 (index 2 after ranking: sold desc -> [1,2]) as nao-estampada
        client = FakeLLM(
            [
                json.dumps(
                    {
                        "clusters": [
                            {"theme": "streetwear", "indices": [1], "why": "x"},
                            {"theme": NAO_ESTAMPADA, "indices": [2], "why": "sem estampa"},
                        ]
                    }
                )
            ]
        )
        report = analyzer.analyze(products, client=client)

        assert report.theme_counts == [("streetwear", 1)]
        by_id = {p.product.item_id: p.theme for p in report.products}
        assert by_id == {1: "streetwear", 2: NAO_ESTAMPADA}


class TestAnalyze:
    def test_full_pipeline(self) -> None:
        products = [
            _product(1, "camiseta meme gato", price=3000, sold=500),
            _product(2, "camiseta evangelica leao", price=4000, sold=300),
            _product(3, "camiseta caveira tribal", price=2000, sold=900),
        ]
        # NOTE: titles reach the LLM in RANKED order [item3, item1, item2],
        # so LLM 1-based indices map: 1->item3, 2->item1, 3->item2
        client = FakeLLM(
            [
                json.dumps(
                    {
                        "clusters": [
                            {"theme": "pets", "indices": [2], "why": "gato"},
                            {"theme": "evangelicas", "indices": [3], "why": "leao"},
                        ]
                    }
                )
            ]
        )
        report = analyzer.analyze(products, client=client)

        # ranked by sold_count desc
        assert [p.product.item_id for p in report.products] == [3, 1, 2]
        # themes land on the right products after ranking
        by_id = {p.product.item_id: p.theme for p in report.products}
        assert by_id == {3: None, 1: "pets", 2: "evangelicas"}
        # price bands over [2000, 3000, 4000]
        assert report.price_p50_cents == 3000
        assert report.theme_counts == [("evangelicas", 1), ("pets", 1)]
        assert "pets" in report.theme_opportunities
        assert "evangelicas" in report.theme_opportunities


class TestComputeThemeOpportunities:
    def test_high_demand_low_comp_by_avg_velocity(self) -> None:
        ap1 = analyzer.AnalyzedProduct(
            product=_product(1, "Anime A", price=3000, shop_id=10),
            theme="anime",
            velocity_metrics=analyzer.VelocityMetrics(velocity_per_day=15.0),
        )
        ap2 = analyzer.AnalyzedProduct(
            product=_product(2, "Anime B", price=4000, shop_id=20),
            theme="anime",
            velocity_metrics=analyzer.VelocityMetrics(velocity_per_day=5.0),
        )
        res = analyzer.compute_theme_opportunities([ap1, ap2])
        assert "anime" in res
        opp = res["anime"]
        assert opp["status_key"] == "high_demand_low_comp"
        assert opp["label"] == "Alta Procura • Pouca Concorrência"
        assert opp["badge_color"] == "emerald"
        assert opp["total_velocity"] == 20.0
        assert opp["avg_velocity"] == 10.0
        assert opp["listings_count"] == 2
        assert opp["shops_count"] == 2

    def test_high_demand_low_comp_by_spread_ratio(self) -> None:
        # total_velocity >= 40.0, shops_count = 9 (> 8)
        # spread_ratio = (4000-2000)/4000 = 0.50 >= 0.20
        products = []
        for i in range(1, 10):
            price = 2000 if i <= 4 else 4000
            products.append(
                analyzer.AnalyzedProduct(
                    product=_product(i, f"Gamer {i}", price=price, shop_id=i * 10),
                    theme="gamer",
                    velocity_metrics=analyzer.VelocityMetrics(velocity_per_day=5.0),
                )
            )
        res = analyzer.compute_theme_opportunities(products)
        opp = res["gamer"]
        assert opp["total_velocity"] == 45.0
        assert opp["shops_count"] == 9
        assert opp["spread_ratio"] >= 0.20
        assert opp["status_key"] == "high_demand_low_comp"
        assert opp["badge_color"] == "emerald"

    def test_high_competition(self) -> None:
        # total_velocity >= 40.0, shops_count = 10 (> 8)
        # all prices same -> spread_ratio = 0.0 < 0.20
        products = []
        for i in range(1, 11):
            products.append(
                analyzer.AnalyzedProduct(
                    product=_product(i, f"Meme {i}", price=3000, shop_id=i * 10),
                    theme="memes",
                    velocity_metrics=analyzer.VelocityMetrics(velocity_per_day=5.0),
                )
            )
        res = analyzer.compute_theme_opportunities(products)
        opp = res["memes"]
        assert opp["total_velocity"] == 50.0
        assert opp["shops_count"] == 10
        assert opp["status_key"] == "high_comp"
        assert opp["label"] == "Nicho Muito Disputado (Briga de Preço)"
        assert opp["badge_color"] == "amber"

    def test_emerging(self) -> None:
        ap1 = analyzer.AnalyzedProduct(
            product=_product(1, "Floral A", price=3000, shop_id=1),
            theme="floral",
            velocity_metrics=analyzer.VelocityMetrics(velocity_per_day=2.0, is_new=True),
        )
        ap2 = analyzer.AnalyzedProduct(
            product=_product(2, "Floral B", price=3000, shop_id=2),
            theme="floral",
            velocity_metrics=analyzer.VelocityMetrics(velocity_per_day=1.0, is_new=False),
        )
        res = analyzer.compute_theme_opportunities([ap1, ap2])
        opp = res["floral"]
        assert opp["status_key"] == "emerging"
        assert opp["label"] == "Estampas Novas Começando a Vender"
        assert opp["badge_color"] == "indigo"

    def test_steady(self) -> None:
        ap = analyzer.AnalyzedProduct(
            product=_product(1, "Vintage A", price=3000, shop_id=1),
            theme="vintage",
            velocity_metrics=analyzer.VelocityMetrics(velocity_per_day=2.0, is_new=False),
        )
        res = analyzer.compute_theme_opportunities([ap])
        opp = res["vintage"]
        assert opp["status_key"] == "steady"
        assert opp["label"] == "Mercado Estável"
        assert opp["badge_color"] == "slate"

    def test_excludes_nao_estampada_and_unthemed(self) -> None:
        ap1 = analyzer.AnalyzedProduct(
            product=_product(1, "Plain X", price=2000),
            theme=NAO_ESTAMPADA,
        )
        ap2 = analyzer.AnalyzedProduct(
            product=_product(2, "No theme", price=2000),
            theme=None,
        )
        res = analyzer.compute_theme_opportunities([ap1, ap2])
        assert res == {}


@pytest.fixture(autouse=True)
def force_ollama_for_tests(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    from core.config import get_settings

    get_settings.cache_clear()
    import agents.trend_scout.analyzer

    agents.trend_scout.analyzer.BATCH_SIZE = 25
