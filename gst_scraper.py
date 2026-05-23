# gst_scraper.py - FIXED TO CLICK SHOW FILING TABLE BUTTON
import sys
import asyncio
import threading
import time
import re
import base64
import uuid
from playwright.sync_api import sync_playwright

# All 8 return types we track
RETURN_TYPES = [
        "gstr1_iff", "gstr3b", "gstr4", "cmp08",
        "gstr4_annual", "gstr9_annual", "gstr9c", "gstr1a"
]

# How the GST portal labels map to our keys
LABEL_TO_KEY = {
        "gstr1": "gstr1_iff", "gstr-1": "gstr1_iff", "gstr1/iff": "gstr1_iff",
        "gstr-1/iff": "gstr1_iff", "iff": "gstr1_iff", "gstr3b": "gstr3b",
        "gstr-3b": "gstr3b", "gstr4": "gstr4", "gstr-4": "gstr4",
        "cmp-08": "cmp08", "cmp08": "cmp08", "gstr9": "gstr9_annual",
        "gstr-9": "gstr9_annual", "gstr9c": "gstr9c", "gstr-9c": "gstr9c",
        "gstr1a": "gstr1a", "gstr-1a": "gstr1a"
    }

# Session store
_active_sessions: dict = {}
_sessions_lock = threading.Lock()
SESSION_TTL_SECONDS = 300
def _store_session(session_id: str, data: dict):
    with _sessions_lock:
        _active_sessions[session_id] = {**data, "created_at": time.time()}
def _pop_session(session_id: str) -> dict | None:
    with _sessions_lock:
        return _active_sessions.pop(session_id, None)
async def cleanup_stale_sessions():
        while True:
            await asyncio.sleep(60)
            now = time.time()
            with _sessions_lock:
                stale_ids = [sid for sid, s in _active_sessions.items()
                            if now - s["created_at"] > SESSION_TTL_SECONDS]
            for sid in stale_ids:
                with _sessions_lock:
                    session = _active_sessions.pop(sid, None)
                if session:
                    try:
                        session["browser"].close()
                        session["playwright"].stop()
                    except Exception:
                        pass
# ── CAPTCHA FETCH ──────────────────────────────────────────────────────────
def _start_gst_search_sync(gstin: str) -> dict:
    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=False,
        slow_mo=100,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    context = browser.new_context(
        viewport={"width": 1400, "height": 1200},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = context.new_page()
    try:
        page.goto("https://services.gst.gov.in/services/searchtp", timeout=60000)
        page.wait_for_selector("#for_gstin")
        page.type("#for_gstin", gstin, delay=120)
        page.keyboard.press("Tab")
        page.wait_for_timeout(1500)
        captcha_img = page.wait_for_selector("#imgCaptcha", state="visible", timeout=20000)
        screenshot_bytes = captcha_img.screenshot()
        captcha_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        session_id = str(uuid.uuid4())
        _store_session(session_id, {"browser": browser, "page": page, "playwright": p})
        return {
            "session_id": session_id,
            "captcha_image": f"data:image/png;base64,{captcha_base64}",
        }
    except Exception as e:
        try:
            browser.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass
        raise RuntimeError(f"GST captcha fetch failed: {e}") from e
async def start_gst_search(gstin: str) -> dict:
    return await asyncio.to_thread(_start_gst_search_sync, gstin)
# ── CAPTCHA SUBMIT + SCRAPE ───────────────────────────────────────────────
def _submit_captcha_and_scrape_sync(session_id: str, captcha_text: str) -> dict:
    session = _pop_session(session_id)
    if not session:
        raise ValueError("Session expired or invalid. Please fetch a new captcha.")
    browser = session["browser"]
    page = session["page"]
    p = session["playwright"]
    try:
        # Fill captcha
        filled = False
        for selector in [
            lambda: page.get_by_placeholder("Enter Characters"),
            lambda: page.locator("#fo-captcha"),
            lambda: page.locator("input[type='text'][maxlength='6']"),
        ]:
            try:
                el = selector()
                if el.count() > 0:
                    el.first.fill(captcha_text)
                    filled = True
                    break
            except Exception:
                continue
        if not filled:
            raise RuntimeError("Could not locate captcha input field.")
        page.wait_for_timeout(500)
        page.click('button:has-text("SEARCH")')
        page.wait_for_timeout(7000)
        # Extract basic business info
        text_elements = page.locator("div, span, p, td, th, label").all()
        all_text = []
        for el in text_elements:
            try:
                t = el.inner_text().strip()
                if t and len(t) > 1:
                    all_text.append(t)
            except Exception:
                continue
        seen: set = set()
        cleaned: list[str] = []
        for x in all_text:
            if x not in seen:
                cleaned.append(x)
                seen.add(x)
        IMPORTANT_FIELDS = [
            "Legal Name of Business",
            "Trade Name",
            "Effective Date of registration",
            "Constitution of Business",
            "GSTIN / UIN Status",
            "Taxpayer Type",
            "Principal Place of Business",
            "Nature of Business Activities",
        ]
        gst_data: dict = {}
        for i in range(len(cleaned) - 1):
            if cleaned[i] in IMPORTANT_FIELDS:
                gst_data[cleaned[i]] = cleaned[i + 1]
        result = {
            "legal_name": gst_data.get("Legal Name of Business"),
            "trade_name": gst_data.get("Trade Name"),
            "registration_date": gst_data.get("Effective Date of registration"),
            "constitution": gst_data.get("Constitution of Business"),
            "status": gst_data.get("GSTIN / UIN Status"),
            "taxpayer_type": gst_data.get("Taxpayer Type"),
            "principal_place": gst_data.get("Principal Place of Business"),
            "business_activity": gst_data.get("Nature of Business Activities"),
        }
        # Extract filing returns
        result["filings"] = _scrape_filing_returns_sync(page)
        print(
            f"\n========== CURRENT FY ==========\n{result['filings']['current']}\n",
            file=sys.stderr
        )

        print(
            f"\n========== PREVIOUS FY ==========\n{result['filings']['previous']}\n",
            file=sys.stderr
        )
        return result
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass
async def submit_captcha_and_scrape(session_id: str, captcha_text: str) -> dict:
    return await asyncio.to_thread(_submit_captcha_and_scrape_sync, session_id, captcha_text)
# ── FILING RETURNS SCRAPER ─────────────────────────────────────────────────
def _scrape_filing_returns_sync(page) -> dict:
    result = {
        "current": {rt: {"status": "N/A"} for rt in RETURN_TYPES},
        "previous": {rt: {"status": "N/A"} for rt in RETURN_TYPES},
    }
    try:
        # Step 1: Scroll down to find SHOW FILING TABLE button
        page.evaluate("window.scrollBy(0, 2000)")
        page.wait_for_timeout(2000)
        # Step 2: Wait for SHOW FILING TABLE to be enabled then click it
        print("[GST] Waiting for SHOW FILING TABLE to be enabled...", file=sys.stderr)
        page.wait_for_selector('button#filingTable:not([disabled])', state="visible", timeout=15000)
        page.locator('button#filingTable').scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        page.locator('button#filingTable').click()
        print("[GST] Clicked SHOW FILING TABLE", file=sys.stderr)
        page.wait_for_timeout(1500)
        # Step 3: Click SEARCH to display current year table
        search_btn = page.locator('button:has-text("SEARCH")').last
        search_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        search_btn.click()
        print("[GST] Clicked SEARCH for current FY", file=sys.stderr)
        # Wait for table to appear
        page.wait_for_selector('text=Filing details for', timeout=15000)
        page.wait_for_timeout(1000)
        print("[GST] Current FY table loaded", file=sys.stderr)
        # Step 4: Fetch current year table
        result["current"] = _parse_filing_table_sync(page)
        # Step 5: Click FY dropdown
        fy_dropdown = page.locator('select').first
        fy_dropdown.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        options = fy_dropdown.locator('option')
        total_options = options.count()
        print(f"[GST] Found {total_options} FY options", file=sys.stderr)
        if total_options > 1:
            # Step 6: Select previous year (index 1)
            fy_dropdown.select_option(index=1)
            page.wait_for_timeout(500)
            print("[GST] Selected previous FY", file=sys.stderr)
            # Step 7: Click SEARCH again
            search_btn = page.locator('button:has-text("SEARCH")').last
            search_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            search_btn.click()
            print("[GST] Clicked SEARCH for previous FY", file=sys.stderr)
            # Wait for old table to clear
            try:
                page.wait_for_selector('text=Filing details for', state="hidden", timeout=5000)
                print("[GST] Old table cleared", file=sys.stderr)
            except Exception:
                print("[GST] Old table did not clear, continuing...", file=sys.stderr)
            # Step 8: Scroll down and wait for new table
            page.evaluate("window.scrollBy(0, 500)")
            page.wait_for_selector('text=Filing details for', state="visible", timeout=15000)
            page.wait_for_timeout(1000)
            print("[GST] Previous FY table loaded", file=sys.stderr)
            # Step 9: Fetch previous year table
            result["previous"] = _parse_filing_table_sync(page)
            print("[GST] Done", file=sys.stderr)
    except Exception as e:
        print(f"[GST] Filing scrape error: {e}", file=sys.stderr)
    return result
# ── HELPERS ────────────────────────────────────────────────────────────────
def _extract_period(text: str, start_pos: int) -> str | None:
    window = text[start_pos : start_pos + 300]
    match = re.search(
        r'(January|February|March|April|May|June|July|August|September|'
        r'October|November|December|Q[1-4]|Jan|Feb|Mar|Apr|May|Jun|Jul|'
        r'Aug|Sep|Oct|Nov|Dec)[\s\-]*\d{4}',
        window, re.IGNORECASE
    )
    return match.group(0).strip() if match else None
    
def _extract_date(text: str, start_pos: int) -> str | None:
    window = text[start_pos : start_pos + 500]
    match = re.search(r'\d{2}[/\-]\d{2}[/\-]\d{4}', window)
    return match.group(0) if match else None

def _parse_filing_table_sync(page) -> dict:
    all_returns = {}
    try:
        sections = page.locator("h4")
        section_count = sections.count()
        print(
            f"[GST] TOTAL SECTIONS = {section_count}",
            file=sys.stderr
        )   
        all_returns = {}
        for i in range(section_count):
            try:
                heading = sections.nth(i)
                heading_text = heading.inner_text().strip()
                if "filing details for" not in heading_text.lower():
                    continue
                print(
                    f"\n[GST] HEADING = {heading_text}",
                    file=sys.stderr
                )
                raw_label = (
                    heading_text
                    .replace("Filing details for", "")
                    .strip()
                    .lower()
                )
                normalized_label = (
                    raw_label
                    .replace(" ", "")
                )
                normalized = LABEL_TO_KEY.get(
                    normalized_label,
                    normalized_label
                )
                table = heading.locator(
                    "xpath=following::table[1]"
                )
                rows = table.locator("tbody tr")
                row_count = rows.count()
                print(
                    f"[GST] ROWS FOUND = {row_count}",
                    file=sys.stderr
                )
                parsed_rows = {}
                for r in range(row_count):
                    try:
                        row = rows.nth(r)
                        cols = row.locator("td")
                        if cols.count() < 4:
                            continue
                        fy = cols.nth(0).inner_text().strip()
                        period = cols.nth(1).inner_text().strip()
                        filing_date = cols.nth(2).inner_text().strip()
                        status_raw = cols.nth(3).inner_text().strip()
                        status_lower = status_raw.lower()
                        status = "N/A"
                        if "not filed" in status_lower:
                            status = "Not Filed"
                        elif "filed" in status_lower:
                            status = "Filed"
                        elif "pending" in status_lower:
                            status = "Pending"
                        month_key = (
                            period.lower()
                            .replace(" ", "_")
                            .replace("-", "_")
                        )
                        parsed_rows[month_key] = {
                            "fy": fy,
                            "period": period,
                            "date": filing_date,
                            "status": status
                        }
                        print(
                            f"[GST] SAVED {normalized} => {month_key}",
                            file=sys.stderr
                        )
                    except Exception as row_error:
                        print(
                            f"[GST] ROW ERROR => {row_error}",
                            file=sys.stderr
                        )
                all_returns[normalized] = parsed_rows
            except Exception as section_error:
                print(
                    f"[GST] SECTION ERROR => {section_error}",
                    file=sys.stderr
                )
                continue
        return all_returns
    except Exception as e:
        print(
            f"[GST] Table parse error: {e}",
            file=sys.stderr
        )
        return {}