// Playwright mobile emulation test for lawear web
// Galaxy S9+ / 실제 흐름: Home → ListScreen(과목, Lv.1~4 토글) → PlayerScreen(재생)
const { chromium, devices } = require('/opt/homebrew/lib/node_modules/playwright');
const fs = require('fs');

const PORT = 8100;
const BASE_URL = `http://localhost:${PORT}/`;
const SCREENSHOT_DIR = '/tmp';
const results = [];
const issues = [];

function record(name, pass, detail = '') {
  const status = pass ? 'PASS' : 'FAIL';
  results.push({ name, status, detail });
  if (!pass) issues.push(`${name}: ${detail}`);
  console.log(`[${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

async function shot(page, name) {
  const path = `${SCREENSHOT_DIR}/lawear_${name}.png`;
  try {
    // viewport only (fullPage 금지 — TTS 관련 미디어로 fonts-loaded 대기가 길어짐)
    await page.screenshot({ path, fullPage: false, timeout: 10000, animations: 'disabled' });
    console.log(`[SHOT] ${path}`);
  } catch (e) {
    console.log(`[SHOT_ERR] ${name}: ${e.message.slice(0, 80)}`);
  }
  return path;
}

async function wait(page, ms) { await page.waitForTimeout(ms); }

// 과목 카드 클릭 (role=button, shortName 또는 name 부분 매칭)
async function clickSubject(page, keyword) {
  // 과목 카드는 <div role="button">
  const card = page.locator(`[role="button"]:has-text("${keyword}")`).first();
  const count = await card.count();
  if (count === 0) return false;
  await card.click();
  return true;
}

// Lv 버튼 클릭 (ListScreen 상단)
async function clickLv(page, lv) {
  // 'Lv.1' / 'Lv.2' / 'Lv.3' / 'Lv.4' 짧은 라벨 기준
  const btn = page.locator(`button:has-text("Lv.${lv}")`).first();
  if (await btn.count() === 0) return false;
  const disabled = await btn.isDisabled();
  if (disabled) {
    console.log(`  Lv.${lv} 비활성(준비중)`);
    return false;
  }
  await btn.click();
  return true;
}

// 문제 카드 클릭 — ListScreen의 문제는 <div role="button"> 이며, duration(0:MM) 포함
async function clickFirstQuestion(page) {
  const cards = await page.locator('[role="button"]').all();
  for (const c of cards) {
    const text = (await c.textContent()) || '';
    const trimmed = text.trim().replace(/\s+/g, ' ');
    // duration 패턴 포함 + Lv/전체 버튼/설정 같은 컨트롤 아님
    if (/\d+:\d{2}/.test(trimmed) && trimmed.length > 5 && trimmed.length < 300 &&
        !/Lv\./i.test(trimmed) && !/^전체|^즐겨찾기|^설정|과목 전체|선택 모드/.test(trimmed)) {
      try {
        await c.scrollIntoViewIfNeeded();
        await c.click({ timeout: 5000 });
        return trimmed.slice(0, 60);
      } catch (e) {
        // 다음 카드 시도
      }
    }
  }
  return null;
}

(async () => {
  const galaxy = devices['Galaxy S9+'];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ ...galaxy });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      // 무시할 패턴 — update 체크 실패 등 환경 에러
      if (/github\.com|Failed to fetch/i.test(text)) return;
      consoleErrors.push(`console.error: ${text.slice(0, 200)}`);
    }
  });

  // TTS(SpeechSynthesis)는 Playwright 환경에서 실제 재생되지 않지만 stub 처리
  await page.addInitScript(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      const orig = window.speechSynthesis.speak;
      window.speechSynthesis.speak = function (utt) {
        // utterance의 onend를 즉시 호출하여 재생 중 상태 방지
        setTimeout(() => {
          if (utt.onend) utt.onend(new Event('end'));
        }, 10);
      };
    }
  });

  // 앱 내 뒤로가기 클릭 helper
  async function goBack() {
    const back = page.locator('button[aria-label*="뒤로"]').first();
    if (await back.count() > 0) {
      await back.click();
      await page.waitForTimeout(500);
      return true;
    }
    return false;
  }

  try {
    console.log(`\n=== 1. 홈 화면 ===`);
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
    await wait(page, 1500);
    await shot(page, '01_home');
    const homeText = await page.textContent('body');
    record('home_loaded', /민법|민소|형소|형법/.test(homeText || ''), `textLen=${homeText?.length}`);

    // ── 민법 과목 테스트 ────────────────────────────────────
    console.log(`\n=== 2. 민법 과목 진입 ===`);
    const minbeopOk = await clickSubject(page, '민법');
    record('subject_minbeop_click', minbeopOk);
    if (minbeopOk) {
      await wait(page, 800);
      await shot(page, '02_list_minbeop');

      // Lv.1 (기본) 표시 확인
      const lv1Btn = page.locator('button:has-text("Lv.1")').first();
      record('lv1_visible_on_list', await lv1Btn.count() > 0);

      // Lv.1~4 각각 클릭하며 스크린샷
      console.log(`\n=== 3. 민법 ListScreen Lv.1~4 전환 ===`);
      for (const lv of [1, 2, 3, 4]) {
        const ok = await clickLv(page, lv);
        if (ok) {
          await wait(page, 400);
          await shot(page, `03_minbeop_list_lv${lv}`);
          record(`minbeop_list_lv${lv}`, true);
        } else {
          record(`minbeop_list_lv${lv}`, false, '버튼 없음 또는 비활성');
        }
      }

      // Lv.1로 돌아가서 문제 클릭 → Player 진입
      console.log(`\n=== 4. 민법 문제 선택 → Player 진입 ===`);
      await clickLv(page, 1);
      await wait(page, 300);

      // 혹시 파일 그룹이 접혀있으면 펼치기
      const expandAll = page.locator('button:has-text("전체"), button[aria-label*="펼치"]').first();
      if (await expandAll.count() > 0) {
        try { await expandAll.click(); await wait(page, 300); } catch {}
      }

      const qClicked = await clickFirstQuestion(page);
      record('minbeop_question_click', !!qClicked, qClicked || '');
      if (qClicked) {
        await wait(page, 1500);
        await shot(page, '04_minbeop_player');

        // Player 화면에 텍스트 표시 확인
        const playerText = await page.textContent('body');
        record('minbeop_player_has_text', !!playerText && playerText.length > 200, `len=${playerText?.length}`);

        // 뒤로 가기 (상단 좌측)
        const backBtn = page.locator('button[aria-label*="뒤로"], button[aria-label*="back"]').first();
        if (await backBtn.count() > 0) {
          await backBtn.click();
          await wait(page, 500);
        } else {
          // fallback: 최상단 첫 버튼
          await page.locator('button').first().click().catch(() => {});
          await wait(page, 500);
        }
      }

      // 홈으로 돌아가기
      const back2 = page.locator('button[aria-label*="뒤로"], button[aria-label*="back"]').first();
      if (await back2.count() > 0) {
        await back2.click();
        await wait(page, 500);
      }
    }

    // ── 민소 과목 테스트 ────────────────────────────────────
    console.log(`\n=== 5. 민소 과목 진입 ===`);
    // 홈으로 복귀: 현재 화면에서 back 버튼 연달아 눌러 홈까지
    for (let i = 0; i < 5; i++) {
      const ok = await goBack();
      if (!ok) break;
    }
    await wait(page, 600);

    const minsoOk = await clickSubject(page, '민소');
    record('subject_minso_click', minsoOk);
    if (minsoOk) {
      await wait(page, 800);
      await shot(page, '05_list_minso');

      // Lv.2 클릭
      const lv2Ok = await clickLv(page, 2);
      if (lv2Ok) {
        await wait(page, 400);
        await shot(page, '06_minso_list_lv2');
        record('minso_list_lv2', true);
      } else {
        record('minso_list_lv2', false);
      }

      // 문제 클릭
      await clickLv(page, 1);
      await wait(page, 300);
      const minsoQ = await clickFirstQuestion(page);
      record('minso_question_click', !!minsoQ, minsoQ || '');
      if (minsoQ) {
        await wait(page, 1500);
        await shot(page, '07_minso_player');
      }
    }

    // ── 형소 과목 테스트 ────────────────────────────────────
    console.log(`\n=== 6. 형소 과목 진입 ===`);
    for (let i = 0; i < 5; i++) {
      const ok = await goBack();
      if (!ok) break;
    }
    await wait(page, 600);

    const hyungsoOk = await clickSubject(page, '형소');
    record('subject_hyungso_click', hyungsoOk);
    if (hyungsoOk) {
      await wait(page, 800);
      await shot(page, '08_list_hyungso');

      const lv3Ok = await clickLv(page, 3);
      if (lv3Ok) {
        await wait(page, 400);
        await shot(page, '09_hyungso_list_lv3');
        record('hyungso_list_lv3', true);
      } else {
        record('hyungso_list_lv3', false);
      }

      await clickLv(page, 1);
      await wait(page, 300);
      const hq = await clickFirstQuestion(page);
      record('hyungso_question_click', !!hq, hq || '');
      if (hq) {
        await wait(page, 1500);
        await shot(page, '10_hyungso_player');
      }
    }

    // ── UI 깨짐 체크 ─────────────────────────────────────────
    console.log(`\n=== 7. UI 깨짐 (가로 오버플로) ===`);
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      const body = document.body;
      const docWidth = Math.max(body.scrollWidth, doc.scrollWidth);
      const viewWidth = window.innerWidth;
      return { docWidth, viewWidth, overflow: docWidth > viewWidth + 5 };
    });
    record('no_horizontal_overflow', !overflow.overflow, `docW=${overflow.docWidth} vw=${overflow.viewWidth}`);

    // ── PlayerBar 렌더링은 재생 중일 때만 보이므로 스킵 ────

  } catch (e) {
    console.error(`[FATAL] ${e.message}`);
    console.error(e.stack);
    issues.push(`FATAL: ${e.message}`);
    try { await shot(page, '99_fatal'); } catch {}
  } finally {
    if (consoleErrors.length > 0) {
      record('no_console_errors', false, `${consoleErrors.length}개: ${consoleErrors.slice(0, 3).join(' | ').slice(0, 300)}`);
    } else {
      record('no_console_errors', true);
    }

    await browser.close();

    const passCount = results.filter(r => r.status === 'PASS').length;
    const failCount = results.filter(r => r.status === 'FAIL').length;

    console.log(`\n\n==========================================`);
    console.log(`PASS: ${passCount}, FAIL: ${failCount}`);
    console.log(`==========================================`);

    fs.writeFileSync('/tmp/lawear_test_report.json', JSON.stringify({ results, issues, consoleErrors }, null, 2));
    console.log(`리포트: /tmp/lawear_test_report.json`);

    process.exit(failCount > 0 ? 1 : 0);
  }
})();
