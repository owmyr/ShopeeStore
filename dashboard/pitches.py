import urllib.parse

from core.config import get_settings
from core.models import StoreLead


def generate_shopee_chat_pitch(lead: StoreLead) -> str:
    """
    Generate a concise, respectful, platform-compliant Portuguese chat copy for Shopee.

    Why: Shopee actively filters external links (like Whatsapp or email) and aggressively
    bans accounts using forbidden trigger words (like "Pix", "WhatsApp", "fora do app", etc.).
    This pitch compliments their best-selling theme, notes recent market sales spikes,
    and offers a free executive dossier PDF without using forbidden words.
    """
    theme = lead.top_theme or "seus produtos"
    return (
        f"Olá, {lead.shop_name}! Tudo bem? Parabéns pelo sucesso com {theme}. "
        "Acompanhamos o pico de vendas do mercado recentemente. "
        "Gostaria de receber um resumo visual semanal com as tendências em alta, "
        "de forma 100% gratuita? Podemos enviar a imagem com os dados por aqui mesmo!"
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
