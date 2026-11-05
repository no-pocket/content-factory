"""Inspect the real Streamlit video elements in a headless Chromium session."""
import asyncio
import json
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path='/app/renderer/node_modules/.remotion/chrome-headless-shell/linux64/chrome-headless-shell-linux64/chrome-headless-shell',
            headless=True, args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required'])
        page = await browser.new_page()
        page.on('console', lambda m: print('CONSOLE', m.type, m.text[:300], flush=True) if m.type == 'error' else None)
        page.on('requestfailed', lambda r: print('FAILED', r.url, r.failure, flush=True))
        page.on('response', lambda r: print('MEDIA', r.status, r.url, flush=True) if '/media/' in r.url else None)
        await page.goto('http://ui:8501/', wait_until='domcontentloaded')
        await page.get_by_role('combobox', name='Selecione um job').wait_for(timeout=30000)
        print('TITLE', await page.title(), flush=True)
        print('COMBOS', await page.get_by_role('combobox').all_text_contents(), flush=True)
        print('VIDEOS_BEFORE', await page.locator('video').count(), flush=True)
        await page.screenshot(path='/tmp/browser_before.png', full_page=True)
        combo = page.get_by_role('combobox', name='Selecione um job')
        await combo.click()
        print('POPOVER', await page.locator('[data-baseweb="popover"]').all_text_contents(), flush=True)
        await combo.fill('2fc2af3e')
        await page.wait_for_timeout(500)
        print('OPTIONS', await page.get_by_role('option').all_text_contents(), flush=True)
        await page.screenshot(path='/tmp/browser_options.png', full_page=True)
        await page.get_by_role('option').filter(has_text='2fc2af3e').click()
        await page.wait_for_timeout(3000)
        print('VIDEOS_AFTER', await page.locator('video').count(), flush=True)
        print('SOURCES', json.dumps(await page.locator('video').evaluate_all('(els) => els.map(e => ({src: e.currentSrc || e.src,html:e.outerHTML.slice(0,400)}))')), flush=True)
        for index in range(3):
            result = await page.evaluate('''async (index) => {
                const v = document.querySelectorAll('video')[index];
                v.muted = true;
                v.playbackRate = 8;
                let playError = null;
                try { await v.play(); } catch (e) { playError = String(e); }
                const outcome = await Promise.race([
                    new Promise(resolve => v.addEventListener('ended', () => resolve('ended'), {once:true})),
                    new Promise(resolve => v.addEventListener('error', () => resolve('error'), {once:true})),
                    new Promise(resolve => setTimeout(() => resolve('timeout'), 15000)),
                ]);
                return {index, outcome, playError, currentTime:v.currentTime, duration:v.duration,
                    readyState:v.readyState, networkState:v.networkState,
                    error:v.error && {code:v.error.code, message:v.error.message}};
            }''', index)
            print('PLAYBACK', json.dumps(result), flush=True)
        await page.screenshot(path='/tmp/browser_after.png', full_page=True)
        await browser.close()


asyncio.run(main())
