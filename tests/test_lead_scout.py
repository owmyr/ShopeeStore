from datetime import UTC, datetime
from unittest.mock import Mock

import httpx

from agents.lead_scout.agent import run_once
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
    assert "edição cortesia desta semana para lojistas de camisetas" in pitch
    assert "vimos que o nicho de anime está com bastante procura" in pitch
    assert "3 estampas que mais aceleraram em vendas" in pitch
    assert "é só me mandar um OK!" in pitch

    # Safe from Shopee moderation triggers
    assert "whatsapp" not in pitch.lower()
    assert "pix" not in pitch.lower()
    assert "http" not in pitch.lower()

    # Dynamic opportunity label
    custom_label = "Alta Procura • Pouca Concorrência"
    pitch_custom = generate_shopee_chat_pitch(lead, opportunity_label=custom_label)
    assert custom_label in pitch_custom

    # Check that it handles missing top_theme
    lead_none = StoreLead(
        shop_id=3, shop_name="No Theme Store", discovered_at=datetime.now(UTC), run_id="test3"
    )
    pitch_none = generate_shopee_chat_pitch(lead_none)
    assert "No Theme Store" in pitch_none
    assert "seus produtos" in pitch_none


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
    assert "mais de 20 nichos" in followup
    assert "ranking de todas as estampas em alta" in followup
    assert "Qual é o melhor WhatsApp ou e-mail de vocês" in followup


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
