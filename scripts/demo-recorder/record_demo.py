#!/usr/bin/env python3
"""Record the docs/index.html demo animation (one full 6-tab cycle) as webm."""
from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

from playwright.async_api import async_playwright

REPO = Path(__file__).resolve().parents[2]
INDEX = REPO / "docs" / "index.html"
OUT_DIR = Path("/tmp/organon-demo-rec")
FINAL = Path("/tmp/organon-demo.webm")

# Tab strip + terminal are about 1000px wide on desktop; give it room.
VIEWPORT = {"width": 1240, "height": 780}
SPEED_FACTOR = 0.35  # 1.0 = real time; lower = faster playback


async def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=2,
            record_video_dir=str(OUT_DIR),
            record_video_size=VIEWPORT,
        )

        # Speed up setTimeout-based delays proportionally before any page JS runs.
        await context.add_init_script(
            f"""
            (() => {{
              const factor = {SPEED_FACTOR};
              const orig = window.setTimeout;
              window.setTimeout = function(fn, ms, ...rest) {{
                const scaled = typeof ms === 'number' ? ms * factor : ms;
                return orig(fn, scaled, ...rest);
              }};
            }})();
            """
        )

        # Track active-tab changes so we can detect one complete cycle.
        await context.add_init_script(
            """
            window.__tabHistory = [];
            window.addEventListener('DOMContentLoaded', () => {
              // Seed with the tab that starts with the 'active' class in HTML,
              // since no mutation fires for the initial state.
              const seed = document.querySelector('.demo-tab.active');
              if (seed) window.__tabHistory.push(seed.dataset.script);
              const observer = new MutationObserver(() => {
                const active = document.querySelector('.demo-tab.active');
                if (!active) return;
                const key = active.dataset.script;
                const last = window.__tabHistory[window.__tabHistory.length - 1];
                if (key !== last) window.__tabHistory.push(key);
              });
              document.querySelectorAll('.demo-tab').forEach((t) => {
                observer.observe(t, { attributes: true, attributeFilter: ['class'] });
              });
            });
            """
        )

        page = await context.new_page()
        await page.goto(INDEX.as_uri())

        await page.wait_for_selector("#term-body", state="attached")

        # Scroll so the tabs sit just below the top nav (~70px) and the terminal
        # is fully visible below. The IntersectionObserver on #term-body fires
        # as soon as any part is in the viewport.
        await page.evaluate(
            """() => {
              const tabs = document.querySelector('.demo-tabs');
              const r = tabs.getBoundingClientRect();
              window.scrollBy(0, r.top - 20);
            }"""
        )
        await asyncio.sleep(0.5)

        # Sanity: the tabs should be visible.
        tabs_box = await page.evaluate(
            """() => {
              const r = document.querySelector('.demo-tabs').getBoundingClientRect();
              return { top: r.top, bottom: r.bottom };
            }"""
        )
        print(f"tabs box: {tabs_box}", file=sys.stderr)

        # Wait for the animation to start (first entry in tabHistory).
        for _ in range(40):
            started = await page.evaluate("window.__tabHistory.length > 0")
            if started:
                break
            await asyncio.sleep(0.25)

        # One complete cycle = 'literature' appears twice in the history
        # (first activation + loop-back after publish).
        elapsed = 0.0
        step = 0.5
        timeout = 180.0
        cycle_done = False
        hist = []
        while elapsed < timeout:
            hist = await page.evaluate("window.__tabHistory")
            if hist.count("literature") >= 2 and "publish" in hist:
                cycle_done = True
                break
            await asyncio.sleep(step)
            elapsed += step

        if cycle_done:
            # Let literature render ~1.5s into its second run for a clean loop seam.
            await asyncio.sleep(1.5)
        else:
            print(f"WARN: cycle not detected in {timeout}s; tab history: {hist}", file=sys.stderr)

        await context.close()
        await browser.close()

    webms = list(OUT_DIR.glob("*.webm"))
    if not webms:
        print("ERROR: no video produced", file=sys.stderr)
        sys.exit(1)
    shutil.move(str(webms[0]), FINAL)
    print(f"Recorded: {FINAL}")
    print(f"Total elapsed wait: {elapsed:.1f}s; cycle_done={cycle_done}")


if __name__ == "__main__":
    asyncio.run(main())
