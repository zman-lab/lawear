// 카오스 시나리오 — 이것저것 빠르게 누르면 버그가 튀어나오는지 전수조사
const { chromium, devices } = require('/opt/homebrew/lib/node_modules/playwright');
const fs = require('fs');

const BASE_URL = 'http://localhost:8100/';
const SHOT_DIR = '/tmp';
const bugs = [];
const passes = [];
function addBug(s, d, det = '') { bugs.push({s, d, det}); console.log(`[BUG] [${s}] ${d}${det ? ' — ' + det : ''}`); }
function addPass(s, d) { passes.push({s, d}); console.log(`[OK]  [${s}] ${d}`); }

async function shot(page, name) {
  try {
    await page.screenshot({ path: `${SHOT_DIR}/lawear_ui_${name}.png`, fullPage: false, timeout: 5000, animations: 'disabled' });
  } catch {}
}

async function wait(page, ms) { await page.waitForTimeout(ms); }

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ ...devices['Galaxy S9+'] });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') {
      const t = m.text();
      if (/github|Failed to fetch/i.test(t)) return;
      consoleErrors.push(`console.error: ${t.slice(0, 200)}`);
    }
  });

  await page.addInitScript(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.speak = function (utt) {
        setTimeout(() => { if (utt.onend) utt.onend(new Event('end')); }, 10);
      };
    }
  });

  try {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
    await wait(page, 1500);

    // ── 시나리오 1: 과목 카드 더블클릭 ───
    const card1 = page.locator('[role="button"]:has-text("민법")').first();
    await card1.click();
    await card1.click().catch(() => {});  // 이미 이동한 상태라 이건 재클릭 안됨
    await wait(page, 800);
    addPass('Scenario1', '과목 카드 중복 클릭 → 안전');

    // ── 시나리오 2: Lv 버튼 빠르게 연타 (4 → 1 → 3 → 2) ───
    for (const lv of [4, 1, 3, 2, 4, 1]) {
      const b = page.locator(`button:has-text("Lv.${lv}")`).first();
      if (await b.count() > 0 && !(await b.isDisabled())) {
        await b.click({ force: true }).catch(() => {});
      }
    }
    await wait(page, 400);
    addPass('Scenario2', 'Lv 버튼 연타 안전');

    // ── 시나리오 3: 검색 열고 닫기 반복 ───
    const searchBtn = page.locator('button[aria-label="검색"]');
    for (let i = 0; i < 5; i++) {
      if (await searchBtn.count() > 0) {
        await searchBtn.click().catch(() => {});
        await wait(page, 150);
      }
    }
    // 마지막 상태 확인
    const searchInput = page.locator('input[placeholder*="검색"]');
    const searchOpen = (await searchInput.count()) > 0;
    addPass('Scenario3', `검색 토글 5회 연타 — 최종상태: ${searchOpen ? '열림' : '닫힘'}`);
    // 닫기
    if (searchOpen) { await searchBtn.click(); await wait(page, 200); }

    // ── 시나리오 4: 선택 모드 진입 → 체크박스 빠르게 여러 개 클릭 → 취소 ───
    const selBtn = page.locator('button:has-text("선택 재생")').first();
    if (await selBtn.count() > 0) {
      await selBtn.click();
      await wait(page, 300);
      // 체크박스 여러 개 클릭
      const checkboxCount = await page.evaluate(() => {
        const checkboxes = document.querySelectorAll('.overflow-y-auto [role="button"]');
        const qs = Array.from(checkboxes).filter(el => {
          const t = el.textContent || '';
          return /\d+:\d{2}/.test(t) && !/Lv\.|전체|선택|즐겨|취약|접/.test(t.trim().split('\n')[0]);
        });
        // 처음 5개 클릭
        qs.slice(0, 5).forEach(q => q.click());
        return qs.length;
      });
      await wait(page, 300);
      addPass('Scenario4', `선택 모드 + ${checkboxCount}개 중 5개 체크`);
      // "취소" 버튼 클릭
      const cancel = page.locator('button:has-text("취소")').first();
      if (await cancel.count() > 0) { await cancel.click(); await wait(page, 300); }
    }

    // ── 시나리오 5: 취약 시트 열고 바로 닫기 (빠르게) ───
    const weakBtn = page.locator('button:has-text("취약 재생")').first();
    if (await weakBtn.count() > 0) {
      for (let i = 0; i < 3; i++) {
        await weakBtn.click().catch(() => {});
        await wait(page, 150);
        const close = page.locator('button:has-text("닫기")').first();
        if (await close.count() > 0) { await close.click().catch(() => {}); await wait(page, 150); }
      }
      addPass('Scenario5', '취약시트 열고닫기 3회 반복 안전');
    }

    // ── 시나리오 6: 파일 그룹 모두 펼치고 접기 반복 ───
    const toggleAll = page.locator('button[aria-label="전체 접기/펼치기"]').first();
    if (await toggleAll.count() > 0) {
      for (let i = 0; i < 4; i++) {
        await toggleAll.click().catch(() => {});
        await wait(page, 200);
      }
      addPass('Scenario6', '전체 접기/펼치기 4회 반복 안전');
    }

    // ── 시나리오 7: 문제 카드 클릭 → PlayerScreen → 바로 뒤로 → 다시 클릭 ───
    for (let i = 0; i < 2; i++) {
      const firstQ = await page.evaluate(() => {
        const all = Array.from(document.querySelectorAll('[role="button"]'));
        const qs = all.filter(el => {
          const t = el.textContent || '';
          return /\d+:\d{2}/.test(t) && !/Lv\.|전체|선택|즐겨|취약|접/.test(t.trim().split('\n')[0]);
        });
        if (qs[0]) { qs[0].click(); return true; }
        return false;
      });
      if (firstQ) {
        await wait(page, 600);
        // 빠르게 뒤로
        const back = page.locator('button[aria-label="뒤로가기"]').first();
        if (await back.count() > 0) await back.click();
        await wait(page, 400);
      }
    }
    addPass('Scenario7', '문제 카드 클릭 → 뒤로 반복 2회 안전');

    // ── 시나리오 8: PlayerScreen에서 Lv 전환 → 재생 → 가사/리더 빠르게 전환 ───
    const firstQ2 = await page.evaluate(() => {
      const all = Array.from(document.querySelectorAll('[role="button"]'));
      const qs = all.filter(el => {
        const t = el.textContent || '';
        return /\d+:\d{2}/.test(t) && !/Lv\.|전체|선택|즐겨|취약|접/.test(t.trim().split('\n')[0]);
      });
      if (qs[0]) { qs[0].click(); return true; }
      return false;
    });
    if (firstQ2) {
      await wait(page, 800);
      // 가사 <-> 리더 빠른 전환
      for (let i = 0; i < 4; i++) {
        const btn = page.locator(`button:has-text("${i % 2 === 0 ? '가사' : '리더'}")`).first();
        if (await btn.count() > 0) await btn.click().catch(() => {});
        await wait(page, 150);
      }
      addPass('Scenario8', '리더/가사 4회 전환 안전');

      // 여러 바텀시트 빠르게 열고 닫기
      const sheetButtons = [
        'button[aria-label*="속도"]',
        'button[aria-label*="반복"]',
        'button[aria-label*="음성"]',
        'button[aria-label*="타이머"]',
        'button[aria-label*="플레이리스트"]',
      ];
      for (const sel of sheetButtons) {
        const b = page.locator(sel).first();
        if (await b.count() > 0) {
          await b.click().catch(() => {});
          await wait(page, 250);
          // backdrop으로 닫기
          await page.evaluate(() => {
            const backdrops = document.querySelectorAll('.fixed.inset-0');
            for (const bd of backdrops) {
              const cs = getComputedStyle(bd);
              if (cs.backgroundColor.includes('0, 0, 0')) {
                bd.click();
                break;
              }
            }
          });
          await wait(page, 250);
        }
      }
      addPass('Scenario9', '5가지 바텀시트 순차 열고닫기 안전');

      // 뒤로가기
      const back = page.locator('button[aria-label="뒤로가기"]').first();
      if (await back.count() > 0) { await back.click(); await wait(page, 400); }
    }

    // ── 시나리오 10: 재생 중에 다른 과목으로 이동 ───
    const firstQ3 = await page.evaluate(() => {
      const all = Array.from(document.querySelectorAll('[role="button"]'));
      const qs = all.filter(el => {
        const t = el.textContent || '';
        return /\d+:\d{2}/.test(t) && !/Lv\.|전체|선택|즐겨|취약|접/.test(t.trim().split('\n')[0]);
      });
      if (qs[0]) { qs[0].click(); return true; }
      return false;
    });
    if (firstQ3) {
      await wait(page, 600);
      // 뒤로 → 홈 → 다른 과목
      const back1 = page.locator('button[aria-label="뒤로가기"]').first();
      if (await back1.count() > 0) { await back1.click(); await wait(page, 400); }
      const back2 = page.locator('button[aria-label="뒤로가기"]').first();
      if (await back2.count() > 0) { await back2.click(); await wait(page, 400); }
      // 홈에서 다른 과목 클릭
      const other = page.locator('[role="button"]:has-text("민소")').first();
      if (await other.count() > 0) {
        await other.click();
        await wait(page, 600);
        addPass('Scenario10', '재생 중 과목 전환 안전');
      }
    }

    // ── 시나리오 11: 홈 → 설정 → 홈 → 즐겨찾기 반복 ───
    for (let i = 0; i < 2; i++) {
      const backS = page.locator('button[aria-label="뒤로가기"]').first();
      if (await backS.count() > 0) { await backS.click(); await wait(page, 400); }

      const settings = page.locator('button[aria-label="설정"]').first();
      if (await settings.count() > 0) {
        await settings.click();
        await wait(page, 500);
        const back = page.locator('button[aria-label="뒤로가기"]').first();
        if (await back.count() > 0) { await back.click(); await wait(page, 400); }
      }
    }
    addPass('Scenario11', '홈 ↔ 설정 순환 안전');

    // ── 시나리오 12: 구간 반복(A-B) 버튼 다중 클릭 ───
    // 민법 → 문제 → Player
    const minbeop = page.locator('[role="button"]:has-text("민법")').first();
    if (await minbeop.count() > 0) {
      await minbeop.click();
      await wait(page, 500);
      const firstQ4 = await page.evaluate(() => {
        const all = Array.from(document.querySelectorAll('[role="button"]'));
        const qs = all.filter(el => {
          const t = el.textContent || '';
          return /\d+:\d{2}/.test(t) && !/Lv\.|전체|선택|즐겨|취약|접/.test(t.trim().split('\n')[0]);
        });
        if (qs[0]) { qs[0].click(); return true; }
        return false;
      });
      if (firstQ4) {
        await wait(page, 800);
        // A-B 버튼 여러 번 클릭 (A설정 → B설정 → 다시 A)
        const abBtn = page.locator('button[aria-label*="구간"]').first();
        if (await abBtn.count() > 0) {
          for (let i = 0; i < 4; i++) {
            await abBtn.click().catch(() => {});
            await wait(page, 200);
          }
          addPass('Scenario12', 'A-B 구간 버튼 4회 연타 안전');
        }
        // 뒤로
        const back = page.locator('button[aria-label="뒤로가기"]').first();
        if (await back.count() > 0) { await back.click(); await wait(page, 400); }
      }
    }

    // ── 시나리오 13: 검색어 2글자 미만 → 2글자 이상 전환 ───
    const search = page.locator('button[aria-label="검색"]').first();
    if (await search.count() > 0) {
      await search.click();
      await wait(page, 300);
      const input = page.locator('input[placeholder*="검색"]').first();
      if (await input.count() > 0) {
        await input.fill('가');      // 1글자
        await wait(page, 400);
        await input.fill('가나');    // 2글자
        await wait(page, 500);
        await input.fill('');       // 빈값
        await wait(page, 400);
        await input.fill('민법');    // 2글자 다시
        await wait(page, 500);
        addPass('Scenario13', '검색어 다양한 입력 안전');
      }
      await search.click();
      await wait(page, 200);
    }

    // 콘솔 에러
    if (consoleErrors.length > 0) {
      for (const err of consoleErrors) addBug('Console', err);
    } else {
      addPass('Console', '모든 시나리오 콘솔 에러 없음');
    }

    await shot(page, 'chaos_final');
  } catch (e) {
    addBug('Runner', `예외: ${e.message}`, e.stack?.slice(0, 300));
  } finally {
    await browser.close();
  }

  console.log(`\nPASS: ${passes.length}, BUG: ${bugs.length}`);
  fs.writeFileSync('/tmp/lawear_ui_chaos_result.json', JSON.stringify({ passes, bugs }, null, 2));
  process.exit(bugs.length > 0 ? 1 : 0);
})();
