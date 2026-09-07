import urllib.parse

from core.config import get_settings
from core.models import StoreLead


def generate_shopee_chat_pitch(lead: StoreLead, opportunity_label: str | None = None) -> str:
    """Generate an authentic, platform-safe Brazilian Portuguese outreach pitch for Shopee Chat.

    Why: Attaching the comprehensive weekly dossier immediately gives undeniable visual proof
    of intelligence depth. The copy positions this as a courtesy edition of our weekly B2B
    intelligence service, directly offering a monthly subscription to receive the dossier every
    Monday without violating Shopee anti-evasion rules.
    """
    theme = lead.top_theme or "estampas em alta"
    theme_mention = f" (com destaque no nicho de {theme})" if theme != "geral / multitemas" else ""

    return (
        f"Olá, equipe da {lead.shop_name}! Tudo bem?\n\n"
        "Toda semana monitoramos as vendas da categoria de camisetas e estamparia na Shopee BR.\n\n"
        "Anexei aqui a edição desta semana do nosso Dossiê Semanal de Tendências para vocês "
        "conhecerem o levantamento e avaliarem os nichos e estampas que mais estão "
        f"acelerando no mercado{theme_mention}.\n\n"
        "Nosso serviço funciona por assinatura mensal para entregar esse relatório completo e "
        "atualizado toda segunda-feira diretamente para confecções e lojistas parceiros.\n\n"
        "Se fizer sentido para o planejamento de produção da loja de vocês, me dá um toque por "
        "aqui que te passo os detalhes da assinatura mensal. Boas vendas!"
    )


def generate_shopee_followup_pitch(lead: StoreLead) -> str:
    """Generate a follow-up pitch when a merchant responds with interest to the weekly dossier.

    Why: Once the merchant signals interest, this pitch transitions to the commercial value
    proposition of the recurring weekly intelligence subscription delivered on WhatsApp/email.
    """
    return (
        f"Show de bola, {lead.shop_name}! O relatório semanal sai toda segunda-feira às 07h "
        "com o ranking dos 10 maiores nichos, auditoria das 12 estampas que mais aceleraram e "
        "diretrizes de produção. A assinatura mensal se paga no primeiro lote.\n\n"
        "Qual é o melhor WhatsApp ou e-mail de vocês para eu enviar as opções do plano?"
    )


def generate_instagram_pitch(lead: StoreLead) -> str:
    """Generate a direct, friendly Portuguese pitch for Instagram."""
    theme = lead.top_theme or "seus produtos"
    return (
        f"Olá, {lead.shop_name}! Vi que vocês estão vendendo muito bem na categoria {theme}. "
        "Gostaria de receber um link gratuito com nosso dossiê semanal de tendências "
        "para lojistas?"
    )


def generate_email_pitch(lead: StoreLead) -> dict[str, str]:
    """Generate subject, body, and mailto URL for an email pitch."""
    settings = get_settings()
    sender_name = settings.sender_name or "Trend Scout BR"
    sender_instagram = settings.sender_instagram or "trendscoutbr"

    theme = lead.top_theme or "seus produtos"
    subject = f"Tendências para {lead.shop_name}"
    body = (
        f"Olá equipe da {lead.shop_name},\n\n"
        f"Vi que vocês estão vendendo muito bem na categoria {theme}. "
        "Gostaria de receber um link gratuito com nosso dossiê semanal de tendências "
        "para lojistas?\n\n"
        f"Abraços,\n{sender_name}\nInstagram: @{sender_instagram}"
    )

    email = lead.email or ""
    mailto_url = (
        f"mailto:{email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    )

    return {"subject": subject, "body": body, "mailto_url": mailto_url}


def generate_instagram_url(handle: str) -> str:
    """Generate Instagram or IG.me URLs."""
    if handle.startswith("@"):
        handle = handle[1:]
    return f"https://ig.me/m/{handle}"
