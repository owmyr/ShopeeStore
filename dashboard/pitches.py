import urllib.parse

from core.config import get_settings
from core.models import StoreLead


def generate_shopee_chat_pitch(lead: StoreLead, opportunity_label: str | None = None) -> str:
    """Generate an authentic, platform-safe Brazilian Portuguese outreach pitch for Shopee Chat.

    Why: Shopee actively filters external links (WhatsApp, sites) and bans accounts using
    forbidden terms (Pix, off-platform payment, external contact). This pitch establishes initial
    rapport by gifting a complimentary weekly trend sample, contextualizing their primary niche,
    and referencing an attached visual card of top accelerating prints, prompting a simple
    'OK' response to sustain communication safely within platform rules.
    """
    theme = lead.top_theme or "seus produtos"
    if opportunity_label:
        situation = f"vimos que o nicho de {theme} está com {opportunity_label}"
    else:
        situation = f"vimos que o nicho de {theme} está com bastante procura"

    return (
        f"Olá, {lead.shop_name}! Tudo bem? "
        f"Preparamos uma edição cortesia desta semana para lojistas de camisetas: {situation}. "
        "Anexamos acima o card resumo mostrando as 3 estampas que mais aceleraram em "
        "vendas nos últimos dias. Atualizamos esse radar toda segunda-feira. "
        "Se quiser continuar recebendo as próximas edições completas por aqui, "
        "é só me mandar um OK!"
    )


def generate_shopee_followup_pitch(lead: StoreLead) -> str:
    """Generate a follow-up pitch when a merchant responds with interest to the initial sample.

    Why: Once the merchant signals interest (e.g. replies 'OK'), this pitch transitions to the
    commercial value proposition of the comprehensive weekly dossier covering 20+ niches and asks
    for their preferred off-chat channel (WhatsApp/email) to send subscription details.
    """
    return (
        f"Show de bola, {lead.shop_name}! No relatório completo nós monitoramos mais de "
        "20 nichos, com ranking de todas as estampas em alta e links diretos dos anúncios "
        "para você auditar o mercado. Qual é o melhor WhatsApp ou e-mail de vocês para "
        "eu enviar os detalhes de como funciona a assinatura semanal?"
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
