import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import httpx

from agents.lead_scout.agent import (
    build_report_theme_mappings,
    classify_theme_by_title,
    load_latest_report,
    migrate_lead_themes,
    resolve_lead_theme,
    run_once,
)
from agents.lead_scout.discovery import (
    _enrich_cnpj,
    extract_cnpj,
    extract_email,
    extract_instagram,
    is_valid_cnpj,
)
from agents.lead_scout.pitch import (
    generate_email_pitch,
    generate_instagram_pitch,
    generate_instagram_url,
    generate_shopee_chat_pitch,
    generate_shopee_followup_pitch,
)
from core.db import session_scope
from core.models import Product, StoreLead


def test_is_valid_cnpj():
    assert is_valid_cnpj("00.000.000/0001-91")
    assert is_valid_cnpj("00000000000191")
    assert not is_valid_cnpj("11111111111111")
    assert not is_valid_cnpj("00.000.000/0001-92")
    assert not is_valid_cnpj("123")


def test_extract_cnpj():
    assert extract_cnpj("CNPJ: 00.000.000/0001-91") == "00000000000191"
    assert extract_cnpj("Some text 00.000.000/0001-91 here") == "00000000000191"
    assert extract_cnpj("Invalid 00.000.000/0001-92") is None


def test_extract_instagram():
    assert extract_instagram("Follow us @mystore") == "mystore"
    assert extract_instagram("Instagram: instagram.com/mystore") == "mystore"
    assert extract_instagram("Email me at test@gmail.com") is None
    assert extract_instagram("Email me at user@shopee.com") is None


def test_extract_email():
    assert extract_email("Contact test@example.com") == "test@example.com"
    assert extract_email("Contact test@shopee.com") is None
    assert extract_email("Contact example@shopee.com") is None


def test_enrich_cnpj():
    client = Mock(spec=httpx.Client)
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "razao_social": "BANCO DO BRASIL SA",
        "nome_fantasia": "BANCO DO BRASIL",
        "email": "contato@bb.com.br",
        "municipio": "BRASILIA",
        "uf": "DF",
    }
    client.get.return_value = response

    result = _enrich_cnpj("00000000000191", client=client)
    assert result is not None
    assert result["razao_social"] == "BANCO DO BRASIL SA"
    assert result["email"] == "contato@bb.com.br"
    assert result["city"] == "BRASILIA"

    response.status_code = 404
    client.get.return_value = response
    assert _enrich_cnpj("00000000000192", client=client) is None


def test_pitch_generators():
    lead = StoreLead(
        shop_id=1,
        shop_name="My Store",
        top_theme="geek",
        email="test@store.com",
        discovered_at=datetime.now(UTC),
        run_id="test",
    )

    ig_pitch = generate_instagram_pitch(lead)
    assert "My Store" in ig_pitch
    assert "geek" in ig_pitch

    email_pitch = generate_email_pitch(lead)
    assert email_pitch["subject"] == "Tendências para My Store"
    assert "mailto:test@store.com" in email_pitch["mailto_url"]
    assert "My%20Store" in email_pitch["mailto_url"]

    assert generate_instagram_url("@mystore") == "https://ig.me/m/mystore"
    assert generate_instagram_url("mystore") == "https://ig.me/m/mystore"


def test_shopee_chat_pitch():
    lead = StoreLead(
        shop_id=2,
        shop_name="Geek Tees",
        top_theme="anime",
        discovered_at=datetime.now(UTC),
        run_id="test2",
    )
    pitch = generate_shopee_chat_pitch(lead)
    assert "Geek Tees" in pitch
    assert "anime" in pitch
    assert "Dossiê Semanal de Tendências" in pitch
    assert "assinatura mensal" in pitch
    assert "boas vendas" in pitch.lower()

    # Safe from Shopee moderation triggers
    assert "whatsapp" not in pitch.lower()
    assert "pix" not in pitch.lower()
    assert "http" not in pitch.lower()

    # Dynamic opportunity label or fallback
    custom_label = "Alta Procura • Pouca Concorrência"
    pitch_custom = generate_shopee_chat_pitch(lead, opportunity_label=custom_label)
    assert "Geek Tees" in pitch_custom

    # Check that it handles missing top_theme
    lead_none = StoreLead(
        shop_id=3, shop_name="No Theme Store", discovered_at=datetime.now(UTC), run_id="test3"
    )
    pitch_none = generate_shopee_chat_pitch(lead_none)
    assert "No Theme Store" in pitch_none
    assert "Dossiê Semanal" in pitch_none


def test_shopee_followup_pitch():
    lead = StoreLead(
        shop_id=2,
        shop_name="Geek Tees",
        top_theme="anime",
        discovered_at=datetime.now(UTC),
        run_id="test2",
    )
    followup = generate_shopee_followup_pitch(lead)
    assert "Geek Tees" in followup
    assert "assinatura mensal" in followup
    assert "ranking dos 10 maiores nichos" in followup
    assert "Qual o melhor e-mail ou canal de contato de vocês" in followup

    # Strictly no prohibited platform evasion triggers in followup
    assert "whatsapp" not in followup.lower()
    assert "pix" not in followup.lower()
    assert "http" not in followup.lower()


def test_run_once(isolated) -> None:
    from sqlmodel import select

    with session_scope() as s:
        p = Product(
            item_id=101,
            shop_id=1,
            title="Camiseta @loja_top CNPJ 00.000.000/0001-91",
            url="http://shopee/101",
            shop_name="Loja Top",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
        s.add(p)
        s.commit()

    client = Mock(spec=httpx.Client)
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "razao_social": "LOJA TOP LTDA",
        "email": "loja@top.com",
    }
    client.get.return_value = response

    count = run_once(enrich_cnpj=True, client=client)
    assert count == 1

    with session_scope() as s:
        lead = s.exec(select(StoreLead).where(StoreLead.shop_id == 1)).first()
        assert lead is not None
        assert lead.instagram == "loja_top"
        assert lead.cnpj == "00000000000191"
        assert lead.razao_social == "LOJA TOP LTDA"
        assert lead.email == "loja@top.com"
        assert lead.status == "discovered"
        assert lead.notes == ""

        # Modify and re-run
        lead.status = "contacted"
        lead.notes = "Do not spam"
        s.add(lead)
        s.commit()

    count = run_once(enrich_cnpj=False)
    assert count == 1

    with session_scope() as s:
        lead = s.exec(select(StoreLead).where(StoreLead.shop_id == 1)).first()
        assert lead is not None
        assert lead.status == "contacted"
        assert lead.notes == "Do not spam"


def test_classify_theme_by_title_all_categories() -> None:
    cases = [
        ("Camiseta Fé em Jesus Cristo Gospel Salmo Cruz Bíblia", "religioso e cristao"),
        ("Camiseta Evangélica com Louvor e Oração de Pastor", "religioso e cristao"),
        ("Camiseta Anime Naruto Shippuden Goku Dragon Ball Luffy", "anime e geek"),
        ("Camiseta Otaku Cosplay Kimetsu Demon Slayer Bleach", "anime e geek"),
        ("Camiseta Homem Aranha Vingadores Marvel Herois Batman", "geek e super-herois"),
        ("Camiseta Gamer PlayStation Xbox Nintendo Harry Potter", "geek e super-herois"),
        ("Camiseta Rock Metallica Heavy Metal Banda Guitarra", "rock e musica"),
        ("Camiseta Iron Maiden Punk Rock AC/DC Beatles Nirvana", "rock e musica"),
        ("Camiseta K-pop BTS Army Coreana", "k-pop"),
        ("Camiseta Blackpink Stray Kids Kpop", "k-pop"),
        ("Camiseta Agro Country Cavalo Boiadeiro Sertanejo Peão Rodeio", "country e sertanejo"),
        ("Camiseta Haras Vaquejada Bruta Bota", "country e sertanejo"),
        ("Camiseta Streetwear Oversized Skate Trap Quebrada Favela", "streetwear"),
        ("Camiseta Tio Patinhas Irmãos Metralha Drip Grau Chronic", "streetwear"),
        ("Camiseta Moto Motocross Harley Carros Automotivo Turbo F1", "automotivo"),
        ("Camiseta Oficina Custom Bike Motor Drift", "automotivo"),
        ("Camiseta Gato Gatinho Cachorro Pet Patinhas Capivara", "pets e animais"),
        ("Camiseta Panda Leão Tigre Lobo Coelho Animais Pássaro", "pets e animais"),
        ("Camiseta Garfield Snoopy Stitch Mickey Minnie Bob Esponja", "desenhos e animacoes"),
        ("Camiseta Rei Leão Simpsons Looney Tunes Tom e Jerry", "desenhos e animacoes"),
        ("Camiseta Girassol Margarida Flores Cereja Floral Rosas", "frutas e flores"),
        ("Camiseta Corações Morango Cactos Plantas Botanical", "frutas e flores"),
        ("Camiseta Futebol Academia Treino Maromba Fitness Musculação", "esportes"),
        ("Camiseta Neymar Jiu Jitsu Corrida Basquete", "esportes"),
        ("Camiseta Tal Pai Tal Filho Papai Mamãe Casal Família", "familia"),
        ("Camiseta Dia dos Pais Vovô Dindo Namorados", "familia"),
        ("Camiseta Infantil Criança Bebê Kids Mesversário Body", "infantil"),
        ("Camiseta Patriota Política Eleições Lula Bolsonaro", "politica"),
        ("Camiseta Professor Enfermeira Médico Advogado Veterinário", "profissoes"),
        ("Camiseta Meme Frases Engraçadas Piada Deboche", "frases engracadas"),
        ("Camiseta Masculina Algodão Penteado Básica Confortável", "geral / multitemas"),
        ("", "geral / multitemas"),
        ("   ", "geral / multitemas"),
    ]
    for title, expected in cases:
        result = classify_theme_by_title(title)
        assert result == expected, f"Failed for '{title}': expected '{expected}', got '{result}'"
        assert result != "camisetas estampadas", "Never return 'camisetas estampadas'"


def test_manga_vs_sleeve_disambiguation() -> None:
    sleeves = [
        "Camiseta Manga Curta 100% Algodão Premium",
        "Camiseta Manga Longa Térmica Lisa",
        "Camiseta Manga Raglan Dry Fit",
        "Regata Sem Manga Masculina Casual",
        "Blusa Com Manga Bufante Princesa",
        "Camiseta com manga dobrada casual",
    ]
    for title in sleeves:
        assert classify_theme_by_title(title) != "anime e geek"
        assert classify_theme_by_title(title) == "geral / multitemas"

    anime_manga = [
        "Camiseta Manga Japonesa Geek",
        "Camiseta Estampa Manga Death Note",
        "Camiseta Manga Curta Anime Naruto",
        "Camiseta Manga Longa Estampa Manga Otaku",
    ]
    for title in anime_manga:
        assert classify_theme_by_title(title) == "anime e geek"


def test_load_latest_report_and_mappings(tmp_path: Path) -> None:
    missing_dir = tmp_path / "non_existent"
    lat, data = load_latest_report(reports_dir=missing_dir)
    assert lat is None
    assert data is None

    rep_dir = tmp_path / "reports"
    rep_dir.mkdir()
    lat, data = load_latest_report(reports_dir=rep_dir)
    assert lat is None
    assert data is None

    r1 = rep_dir / "20260701T000000Z"
    r1.mkdir()
    (r1 / "report.json").write_text(json.dumps({"products": []}))

    r2 = rep_dir / "20260702T000000Z"
    r2.mkdir()
    report_content = {
        "products": [
            {"shop_id": 10, "item_id": 1001, "theme": "streetwear"},
            {"shop_id": 10, "item_id": 1002, "theme": "streetwear"},
            {"shop_id": 10, "item_id": 1003, "theme": "esportes"},
            {"shop_id": 20, "item_id": 2001, "theme": "nao-estampada"},
            {"shop_id": 30, "item_id": 3001, "theme": ""},
        ],
        "breakout_products": [
            {"shop_id": 10, "item_id": 1004, "theme": "streetwear"},
            {"shop_id": 40, "item_id": 4001, "theme": "anime e geek"},
        ],
    }
    (r2 / "report.json").write_text(json.dumps(report_content))

    lat, data = load_latest_report(reports_dir=rep_dir)
    assert lat == r2
    assert data is not None

    shop_map, item_map = build_report_theme_mappings(data)
    assert shop_map[10] == ["streetwear", "streetwear", "esportes", "streetwear"]
    assert 20 not in shop_map
    assert 30 not in shop_map
    assert shop_map[40] == ["anime e geek"]

    assert item_map[1001] == "streetwear"
    assert item_map[4001] == "anime e geek"
    assert 2001 not in item_map
    assert 3001 not in item_map

    empty_shop_map, empty_item_map = build_report_theme_mappings(None)
    assert empty_shop_map == {}
    assert empty_item_map == {}


def test_resolve_lead_theme() -> None:
    shop_map = {10: ["streetwear", "streetwear", "rock e musica"]}
    item_map = {2001: "k-pop"}

    prod_mock = Product(
        item_id=2001,
        shop_id=20,
        title="Camiseta Neutra Algodão",
        url="",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )

    # 1. Shop ID majority theme
    res = resolve_lead_theme(10, prod_mock, shop_map, item_map)
    assert res == "streetwear"

    # 2. Item ID theme
    res = resolve_lead_theme(20, prod_mock, shop_map, item_map)
    assert res == "k-pop"

    # 3. Title fallback
    prod_title = Product(
        item_id=9999,
        shop_id=99,
        title="Camiseta Fé Jesus Cristo Gospel",
        url="",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    res = resolve_lead_theme(99, prod_title, shop_map, item_map)
    assert res == "religioso e cristao"

    # 4. Fallback when title has no match
    prod_plain = Product(
        item_id=8888,
        shop_id=88,
        title="Camiseta Algodão Básica",
        url="",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    res = resolve_lead_theme(88, prod_plain, shop_map, item_map)
    assert res == "geral / multitemas"
    assert res != "camisetas estampadas"

    # 5. Fallback when product is None
    res = resolve_lead_theme(77, None, shop_map, item_map)
    assert res == "geral / multitemas"


def test_migrate_lead_themes(isolated, tmp_path: Path) -> None:
    from sqlmodel import select

    rep_dir = tmp_path / "reports"
    rep_dir.mkdir()
    r = rep_dir / "20260801T000000Z"
    r.mkdir()
    report_data = {
        "products": [
            {"shop_id": 501, "item_id": 5001, "theme": "streetwear"},
        ]
    }
    (r / "report.json").write_text(json.dumps(report_data))

    now = datetime.now(UTC)
    with session_scope() as s:
        # Lead 1: in report
        s.add(
            StoreLead(
                shop_id=501,
                shop_name="Store 501",
                top_theme="camisetas estampadas",
                discovered_at=now,
                run_id="t",
            )
        )
        # Lead 2: has product with title
        s.add(
            StoreLead(
                shop_id=502,
                shop_name="Store 502",
                top_theme="camisetas estampadas",
                discovered_at=now,
                run_id="t",
            )
        )
        s.add(
            Product(
                item_id=5002,
                shop_id=502,
                title="Camiseta Moto Harley Davidson Motocross",
                url="",
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        # Lead 3: only lead.top_product_title exists
        s.add(
            StoreLead(
                shop_id=503,
                shop_name="Store 503",
                top_theme="camisetas estampadas",
                top_product_title="Camiseta Fé em Deus Bíblia",
                discovered_at=now,
                run_id="t",
            )
        )
        s.commit()

    migrated = migrate_lead_themes(reports_dir=rep_dir)
    assert migrated == 3

    with session_scope() as s:
        l1 = s.exec(select(StoreLead).where(StoreLead.shop_id == 501)).first()
        l2 = s.exec(select(StoreLead).where(StoreLead.shop_id == 502)).first()
        l3 = s.exec(select(StoreLead).where(StoreLead.shop_id == 503)).first()

        assert l1.top_theme == "streetwear"
        assert l2.top_theme == "automotivo"
        assert l3.top_theme == "religioso e cristao"
        for lead in [l1, l2, l3]:
            assert lead.top_theme != "camisetas estampadas"


def test_run_once_theme_assignment(isolated) -> None:
    from sqlmodel import select

    now = datetime.now(UTC)
    with session_scope() as s:
        p1 = Product(
            item_id=301,
            shop_id=31,
            title="Camiseta Oversized Streetwear Skate Trap",
            url="http://shopee/301",
            shop_name="Street Store",
            first_seen_at=now,
            last_seen_at=now,
        )
        s.add(p1)
        # Existing lead with outdated placeholder theme
        s.add(
            StoreLead(
                shop_id=31,
                shop_name="Street Store",
                top_theme="camisetas estampadas",
                top_product_title=p1.title,
                discovered_at=now,
                run_id="old_run",
            )
        )
        s.commit()

    client = Mock(spec=httpx.Client)
    client.get.return_value = Mock(status_code=404)

    run_once(enrich_cnpj=False, client=client)

    with session_scope() as s:
        lead = s.exec(select(StoreLead).where(StoreLead.shop_id == 31)).first()
        assert lead is not None
        assert lead.top_theme == "streetwear"
        assert lead.top_theme != "camisetas estampadas"

