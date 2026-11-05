"""Reproduce candidate playback in the installed Windows Firefox."""
import json
import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


opts = Options()
opts.binary_location = r'C:\Program Files\Mozilla Firefox\firefox.exe'
if os.getenv('FIREFOX_HEADLESS', '1') != '0':
    opts.add_argument('-headless')
opts.add_argument('-no-remote')
driver = webdriver.Firefox(options=opts, service=Service(log_output='research/geckodriver.log'))
driver.set_window_size(1400, 1000)
if os.getenv('FIREFOX_HEADLESS', '1') == '0':
    driver.set_window_position(-1800, 0)
driver.set_script_timeout(70000)
try:
    driver.get('http://127.0.0.1:8501/')
    wait = WebDriverWait(driver, 35)
    combo = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, '[role="combobox"][aria-label="Selecione um job"]'))
    print('COMBO', combo.get_attribute('outerHTML')[:500], flush=True)
    prefix = os.getenv('JOB_PREFIX', '2fc2af3e')
    if prefix not in combo.get_attribute('value'):
        combo.click()
        combo.send_keys(prefix)
        option = wait.until(lambda d: next((o for o in d.find_elements(By.CSS_SELECTOR, '[role="option"]') if prefix in o.text), None))
        option.click()
    wait.until(lambda d: len(d.find_elements(By.TAG_NAME, 'video')) == 3)
    time.sleep(2)
    sources = driver.execute_script('return [...document.querySelectorAll("video")].map(v => v.currentSrc || v.src)')
    print('SOURCES', json.dumps(sources), flush=True)
    assert len(sources) == 3 and all(src.endswith('.webm') for src in sources), sources
    for index in range(3):
        result = driver.execute_async_script('''
            const index = arguments[0], done = arguments[arguments.length - 1];
            const v = document.querySelectorAll('video')[index];
            v.muted = true;
            v.playbackRate = arguments[1];
            let playError = null;
            const events = [];
            for (const name of ['loadstart','stalled','suspend','abort','error','ended','waiting','emptied'])
                v.addEventListener(name, () => events.push([name, Math.round(v.currentTime*10)/10]));
            const finish = outcome => done({index, outcome, playError, currentTime:v.currentTime, duration:v.duration,
                readyState:v.readyState, networkState:v.networkState,
                error:v.error && {code:v.error.code, message:v.error.message},
                connected:document.contains(v), events,
                canPlay:v.canPlayType('video/webm; codecs="vp8, opus"')});
            v.addEventListener('ended', () => finish('ended'), {once:true});
            v.addEventListener('error', () => finish('error'), {once:true});
            setTimeout(() => finish('timeout'), 60000);
            v.play().catch(e => {playError = String(e); finish('play-rejected')});
        ''', index, float(os.getenv('PLAYBACK_RATE', '1')))
        print('PLAYBACK', json.dumps(result), flush=True)
        assert result['outcome'] == 'ended' and result['error'] is None, result
finally:
    driver.quit()
