const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_CORE || '../../../qa/node_modules/playwright-core');
const base = process.env.CAPTCHA_URL || 'http://127.0.0.1:18872/experiments/prod_live_motion/';

async function check(browser, mode) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [], requests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('requestfailed', request => errors.push(request.url() + ' ' + request.failure()?.errorText));
  page.on('request', request => requests.push(request.url()));
  try {
    await page.addInitScript(() => {
      navigator.mediaDevices.getUserMedia = async () => {
        const canvas = document.createElement('canvas');
        canvas.width = 640;
        canvas.height = 480;
        const context = canvas.getContext('2d');
        const draw = () => {
          context.fillStyle = '#223344';
          context.fillRect(0, 0, canvas.width, canvas.height);
          requestAnimationFrame(draw);
        };
        draw();
        return canvas.captureStream(30);
      };
    });
    await page.goto(mode === '3d' ? base : base + '?motion=' + mode);
    await page.waitForFunction(() => phase === 'detecting_hand' && cv.readyState >= 2, null, { timeout: 60000 });
    assert.equal(await page.locator('.motion-control select').inputValue(), mode);
    // Inspect the target integration independently of gesture classification.
    await page.evaluate(async () => {
      selectedHand = 'right';
      await genSequence();
      startRealChallenge();
    });
    await page.waitForFunction(() => targetFrame.width > 0 && !targetPending);
    const before = await page.evaluate(() => ({
      image: targetFrame.toDataURL(), count: keyframes.length,
      clip: keyframes[0].clip.clip_id, reached: phase === 'matching',
      scoreFns: [computeScores, angleErr].map(f => f.toString()),
    }));
    assert.ok(before.reached && before.count > 2);
    if (mode === 'recorded') {
      assert.ok(requests.some(url => url.endsWith('.mp4')));
      return before.scoreFns;
    }
    assert.match(before.clip, new RegExp('^live-' + mode));
    assert.ok(!requests.some(url => /pool_manifest\.json|\.mp4|landmarks\.json/.test(url)));
    await page.evaluate(() => beginNextTransition());
    await page.waitForFunction(() => videoPlaying && liveTime() > .35);
    await page.locator('#swapHandViews').click();
    await page.waitForFunction(() => !videoPlaying && liveTime() === keyframes[1].time);
    const after = await page.evaluate(() => ({
      image: targetFrame.toDataURL(), clip: keyframes[kfIdx].clip.clip_id,
      color: [...targetFrame.getContext('2d').getImageData(258, 180, 1, 1).data],
    }));
    assert.equal(after.clip, before.clip);
    assert.notEqual(after.image, before.image);
    assert.deepEqual(after.color, [7, 11, 16, 255]);
    assert.deepEqual(errors, []);
    console.log(`PASS ${mode}: initialized capture, generated masked frames, played and held the next pose`);
    return before.scoreFns;
  } catch (error) {
    console.error(mode, errors, await page.locator('#statusBar').textContent());
    throw error;
  } finally {
    await page.close();
  }
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
  });
  try {
    const baseline = await check(browser, 'recorded');
    assert.deepEqual(await check(browser, '3d'), baseline);
    assert.deepEqual(await check(browser, '2d'), baseline);
    console.log('PASS recorded playback and matching/scoring parity across the three modes');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
