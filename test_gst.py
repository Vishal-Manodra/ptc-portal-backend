import asyncio
import json
import os
# pyrefly: ignore [missing-import]
from playwright.async_api import async_playwright

OUTPUT_DIR = "gst_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def run_scraper():

    print("========== GST JSON SCRAPER ==========")

    gstin = input("Enter GSTIN: ").strip()

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False,
            slow_mo=100
        )

        context = await browser.new_context(
            viewport={"width": 1400, "height": 1200},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
        )

        page = await context.new_page()

        try:

            print("Opening GST Portal...")

            await page.goto(
                "https://services.gst.gov.in/services/searchtp",
                timeout=60000
            )

            await page.wait_for_selector("#for_gstin")

            print("Typing GSTIN...")

            await page.type("#for_gstin", gstin, delay=120)

            await page.keyboard.press("Tab")

            print("Waiting for CAPTCHA...")

            captcha_img = await page.wait_for_selector(
                "#imgCaptcha",
                state="visible",
                timeout=20000
            )

            await page.wait_for_timeout(2000)

            captcha_path = f"{OUTPUT_DIR}/captcha.png"

            await captcha_img.screenshot(path=captcha_path)

            print(f"CAPTCHA saved: {captcha_path}")

            captcha = input("Enter CAPTCHA: ").strip()
            print(f"Entering captcha text: {captcha}")
            await page.wait_for_selector("#fo-captcha", state="visible", timeout=5000)
            await page.fill("#fo-captcha", captcha)
            print("Filled #fo-captcha successfully.")

            await page.wait_for_timeout(1000)

            print("Submitting search...")

            await page.click('button:has-text("SEARCH")')

            print("Waiting for results...")

            await page.wait_for_timeout(10000)

            # SAVE DEBUG FILES
            await page.screenshot(
                path=f"{OUTPUT_DIR}/final_page.png",
                full_page=True
            )

            html = await page.content()

            with open(
                f"{OUTPUT_DIR}/debug.html",
                "w",
                encoding="utf-8"
            ) as f:
                f.write(html)

            # ===============================
            # EXTRACT JSON DATA
            # ===============================

            gst_data = {}

            # Get all visible text blocks
            raw_texts = await page.locator(
                "div, span, p, td, th, label"
            ).all_inner_texts()

            all_text = [
                txt.strip() for txt in raw_texts
                if txt and len(txt.strip()) > 1
            ]

            # Remove duplicates while preserving order
            cleaned = list(dict.fromkeys(all_text))

            # KEY FIELDS
            important_fields = {
                "Legal Name of Business",
                "Trade Name",
                "Effective Date of registration",
                "Constitution of Business",
                "GSTIN / UIN Status",
                "Taxpayer Type",
                "Principal Place of Business",
                "Whether Aadhaar Authenticated?",
                "Whether e-KYC Verified?",
                "Nature Of Core Business Activity",
                "Nature of Business Activities"
            }

            # Extract key-value pairs
            for i in range(len(cleaned) - 1):

                current = cleaned[i]
                nxt = cleaned[i + 1]

                if current in important_fields:
                    gst_data[current] = nxt

            # ===============================
            # TABLE EXTRACTION
            # ===============================

            gst_data["tables"] = await page.evaluate("""() => {
                const tables = Array.from(document.querySelectorAll('table'));
                return tables.map(table => {
                    const rows = Array.from(table.querySelectorAll('tr'));
                    return rows.map(row => {
                        const cols = Array.from(row.querySelectorAll('th, td'));
                        return cols.map(col => col.innerText.trim());
                    }).filter(rowData => rowData.length > 0);
                }).filter(tableData => tableData.length > 0);
            }""")

            # ===============================
            # RAW PAGE TEXT
            # ===============================

            body_text = await page.locator("body").inner_text()

            gst_data["raw_text"] = body_text

            # ===============================
            # SAVE JSON
            # ===============================

            json_path = f"{OUTPUT_DIR}/gst_data.json"

            with open(
                json_path,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    gst_data,
                    f,
                    indent=4,
                    ensure_ascii=False
                )

            print("\n========== JSON DATA ==========\n")

            print(json.dumps(
                gst_data,
                indent=4,
                ensure_ascii=False
            ))

            print("\n===============================\n")

            print("Saved Files:")
            print(f" - {json_path}")
            print(f" - {OUTPUT_DIR}/final_page.png")
            print(f" - {OUTPUT_DIR}/debug.html")

        except Exception as e:

            print("\nERROR OCCURRED:")
            print(str(e))

            try:

                await page.screenshot(
                    path=f"{OUTPUT_DIR}/error.png",
                    full_page=True
                )

                print("Saved error screenshot.")

            except:
                pass

        finally:

            print("\nBrowser kept open for inspection.")
            input("Press ENTER to close browser...")

            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper()),