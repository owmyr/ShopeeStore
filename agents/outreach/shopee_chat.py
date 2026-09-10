"""
Shopee Chat Outreach Module.

This module is responsible for automating the delivery of the weekly trend dossier
directly to potential leads via Shopee's built-in chat system. It utilizes Playwright
to simulate human interaction, bypass basic bot detection overlays, and dispatch
varied text pitches alongside image attachments, ensuring our outreach remains
effective and avoids spam filters.
"""

import argparse
import logging
import random
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from sqlmodel import select

import core.ledger
import dashboard.pitches  # noqa: F401 - pitch templates reference
import dashboard.supervision  # noqa: F401 - supervision reference
from core.config import get_settings
from core.db import session_scope
from core.models import StoreLead
from dashboard.supervision import get_weekly_dossier_png_path

logger = logging.getLogger(__name__)


def generate_varied_shopee_pitch(lead: StoreLead, opportunity_label: str | None = None) -> str:
    """
    Generates a linguistically jittered pitch for a given lead.

    This function assembles a pitch from a set of predefined greetings, transitions,
    and closings to prevent spam pattern detection by the platform. It ensures no
    forbidden words (like external links or payment terms) are included to avoid
    account bans.
    """
    greetings = [
        f"Olá, equipe da {lead.shop_name}! Tudo bem?",
        f"Oi pessoal da {lead.shop_name}! Tudo bem por aí?",
        f"Olá, time da {lead.shop_name}! Tudo bem com vocês?",
    ]

    transitions = [
        "Toda semana monitoramos as vendas da categoria de "
        "camisetas e estamparia na Shopee BR.",
        "Semanalmente fazemos o acompanhamento do volume de vendas em "
        "camisetas e estamparia na Shopee BR.",
        "Monitoramos semanalmente o ritmo de vendas e tendências em "
        "estamparia e camisetas na Shopee BR.",
    ]

    theme = lead.top_theme or "estampas em alta"
    theme_mention = f" (com destaque no nicho de {theme})" if theme != "geral / multitemas" else ""

    body = (
        "Anexei aqui a edição desta semana do nosso Dossiê Semanal de Tendências "
        "para vocês conhecerem "
        "o levantamento e avaliarem os nichos e estampas que mais estão "
        f"acelerando no mercado{theme_mention}.\n\n"
        "Nosso serviço funciona por assinatura mensal para entregar esse relatório "
        "completo e atualizado "
        "toda segunda-feira diretamente para confecções e lojistas parceiros."
    )

    closings = [
        "Se fizer sentido para o planejamento de produção da loja de vocês, me dá um toque "
        "por aqui que te passo os detalhes da assinatura mensal. Boas vendas!",
        "Se ajudar no planejamento de coleção e corte de vocês, me chama aqui "
        "para vermos a assinatura semanal. Sucesso nas vendas!",
        "Se fizer sentido acompanhar essas tendências toda segunda-feira, é só responder "
        "aqui que te passo as condições do clube mensal. Boas vendas na produção!",
    ]

    greeting = random.choice(greetings)
    transition = random.choice(transitions)
    closing = random.choice(closings)

    pitch = f"{greeting}\n\n{transition}\n\n{body}\n\n{closing}"

    forbidden_pattern = re.compile(r"whatsapp|pix|http://|https://|www\.", re.IGNORECASE)
    if forbidden_pattern.search(pitch):
        raise ValueError("Forbidden words found in the generated pitch.")

    return pitch


def _new_browser_context(pw: Any, *, headless: bool) -> tuple[Browser, BrowserContext]:
    """Launch browser context configuring authenticated session and anti-fingerprinting.

    Why: Shopee requires active logged-in cookies stored in `shopee_auth.json` to allow
    accessing merchant chat. Replicating the Chrome browser parameters and São Paulo locale
    ensures session cookies are accepted without triggering security verification challenges.
    """
    settings = get_settings()
    auth_path = settings.shopee_auth_path

    if not auth_path.exists():
        raise FileNotFoundError(
            f"Shopee auth session file not found at '{auth_path}'. "
            "Run 'python -m agents.trend_scout.scraper --login' first."
        )

    browser = pw.chromium.launch(
        channel="chrome", headless=headless, args=["--disable-blink-features=AutomationControlled"]
    )

    context = browser.new_context(
        viewport={"width": 1366, "height": 768},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
        ),
        storage_state=str(auth_path),
    )

    return browser, context


def _dismiss_overlays(page: Page) -> None:
    """Best-effort dismissal of common intrusive overlays like cookie banners or language selectors.

    Why: Shopee storefronts frequently show regional or promotional overlays that sit on top
    of the DOM hierarchy and intercept clicks destined for the merchant chat launcher.
    """
    for text in (
        "Português (BR)",
        "Aceitar todos os cookies",
        "Aceitar",
        "Entendi",
        "Fechar",
    ):
        try:
            target = page.get_by_text(text, exact=False).first
            if target.is_visible(timeout=1000):
                target.click(timeout=1000)
                page.wait_for_timeout(300)
        except Exception:
            pass

    for selector in (
        "div.shopee-popup__close-btn",
        "button.cookie-banner__accept",
        "[aria-label='close']",
        "[aria-label='Fechar']",
        ".close-btn",
    ):
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=800):
                btn.click(timeout=800)
                page.wait_for_timeout(300)
        except Exception:
            pass


def _check_captcha_or_wall(
    page: Page, timeout_sec: int = 180, headful: bool = False
) -> bool:
    """Check for the presence of a login wall or captcha challenge.

    Why: Rate-based anomalies or new device fingerprints trigger Shopee security gates.
    In headful mode, giving a human operator time to solve puzzles preserves the session,
    while in headless mode, capturing screenshots enables diagnosis without indefinite hangs.
    """
    settings = get_settings()
    error_dir = settings.data_dir / "error_screenshots"
    error_dir.mkdir(parents=True, exist_ok=True)

    def is_wall() -> bool:
        url = page.url
        if "/verify/" in url or "/buyer/login" in url:
            return True
        for sel in (
            "iframe[src*='verify']",
            "div.captcha-container",
            "text='Arraste para completar'",
        ):
            try:
                if page.locator(sel).first.is_visible(timeout=500):
                    return True
            except Exception:
                pass
        return False

    if not is_wall():
        return True

    timestamp = int(time.time())
    if not headful:
        screenshot_path = error_dir / f"captcha_{timestamp}.png"
        try:
            page.screenshot(path=str(screenshot_path))
            logger.error(
                "Captcha/wall detected in headless mode. Saved: %s", screenshot_path
            )
        except Exception as e:
            logger.error("Failed to capture captcha screenshot: %s", e)
        return False

    print("\n[ALERTA] Desafio de segurança/captcha detectado em:", page.url)
    print(
        f"Resolva o desafio na janela do navegador. Aguardando até {timeout_sec}s...\n",
        flush=True,
    )

    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        page.wait_for_timeout(2000)
        if not is_wall():
            print("[OK] Desafio resolvido com sucesso!", flush=True)
            page.wait_for_timeout(1500)
            return True

    screenshot_path = error_dir / f"captcha_timeout_{timestamp}.png"
    try:
        page.screenshot(path=str(screenshot_path))
    except Exception:
        pass
    print(
        f"[TIMEOUT] Desafio de segurança não resolvido em {timeout_sec}s.", flush=True
    )
    return False


def send_lead_message(
    page: Page,
    lead: StoreLead,
    dossier_png_path: Path,
    *,
    dry_run: bool = False,
    headful: bool = False,
) -> bool:
    """Deliver weekly infographic dossier and customized pitch to a seller via Shopee Chat.

    Why: Direct vendor chat provides the highest open rate among e-commerce sellers.
    Attaching visual proof of market intelligence establishes credibility before offering
    the recurring subscription service.
    """
    settings = get_settings()
    error_dir = settings.data_dir / "error_screenshots"
    error_dir.mkdir(parents=True, exist_ok=True)

    shop_url = (
        lead.shop_url if lead.shop_url else f"https://shopee.com.br/shop/{lead.shop_id}"
    )

    try:
        logger.info(
            "Opening seller storefront for shop %s: %s", lead.shop_name, shop_url
        )
        page.goto(shop_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)

        _dismiss_overlays(page)

        if not _check_captcha_or_wall(page, headful=headful):
            logger.warning(
                "Security wall active or unresolved for shop %s", lead.shop_id
            )
            return False

        # Primary: role button matching conversar agora or chat agora
        chat_btn = page.get_by_role(
            "button", name=re.compile(r"conversar\s*agora|chat\s*agora", re.I)
        )
        if not chat_btn.is_visible(timeout=3000):
            # Fallback text locator
            chat_btn = page.locator(
                "button:has-text('Conversar Agora'), button:has-text('Chat Agora')"
            ).first

        if not chat_btn.is_visible(timeout=3000):
            page.evaluate("window.scrollBy(0, 300)")
            page.wait_for_timeout(500)
            chat_btn = page.locator(
                "button:has-text('Conversar'), button:has-text('Chat'),"
                " [class*='chat-btn'], [aria-label*='chat']"
            ).first

        if not chat_btn.is_visible(timeout=3000):
            logger.error("Chat button not found for shop %s", lead.shop_id)
            screenshot_path = (
                error_dir / f"chat_error_{lead.shop_id}_{int(time.time())}.png"
            )
            page.screenshot(path=str(screenshot_path))
            return False

        chat_btn.click()

        # Wait for floating chat window
        chat_window_selector = (
            "[class*='chat'], [class*='floating-chat'], [class*='chat-window'],"
            " [class*='dialog']"
        )
        chat_window = page.locator(chat_window_selector).first
        chat_window.wait_for(state="visible", timeout=15000)

        # Attach image
        file_input = page.locator("input[type='file'][accept*='image']").first
        if file_input.count() > 0:
            logger.info("Attaching dossier infographic: %s", dossier_png_path)
            file_input.set_input_files(str(dossier_png_path))
            # Wait 2-4s for upload and preview to render
            page.wait_for_timeout(random.randint(2000, 4000))
        else:
            logger.warning(
                "Image file input not located in chat window for shop %s", lead.shop_id
            )

        pitch = generate_varied_shopee_pitch(lead)
        lines = pitch.split("\n")
        first_line = lines[0] if lines else pitch
        rest_of_pitch = "\n".join(lines[1:]) if len(lines) > 1 else ""

        # Locate message input
        editor = page.locator("textarea, div[contenteditable='true']").first
        editor.wait_for(state="visible", timeout=5000)
        editor.click()
        page.wait_for_timeout(400)

        # Simulate human keystrokes: press_sequentially on first line,
        # natural typing or insert for remainder
        editor.press_sequentially(first_line, delay=random.randint(25, 45))
        if rest_of_pitch:
            page.wait_for_timeout(random.randint(150, 300))
            page.keyboard.press("Shift+Enter")
            page.wait_for_timeout(random.randint(100, 200))
            page.keyboard.insert_text(rest_of_pitch)

        page.wait_for_timeout(1000)

        if dry_run:
            dry_run_path = error_dir / f"dry_run_chat_{lead.shop_id}.png"
            page.screenshot(path=str(dry_run_path))
            logger.info(
                "[DRY RUN] Pitch composed for shop %s. Screenshot: %s",
                lead.shop_id,
                dry_run_path,
            )
            return True

        send_btn = page.locator(
            "button:has-text('Enviar'), button.send-btn, svg.icon-send,"
            " [class*='send-button']"
        ).first
        if send_btn.is_visible(timeout=2000):
            send_btn.click()
        else:
            editor.press("Enter")

        page.wait_for_timeout(random.randint(2000, 3000))

        confirm_path = error_dir / f"sent_chat_{lead.shop_id}_{int(time.time())}.png"
        page.screenshot(path=str(confirm_path))
        logger.info("Outreach dispatched successfully to shop %s", lead.shop_id)
        return True

    except Exception as e:
        logger.error(
            "Error sending chat message to shop %s: %s",
            lead.shop_id,
            e,
            exc_info=True,
        )
        ts = int(time.time())
        try:
            page.screenshot(path=str(error_dir / f"chat_error_{lead.shop_id}_{ts}.png"))
        except Exception:
            pass
        return False


def send_shopee_outreach_batch(
    limit: int = 10,
    *,
    dry_run: bool = False,
    headful: bool = True,
    lead_id: int | None = None,
    delay_range: tuple[int, int] = (90, 180),
) -> dict[str, Any]:
    """Execute batch outreach to qualified StoreLead records via Shopee Chat.

    Why: Coordinates the end-to-end prospecting cycle, enforcing rate limits and natural
    delays between conversations to avoid bot detection while recording state changes in the CRM.
    """
    dossier_path = get_weekly_dossier_png_path()
    if not dossier_path or not dossier_path.exists():
        raise FileNotFoundError(
            f"Weekly dossier PNG infographic not found at '{dossier_path}'. "
            "Run 'python -m agents.dossier.agent' to compile the weekly dossier before outreach."
        )

    with session_scope() as session:
        if lead_id is not None:
            lead = session.get(StoreLead, lead_id)
            leads = [lead] if lead is not None else []
        else:
            query = (
                select(StoreLead)
                .where(StoreLead.status == "discovered")
                .order_by(StoreLead.discovered_at.desc())
                .limit(limit)
            )
            leads = list(session.exec(query).all())

    if not leads:
        logger.info("No leads matching outreach criteria.")
        return {"dispatched": 0, "status": "no_leads"}

    summary: dict[str, Any] = {
        "dispatched": 0,
        "failed": 0,
        "total": len(leads),
        "status": "completed",
        "dry_run": dry_run,
        "lead_ids": [ld.id for ld in leads if ld.id is not None],
    }

    with core.ledger.run(
        "outreach_shopee_chat",
        inputs={
            "limit": limit,
            "dry_run": dry_run,
            "headful": headful,
            "lead_id": lead_id,
        },
    ) as run_handle:
        with sync_playwright() as pw:
            browser, context = _new_browser_context(pw, headless=not headful)
            try:
                page = context.new_page()
                for i, lead in enumerate(leads):
                    logger.info(
                        "Processing lead %d/%d (Shop ID: %s, Name: %s)",
                        i + 1,
                        len(leads),
                        lead.shop_id,
                        lead.shop_name,
                    )
                    success = send_lead_message(
                        page,
                        lead,
                        dossier_path,
                        dry_run=dry_run,
                        headful=headful,
                    )
                    if success:
                        summary["dispatched"] += 1
                        if not dry_run and lead.id is not None:
                            with session_scope() as session:
                                db_lead = session.get(StoreLead, lead.id)
                                if db_lead:
                                    db_lead.status = "sample_sent"
                                    now = datetime.now(UTC).replace(tzinfo=None)
                                    db_lead.last_contacted_at = now
                                    db_lead.preferred_channel = "shopee_chat"
                                    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
                                    note_entry = (
                                        f"[Shopee Chat] Dossiê enviado em {timestamp_str}."
                                    )
                                    existing_notes = db_lead.notes or ""
                                    db_lead.notes = f"{existing_notes}\n{note_entry}".strip()
                                    session.add(db_lead)
                                    session.commit()
                    else:
                        summary["failed"] += 1

                    is_last = i == len(leads) - 1
                    if not is_last and not (dry_run and len(leads) == 1):
                        delay = random.randint(delay_range[0], delay_range[1])
                        logger.info(
                            "Throttling between contacts: sleeping %d seconds...", delay
                        )
                        time.sleep(delay)
            finally:
                context.close()
                browser.close()

        run_handle.set_outputs(
            f"dispatched={summary['dispatched']}, failed={summary['failed']}"
        )

    return summary


def main() -> None:
    """CLI entrypoint for triggering the Shopee Chat outreach process.

    Why: Allows manual execution, debugging runs, and scheduled cron jobs
    to initiate seller outreach directly from the terminal.
    """
    parser = argparse.ArgumentParser(description="Shopee Chat Outreach Agent")
    parser.add_argument("--lead-id", type=int, help="Specific lead ID to message")
    parser.add_argument(
        "--limit", type=int, default=10, help="Max leads to process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without sending messages or updating DB",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        default=True,
        help="Run browser in headful mode (default)",
    )
    parser.add_argument(
        "--headless",
        dest="headful",
        action="store_false",
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--delay-min",
        type=int,
        default=90,
        help="Min delay between messages in seconds",
    )
    parser.add_argument(
        "--delay-max",
        type=int,
        default=180,
        help="Max delay between messages in seconds",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    result = send_shopee_outreach_batch(
        limit=args.limit,
        dry_run=args.dry_run,
        headful=args.headful,
        lead_id=args.lead_id,
        delay_range=(args.delay_min, args.delay_max),
    )
    print(f"Batch result: {result}")


if __name__ == "__main__":
    main()
