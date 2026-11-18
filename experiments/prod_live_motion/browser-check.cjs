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
    await page.waitForFunction(() => phase === 'detecting_hand' && cv.readyState >= 2 && !cv.paused, null, { timeout: 60000 });
    assert.equal(await page.locator('.motion-control select').inputValue(), mode);
    // Inspect the target integration independently of gesture classification.
    const opening = await page.evaluate(async () => {
      selectedHand = 'right';
      await genSequence();
      startRealChallenge();
      if (motionMode === 'recorded') return null;
      const pixel = () => [...targetFrame.getContext('2d').getImageData(258, 233, 1, 1).data];
      const firstPixel = pixel();
      const start = liveTarget.previewStartedAt;
      const during = { active: targetPreviewActive(), firstPixel, initialOpacity: liveTarget.drawnOpacity };
      const initialMode = motionMode;
      modeSelect.value = motionMode === '3d' ? '2d' : '3d';
      modeSelect.dispatchEvent(new Event('change'));
      during.startStable = liveTarget.previewStartedAt === start;
      modeSelect.value = initialMode;
      modeSelect.dispatchEvent(new Event('change'));
      await new Promise(resolve => {
        const waitForPaint = () => {
          if (!targetPreviewActive()) return resolve();
          const elapsed = performance.now() - start;
          const opacity = liveTarget.drawnOpacity;
          if (elapsed >= 200 && elapsed < 500) during.holdOpacity = opacity;
          if (!during.fadePixel && opacity > .2 && opacity < .8) during.fadePixel = pixel();
          requestAnimationFrame(waitForPaint);
        };
        requestAnimationFrame(waitForPaint);
      });
      return { ...during, elapsed: performance.now() - start, maskedPixel: pixel(), time: liveTime() };
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
    const masked = [7, 11, 16, 255];
    assert.ok(opening.active && opening.startStable);
    assert.equal(opening.initialOpacity, 0);
    assert.equal(opening.holdOpacity, 0);
    assert.notDeepEqual(opening.firstPixel, masked);
    assert.ok(opening.fadePixel);
    assert.notDeepEqual(opening.fadePixel, masked);
    assert.notDeepEqual(opening.fadePixel, opening.firstPixel);
    assert.deepEqual(opening.maskedPixel, masked);
    assert.ok(opening.elapsed >= 1000);
    assert.equal(opening.time, 0);
    assert.match(before.clip, /^live-/);
    assert.ok(!requests.some(url => /pool_manifest\.json|\.mp4|landmarks\.json/.test(url)));
    const otherMode = mode === '3d' ? '2d' : '3d';
    await page.locator('.motion-control select').selectOption(otherMode);
    const changed = await page.evaluate(() => ({
      image: targetFrame.toDataURL(), clip: keyframes[0].clip.clip_id, time: liveTime(), index: kfIdx,
      reports: [...presentedModes],
    }));
    assert.deepEqual({ clip: changed.clip, time: changed.time, index: changed.index }, { clip: before.clip, time: 0, index: 0 });
    assert.notEqual(changed.image, before.image);
    assert.deepEqual(changed.reports, [mode, otherMode]);
    await page.locator('.motion-control select').selectOption(mode);
    const restored = await page.evaluate(() => ({
      mode: liveTarget.drawnMode, clip: liveTarget.keyframe.clip.clip_id, time: liveTime(),
      pixel: [...targetFrame.getContext('2d').getImageData(258, 233, 1, 1).data],
    }));
    assert.deepEqual(restored, { mode, clip: before.clip, time: 0, pixel: masked });
    if (process.env.CAPTCHA_SCREENSHOTS) {
      await page.locator('#targetFrame').screenshot({ path: process.env.CAPTCHA_SCREENSHOTS + '-' + mode + '.png' });
    }
    await page.evaluate(() => beginNextTransition());
    await page.waitForFunction(() => videoPlaying && liveTime() > .35);
    await page.locator('#swapHandViews').click();
    await page.waitForFunction(() => !videoPlaying && liveTime() === keyframes[1].time);
    const after = await page.evaluate(() => ({
      image: targetFrame.toDataURL(), clip: keyframes[kfIdx].clip.clip_id,
      maskPixels: [[258, 140], [258, 326], [165, 233], [351, 233], [258, 134], [258, 332]]
        .map(([x, y]) => [...targetFrame.getContext('2d').getImageData(x, y, 1, 1).data]),
    }));
    assert.equal(after.clip, before.clip);
    assert.notEqual(after.image, before.image);
    assert.deepEqual(after.maskPixels.slice(0, 4), Array(4).fill(masked));
    for (const pixel of after.maskPixels.slice(4)) assert.notDeepEqual(pixel, masked);
    const nextClip = await page.evaluate(() => {
      const nextIndex = keyframes.findIndex(kf => kf.clip !== keyframes[0].clip);
      showKeyframeImage(nextIndex);
      return { preview: targetPreviewActive(),
        pixel: [...targetFrame.getContext('2d').getImageData(258, 233, 1, 1).data] };
    });
    assert.deepEqual(nextClip, { preview: false, pixel: masked });
    assert.deepEqual(errors, []);
    console.log(`PASS ${mode}: V5 capture, ${Math.round(opening.elapsed)} ms opening preview with fade, then masked playback`);
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
