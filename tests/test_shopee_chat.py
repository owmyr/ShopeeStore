"""Tests for Shopee Chat Outreach module.

Why: The Shopee Chat outreach agent delivers weekly trend intelligence dossiers
directly to validated apparel sellers on Shopee BR. Thorough testing guarantees
that anti-spam pitch variations and forbidden word protections work correctly,
DOM interaction fallbacks function under simulated conditions, error screenshots
are captured during failures, and CRM lead transitions are persistently recorded.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import select

import agents.outreach.shopee_chat as shopee_chat
from agents.outreach.shopee_chat import (
    _check_captcha_or_wall,
    _dismiss_overlays,
    _new_browser_context,
    generate_varied_shopee_pitch,
    main,
    send_lead_message,
    send_shopee_outreach_batch,
)
from core.db import session_scope
from core.models import AgentLedger, StoreLead


class MockLocator:
    """Mock Playwright Locator with chainable methods and interaction tracking."""

    def __init__(
        self,
        *,
        visible: bool = True,
        count_val: int = 1,
        click_side_effect: Exception | None = None,
    ) -> None:
        self._visible = visible
        self._count = count_val
        self._click_side_effect = click_side_effect
        self.clicked = False
        self.click_count = 0
        self.pressed_keys: list[str] = []
        self.typed_texts: list[str] = []
        self.input_files: list[str] = []

    @property
    def first(self) -> "MockLocator":
        """Simulate locator .first property returning self."""
        return self

    def is_visible(self, timeout: int | None = None) -> bool:
        """Simulate checking element visibility."""
        return self._visible

    def count(self) -> int:
        """Return element match count."""
        return self._count

    def click(self, timeout: int | None = None) -> None:
        """Simulate clicking element, with optional exception trigger."""
        if self._click_side_effect:
            raise self._click_side_effect
        self.clicked = True
        self.click_count += 1

    def wait_for(self, state: str = "visible", timeout: int | None = None) -> None:
        """Simulate waiting for state."""
        if not self._visible and state == "visible":
            raise TimeoutError("Element wait_for timed out")

    def press_sequentially(self, text: str, delay: int = 0) -> None:
        """Record keystroke text entries."""
        self.typed_texts.append(text)

    def press(self, key: str) -> None:
        """Record keyboard key presses."""
        self.pressed_keys.append(key)

    def set_input_files(self, files: str | list[str]) -> None:
        """Record uploaded files."""
        if isinstance(files, list):
            self.input_files.extend(files)
        else:
            self.input_files.append(files)


class MockKeyboard:
    """Mock Playwright Keyboard."""

    def __init__(self) -> None:
        self.pressed: list[str] = []
        self.inserted_texts: list[str] = []

    def press(self, key: str) -> None:
        """Record keyboard press."""
        self.pressed.append(key)

    def insert_text(self, text: str) -> None:
        """Record text insertion."""
        self.inserted_texts.append(text)


class MockPage:
    """Mock Playwright Page for simulated browser interactions."""

    def __init__(
        self,
        url: str = "https://shopee.com.br/shop/999888",
    ) -> None:
        self.url = url
        self.keyboard = MockKeyboard()
        self.screenshots: list[str] = []
        self.visited_urls: list[str] = []
        self.text_locators: dict[str, MockLocator] = {}
        self.selector_locators: dict[str, MockLocator] = {}
        self.chat_btn_locator = MockLocator(visible=True)
        self.goto_side_effect: Exception | None = None
        for captcha_sel in (
            "iframe[src*='verify']",
            "div.captcha-container",
            "text='Arraste para completar'",
        ):
            self.selector_locators[captcha_sel] = MockLocator(visible=False)

    def goto(self, url: str, **kwargs: Any) -> None:
        """Simulate navigation."""
        if self.goto_side_effect:
            raise self.goto_side_effect
        self.visited_urls.append(url)
        self.url = url

    def wait_for_timeout(self, ms: int) -> None:
        """Simulate timeout wait."""

    def evaluate(self, script: str) -> Any:
        """Simulate JS evaluation."""
        return None

    def screenshot(self, path: str, **kwargs: Any) -> None:
        """Simulate screenshot capture creating the artifact file."""
        self.screenshots.append(path)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"dummy_png_bytes")

    def get_by_text(self, text: str, exact: bool = False) -> MockLocator:
        """Return registered locator for text lookup."""
        if text not in self.text_locators:
            self.text_locators[text] = MockLocator(visible=False)
        return self.text_locators[text]

    def locator(self, selector: str) -> MockLocator:
        """Return registered locator for css/xpath selector."""
        if selector not in self.selector_locators:
            self.selector_locators[selector] = MockLocator(visible=False)
        return self.selector_locators[selector]

    def get_by_role(self, role: str, name: Any = None) -> MockLocator:
        """Return locator for accessibility role."""
        if role == "button":
            return self.chat_btn_locator
        return MockLocator(visible=False)


class MockPlaywrightContext:
    """Context manager for mocking sync_playwright."""

    def __enter__(self) -> MagicMock:
        return MagicMock()

    def __exit__(self, *args: Any) -> None:
        pass


# ==============================================================================
# 1. Test generate_varied_shopee_pitch
# ==============================================================================


class TestGenerateVariedShopeePitch:
    """Validate jittered pitch composition and platform safety constraints."""

    def test_lead_shop_name_included_in_pitch(self) -> None:
        """Ensure the target shop name is personalized into the greeting."""
        lead = StoreLead(
            shop_id=123,
            shop_name="Estamparia Radical",
            top_theme="anime",
            discovered_at=datetime.now(UTC),
            run_id="run_1",
        )
        pitch = generate_varied_shopee_pitch(lead)
        assert "Estamparia Radical" in pitch

    def test_forbidden_words_not_present(self) -> None:
        """Guarantee no external channel links or payment terms appear in pitches.

        Why: Shopee uses automated text filters to ban accounts that mention
        external contacts like WhatsApp, PIX or external URLs.
        """
        lead = StoreLead(
            shop_id=456,
            shop_name="Malharia Elite",
            top_theme="rock",
            discovered_at=datetime.now(UTC),
            run_id="run_1",
        )
        # Generate multiple pitches to test combinations of greetings/transitions/closings
        for _ in range(50):
            pitch = generate_varied_shopee_pitch(lead).lower()
            for forbidden in ("whatsapp", "pix", "http://", "https://", "www."):
                assert forbidden not in pitch, f"Forbidden term '{forbidden}' detected in pitch"

    def test_theme_mentioning_logic(self) -> None:
        """Verify theme mention varies appropriately based on lead data.

        - When specific theme is present -> highlighted in body text.
        - When theme is None -> falls back to 'estampas em alta'.
        - When theme is 'geral / multitemas' -> omits specific highlight to remain natural.
        """
        lead_specific = StoreLead(
            shop_id=101,
            shop_name="Otaku Shirts",
            top_theme="geek",
            discovered_at=datetime.now(UTC),
            run_id="run_1",
        )
        pitch_specific = generate_varied_shopee_pitch(lead_specific)
        assert "(com destaque no nicho de geek)" in pitch_specific

        lead_none = StoreLead(
            shop_id=102,
            shop_name="Camisas Top",
            top_theme=None,
            discovered_at=datetime.now(UTC),
            run_id="run_1",
        )
        pitch_none = generate_varied_shopee_pitch(lead_none)
        assert "(com destaque no nicho de estampas em alta)" in pitch_none

        lead_multi = StoreLead(
            shop_id=103,
            shop_name="Multimarcas Geral",
            top_theme="geral / multitemas",
            discovered_at=datetime.now(UTC),
            run_id="run_1",
        )
        pitch_multi = generate_varied_shopee_pitch(lead_multi)
        assert "(com destaque no nicho de" not in pitch_multi

    def test_linguistic_jitter_consistency(self) -> None:
        """Verify repeated calls generate varied non-empty structures with 5 paragraphs."""
        lead = StoreLead(
            shop_id=202,
            shop_name="Studio Camisetas",
            top_theme="automotivo",
            discovered_at=datetime.now(UTC),
            run_id="run_1",
        )
        pitches = {generate_varied_shopee_pitch(lead) for _ in range(30)}
        # With 3 greetings, 3 transitions, and 3 closings,
        # multiple distinct strings must be generated
        assert len(pitches) > 1

        for pitch in pitches:
            paragraphs = pitch.split("\n\n")
            assert len(paragraphs) == 5
            assert all(len(p.strip()) > 0 for p in paragraphs)

    def test_forbidden_word_detection_raises_value_error(self) -> None:
        """Ensure regex guard triggers ValueError if forbidden word is inadvertently introduced."""
        lead = StoreLead(
            shop_id=303,
            shop_name="WhatsApp Lojinha",  # Shop name contains forbidden keyword
            top_theme="streetwear",
            discovered_at=datetime.now(UTC),
            run_id="run_1",
        )
        with pytest.raises(ValueError, match="Forbidden words found"):
            generate_varied_shopee_pitch(lead)


# ==============================================================================
# 2. Test _dismiss_overlays
# ==============================================================================


class TestDismissOverlays:
    """Verify dismiss routines for cookie banners and modal overlays."""

    def test_dismiss_overlays_clicks_visible_targets(self) -> None:
        """Verify that visible cookie and language overlays are dismissed."""
        page = MockPage()
        for text in (
            "Português (BR)",
            "Aceitar todos os cookies",
            "Aceitar",
            "Entendi",
            "Fechar",
        ):
            page.text_locators[text] = MockLocator(visible=True)

        for selector in (
            "div.shopee-popup__close-btn",
            "button.cookie-banner__accept",
            "[aria-label='close']",
            "[aria-label='Fechar']",
            ".close-btn",
        ):
            page.selector_locators[selector] = MockLocator(visible=True)

        _dismiss_overlays(page)

        # Check text-based overlay clicks
        for text in (
            "Português (BR)",
            "Aceitar todos os cookies",
            "Aceitar",
            "Entendi",
            "Fechar",
        ):
            loc = page.get_by_text(text)
            assert loc.clicked, f"Expected text overlay '{text}' to be clicked"

        # Check selector-based close button clicks
        for selector in (
            "div.shopee-popup__close-btn",
            "button.cookie-banner__accept",
            "[aria-label='close']",
            "[aria-label='Fechar']",
            ".close-btn",
        ):
            loc = page.locator(selector)
            assert loc.clicked, f"Expected selector '{selector}' to be clicked"

    def test_dismiss_overlays_suppresses_exceptions(self) -> None:
        """Verify errors thrown during overlay dismissal are gracefully caught."""
        page = MockPage()
        # Set click on Português (BR) to raise an unexpected runtime error
        page.text_locators["Português (BR)"] = MockLocator(
            visible=True, click_side_effect=RuntimeError("DOM detached")
        )
        page.selector_locators["div.shopee-popup__close-btn"] = MockLocator(
            visible=True, click_side_effect=RuntimeError("Element obscured")
        )

        # Execution must complete cleanly without re-raising
        _dismiss_overlays(page)


# ==============================================================================
# 3. Test _check_captcha_or_wall
# ==============================================================================


class TestCheckCaptchaOrWall:
    """Validate login wall and challenge detection across headless and headful modes."""

    def test_clear_url_returns_true(self, isolated: Path) -> None:
        """A normal storefront URL without challenge elements immediately returns True."""
        page = MockPage(url="https://shopee.com.br/shop/12345")
        assert _check_captcha_or_wall(page, headful=False) is True

    def test_headless_wall_captures_screenshot_and_returns_false(
        self, isolated: Path
    ) -> None:
        """Detecting a verify wall in headless mode takes an error screenshot and aborts."""
        page = MockPage(url="https://shopee.com.br/verify/traffic/error")
        res = _check_captcha_or_wall(page, headful=False)
        assert res is False
        assert len(page.screenshots) == 1
        assert "captcha_" in page.screenshots[0]
        assert Path(page.screenshots[0]).exists()

    def test_headful_wall_resolves_when_solved(self, isolated: Path) -> None:
        """In headful mode, when the challenge clears, check returns True."""
        page = MockPage(url="https://shopee.com.br/verify/captcha")

        # Simulate operator solving captcha: after first wait_for_timeout, url normalizes
        original_wait = page.wait_for_timeout

        def simulate_solve(ms: int) -> None:
            original_wait(ms)
            page.url = "https://shopee.com.br/shop/12345"

        page.wait_for_timeout = simulate_solve  # type: ignore[method-assign]

        res = _check_captcha_or_wall(page, timeout_sec=10, headful=True)
        assert res is True

    def test_headful_wall_times_out_and_returns_false(self, isolated: Path) -> None:
        """In headful mode, when the challenge is not solved within timeout, returns False."""
        page = MockPage(url="https://shopee.com.br/verify/captcha")
        # Set timeout_sec=0 to immediately trigger the timeout condition
        res = _check_captcha_or_wall(page, timeout_sec=0, headful=True)
        assert res is False
        assert any("captcha_timeout_" in s for s in page.screenshots)

    def test_wall_detected_via_dom_selector(self, isolated: Path) -> None:
        """Detecting captcha via DOM container even when URL is disguised triggers wall handling."""
        page = MockPage(url="https://shopee.com.br/shop/12345")
        # Mark captcha container visible
        page.selector_locators["div.captcha-container"] = MockLocator(visible=True)

        res = _check_captcha_or_wall(page, headful=False)
        assert res is False
        assert len(page.screenshots) == 1


# ==============================================================================
# 4. Test send_lead_message
# ==============================================================================


class TestSendLeadMessage:
    """Validate seller storefront navigation, message composition, and dispatch."""

    def _setup_lead(self) -> StoreLead:
        return StoreLead(
            shop_id=987654,
            shop_name="Estampa Moderna",
            shop_url="https://shopee.com.br/estampamoderna",
            top_theme="anime",
            discovered_at=datetime.now(UTC),
            run_id="run_test",
        )

    def _setup_page(self) -> tuple[MockPage, MockLocator, MockLocator, MockLocator, MockLocator]:
        """Configure page with standard interactive elements for chat testing."""
        page = MockPage()

        chat_btn_loc = MockLocator(visible=True)
        page.chat_btn_locator = chat_btn_loc

        chat_win_sel = (
            "[class*='chat'], [class*='floating-chat'], [class*='chat-window'],"
            " [class*='dialog']"
        )
        chat_win_loc = MockLocator(visible=True)
        page.selector_locators[chat_win_sel] = chat_win_loc

        file_input_loc = MockLocator(visible=True, count_val=1)
        page.selector_locators["input[type='file'][accept*='image']"] = file_input_loc

        editor_loc = MockLocator(visible=True)
        page.selector_locators["textarea, div[contenteditable='true']"] = editor_loc

        send_btn_sel = (
            "button:has-text('Enviar'), button.send-btn, svg.icon-send,"
            " [class*='send-button']"
        )
        send_btn_loc = MockLocator(visible=True)
        page.selector_locators[send_btn_sel] = send_btn_loc

        return page, chat_btn_loc, file_input_loc, editor_loc, send_btn_loc

    def test_dry_run_mode(self, isolated: Path) -> None:
        """Dry run performs all actions up to typing pitch and captures
        dry run screenshot without sending.
        """
        lead = self._setup_lead()
        dossier_png = isolated / "dossier_sample.png"
        dossier_png.write_bytes(b"dummy_image")

        page, chat_btn_loc, file_input_loc, editor_loc, send_btn_loc = self._setup_page()

        success = send_lead_message(page, lead, dossier_png, dry_run=True, headful=False)
        assert success is True

        # Assert navigation occurred
        assert page.visited_urls == ["https://shopee.com.br/estampamoderna"]

        # Assert dossier attached
        assert file_input_loc.input_files == [str(dossier_png)]

        # Assert pitch was typed
        assert len(editor_loc.typed_texts) == 1
        assert "Estampa Moderna" in editor_loc.typed_texts[0]
        assert "Shift+Enter" in page.keyboard.pressed
        assert len(page.keyboard.inserted_texts) == 1

        # Assert dry-run screenshot was taken
        assert any(f"dry_run_chat_{lead.shop_id}.png" in s for s in page.screenshots)

        # CRITICAL: In dry run, send button is NOT clicked and Enter is NOT pressed
        assert not send_btn_loc.clicked
        assert "Enter" not in editor_loc.pressed_keys

    def test_normal_send_with_button_click(self, isolated: Path) -> None:
        """Normal mode clicks send button and captures confirmation screenshot."""
        lead = self._setup_lead()
        dossier_png = isolated / "dossier_sample.png"
        dossier_png.write_bytes(b"dummy_image")

        page, _, _, _, send_btn_loc = self._setup_page()

        success = send_lead_message(page, lead, dossier_png, dry_run=False, headful=False)
        assert success is True

        # Verify send button clicked
        assert send_btn_loc.clicked
        # Verify confirmation screenshot taken
        assert any(f"sent_chat_{lead.shop_id}_" in s for s in page.screenshots)

    def test_normal_send_fallback_to_enter_press(self, isolated: Path) -> None:
        """When send button is not found, falls back to pressing Enter on the editor."""
        lead = self._setup_lead()
        dossier_png = isolated / "dossier_sample.png"
        dossier_png.write_bytes(b"dummy_image")

        page, _, _, editor_loc, send_btn_loc = self._setup_page()
        # Mark send button NOT visible
        send_btn_loc._visible = False

        success = send_lead_message(page, lead, dossier_png, dry_run=False, headful=False)
        assert success is True
        assert "Enter" in editor_loc.pressed_keys
        assert any(f"sent_chat_{lead.shop_id}_" in s for s in page.screenshots)

    def test_exception_handling_captures_error_screenshot(self, isolated: Path) -> None:
        """If navigation or DOM interaction fails, catches exception and logs screenshot."""
        lead = self._setup_lead()
        dossier_png = isolated / "dossier_sample.png"
        dossier_png.write_bytes(b"dummy_image")

        page, _, _, _, _ = self._setup_page()
        page.goto_side_effect = TimeoutError("Connection reset by peer")

        success = send_lead_message(page, lead, dossier_png, dry_run=False, headful=False)
        assert success is False
        assert any(f"chat_error_{lead.shop_id}_" in s for s in page.screenshots)

    def test_security_wall_unresolved_returns_false(self, isolated: Path) -> None:
        """When security wall or captcha is active, returns False without attempting to chat."""
        lead = self._setup_lead()
        dossier_png = isolated / "dossier_sample.png"
        dossier_png.write_bytes(b"dummy_image")

        page, _, _, _, _ = self._setup_page()

        # Simulate storefront navigation redirecting to security wall
        def redirect_to_wall(url: str, **kwargs: Any) -> None:
            page.url = "https://shopee.com.br/verify/traffic/error"

        page.goto = redirect_to_wall  # type: ignore[method-assign]

        success = send_lead_message(page, lead, dossier_png, dry_run=False, headful=False)
        assert success is False

    def test_chat_button_not_found_returns_false(self, isolated: Path) -> None:
        """When chat launcher button is not present on storefront,
        saves error screenshot and returns False.
        """
        lead = self._setup_lead()
        dossier_png = isolated / "dossier_sample.png"
        dossier_png.write_bytes(b"dummy_image")

        page, chat_btn_loc, _, _, _ = self._setup_page()
        chat_btn_loc._visible = False

        success = send_lead_message(page, lead, dossier_png, dry_run=False, headful=False)
        assert success is False
        assert any(f"chat_error_{lead.shop_id}_" in s for s in page.screenshots)


# ==============================================================================
# 5. Test send_shopee_outreach_batch
# ==============================================================================


class TestSendShopeeOutreachBatch:
    """Verify batch orchestration, database state transitions, and ledger logging."""

    def test_missing_dossier_raises_file_not_found(
        self, isolated: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises FileNotFoundError if weekly infographic has not been pre-compiled."""
        monkeypatch.setattr(
            shopee_chat,
            "get_weekly_dossier_png_path",
            lambda: isolated / "nonexistent_dossier.png",
        )
        with pytest.raises(FileNotFoundError, match="Weekly dossier PNG infographic not found"):
            send_shopee_outreach_batch()

    def test_no_discovered_leads_returns_no_leads_status(
        self, isolated: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns dispatched=0 and status='no_leads' when CRM has no matching candidates."""
        dossier_file = isolated / "dossier.png"
        dossier_file.write_bytes(b"img")
        monkeypatch.setattr(
            shopee_chat, "get_weekly_dossier_png_path", lambda: dossier_file
        )

        result = send_shopee_outreach_batch()
        assert result == {"dispatched": 0, "status": "no_leads"}

    def test_batch_dispatches_leads_updates_db_and_logs_ledger(
        self, isolated: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulate successful batch dispatch with DB updates and ledger recording."""
        dossier_file = isolated / "dossier.png"
        dossier_file.write_bytes(b"img")
        monkeypatch.setattr(
            shopee_chat, "get_weekly_dossier_png_path", lambda: dossier_file
        )

        # Seed 2 discovered leads
        with session_scope() as session:
            lead1 = StoreLead(
                shop_id=111,
                shop_name="Loja Alfa",
                status="discovered",
                discovered_at=datetime.now(UTC),
                run_id="seed",
            )
            lead2 = StoreLead(
                shop_id=222,
                shop_name="Loja Beta",
                status="discovered",
                discovered_at=datetime.now(UTC),
                run_id="seed",
            )
            session.add(lead1)
            session.add(lead2)
            session.commit()
            lead1_id = lead1.id
            lead2_id = lead2.id

        # Mock browser and send_lead_message
        mock_page = MockPage()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()

        monkeypatch.setattr(shopee_chat, "sync_playwright", lambda: MockPlaywrightContext())
        monkeypatch.setattr(
            shopee_chat,
            "_new_browser_context",
            lambda pw, headless: (mock_browser, mock_context),
        )

        sent_leads: list[StoreLead] = []

        def mock_send(
            page: Any,
            lead: StoreLead,
            dossier_path: Path,
            *,
            dry_run: bool = False,
            headful: bool = True,
        ) -> bool:
            sent_leads.append(lead)
            return True

        monkeypatch.setattr(shopee_chat, "send_lead_message", mock_send)

        # Zero out sleep delay
        sleep_calls: list[int] = []
        monkeypatch.setattr(shopee_chat.time, "sleep", lambda s: sleep_calls.append(s))

        # Execute batch
        res = send_shopee_outreach_batch(
            limit=5,
            dry_run=False,
            headful=False,
            delay_range=(5, 10),
        )

        # Assert result summary
        assert res["dispatched"] == 2
        assert res["failed"] == 0
        assert res["status"] == "completed"
        assert res["total"] == 2
        assert set(res["lead_ids"]) == {lead1_id, lead2_id}

        # Assert delay throttling between 2 leads occurred once
        assert len(sleep_calls) == 1
        assert 5 <= sleep_calls[0] <= 10

        # Verify DB updates on both leads
        with session_scope() as session:
            db_l1 = session.get(StoreLead, lead1_id)
            assert db_l1 is not None
            assert db_l1.status == "sample_sent"
            assert db_l1.preferred_channel == "shopee_chat"
            assert db_l1.last_contacted_at is not None
            assert db_l1.notes is not None
            assert "[Shopee Chat] Dossiê enviado em" in db_l1.notes

            db_l2 = session.get(StoreLead, lead2_id)
            assert db_l2 is not None
            assert db_l2.status == "sample_sent"
            assert db_l2.preferred_channel == "shopee_chat"
            assert db_l2.last_contacted_at is not None
            assert db_l2.notes is not None
            assert "[Shopee Chat] Dossiê enviado em" in db_l2.notes

        # Verify ledger entry was created
        with session_scope() as session:
            ledgers = list(session.exec(select(AgentLedger)).all())
            chat_runs = [entry for entry in ledgers if entry.agent == "outreach_shopee_chat"]
            assert len(chat_runs) >= 1
            assert chat_runs[-1].outputs_path == "dispatched=2, failed=0"

    def test_batch_single_lead_id_targeting(
        self, isolated: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Targeting a specific lead ID processes only that record."""
        dossier_file = isolated / "dossier.png"
        dossier_file.write_bytes(b"img")
        monkeypatch.setattr(
            shopee_chat, "get_weekly_dossier_png_path", lambda: dossier_file
        )

        with session_scope() as session:
            lead = StoreLead(
                shop_id=777,
                shop_name="Loja Alvo",
                status="discovered",
                discovered_at=datetime.now(UTC),
                run_id="seed",
            )
            session.add(lead)
            session.commit()
            target_id = lead.id

        mock_context = MagicMock()
        mock_browser = MagicMock()
        monkeypatch.setattr(shopee_chat, "sync_playwright", lambda: MockPlaywrightContext())
        monkeypatch.setattr(
            shopee_chat,
            "_new_browser_context",
            lambda pw, headless: (mock_browser, mock_context),
        )
        monkeypatch.setattr(shopee_chat, "send_lead_message", lambda *args, **kwargs: True)

        res = send_shopee_outreach_batch(lead_id=target_id, dry_run=True)
        assert res["dispatched"] == 1
        assert res["lead_ids"] == [target_id]

        # In dry run, DB lead status remains 'discovered'
        with session_scope() as session:
            db_lead = session.get(StoreLead, target_id)
            assert db_lead is not None
            assert db_lead.status == "discovered"

    def test_batch_handles_lead_failure(
        self, isolated: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When message dispatch fails, increments failed count without modifying lead status."""
        dossier_file = isolated / "dossier.png"
        dossier_file.write_bytes(b"img")
        monkeypatch.setattr(
            shopee_chat, "get_weekly_dossier_png_path", lambda: dossier_file
        )

        with session_scope() as session:
            lead = StoreLead(
                shop_id=888,
                shop_name="Loja Problemática",
                status="discovered",
                discovered_at=datetime.now(UTC),
                run_id="seed",
            )
            session.add(lead)
            session.commit()
            lead_id = lead.id

        mock_context = MagicMock()
        mock_browser = MagicMock()
        monkeypatch.setattr(shopee_chat, "sync_playwright", lambda: MockPlaywrightContext())
        monkeypatch.setattr(
            shopee_chat,
            "_new_browser_context",
            lambda pw, headless: (mock_browser, mock_context),
        )
        monkeypatch.setattr(shopee_chat, "send_lead_message", lambda *args, **kwargs: False)

        res = send_shopee_outreach_batch(lead_id=lead_id)
        assert res["dispatched"] == 0
        assert res["failed"] == 1

        with session_scope() as session:
            db_lead = session.get(StoreLead, lead_id)
            assert db_lead is not None
            assert db_lead.status == "discovered"
            assert db_lead.last_contacted_at is None


# ==============================================================================
# 6. Test _new_browser_context
# ==============================================================================


class TestNewBrowserContext:
    """Verify browser and context launching with evasion settings and auth state."""

    def test_raises_when_auth_file_missing(
        self, isolated: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing auth state file triggers FileNotFoundError with login instruction."""
        monkeypatch.setenv("SHOPEE_AUTH_PATH", str(isolated / "missing_auth.json"))
        shopee_chat.get_settings.cache_clear()

        with pytest.raises(FileNotFoundError, match="Shopee auth session file not found"):
            _new_browser_context(MagicMock(), headless=True)

    def test_creates_evasion_context_with_auth_state(
        self, isolated: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valid auth state initializes Chrome with pt-BR locale and anti-detection flags."""
        auth_file = isolated / "shopee_auth.json"
        auth_file.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("SHOPEE_AUTH_PATH", str(auth_file))
        shopee_chat.get_settings.cache_clear()

        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context

        browser, context = _new_browser_context(mock_pw, headless=False)

        assert browser is mock_browser
        assert context is mock_context

        mock_pw.chromium.launch.assert_called_once_with(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        mock_browser.new_context.assert_called_once()
        _, kwargs = mock_browser.new_context.call_args
        assert kwargs["locale"] == "pt-BR"
        assert kwargs["timezone_id"] == "America/Sao_Paulo"
        assert kwargs["storage_state"] == str(auth_file)


# ==============================================================================
# 7. Test CLI Parser
# ==============================================================================


class TestCLIParser:
    """Verify terminal argument parsing and invocation parameter propagation."""

    def test_cli_argument_parsing_with_custom_flags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Custom command line options are correctly parsed and forwarded to batch runner."""
        batch_calls: list[dict[str, Any]] = []

        def mock_batch(**kwargs: Any) -> dict[str, Any]:
            batch_calls.append(kwargs)
            return {"dispatched": 1, "status": "completed"}

        monkeypatch.setattr(shopee_chat, "send_shopee_outreach_batch", mock_batch)

        test_args = [
            "shopee_chat.py",
            "--lead-id",
            "99",
            "--limit",
            "25",
            "--dry-run",
            "--headless",
            "--delay-min",
            "45",
            "--delay-max",
            "75",
        ]

        with patch("sys.argv", test_args):
            main()

        assert len(batch_calls) == 1
        call = batch_calls[0]
        assert call["lead_id"] == 99
        assert call["limit"] == 25
        assert call["dry_run"] is True
        assert call["headful"] is False
        assert call["delay_range"] == (45, 75)

    def test_cli_argument_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default arguments match expected configuration when no flags are supplied."""
        batch_calls: list[dict[str, Any]] = []

        def mock_batch(**kwargs: Any) -> dict[str, Any]:
            batch_calls.append(kwargs)
            return {"dispatched": 0, "status": "completed"}

        monkeypatch.setattr(shopee_chat, "send_shopee_outreach_batch", mock_batch)

        with patch("sys.argv", ["shopee_chat.py"]):
            main()

        assert len(batch_calls) == 1
        call = batch_calls[0]
        assert call["lead_id"] is None
        assert call["limit"] == 10
        assert call["dry_run"] is False
        assert call["headful"] is True
        assert call["delay_range"] == (90, 180)
