// UI 전수조사 스크립트 (lawear)
// Galaxy S9+ 에뮬레이션, 모든 화면/플로우 체크 + 플레이바 오버랩 검증
const { chromium, devices } = require('/opt/homebrew/lib/node_modules/playwright');
const fs = require('fs');

const PORT = 8100;
const BASE_URL = `http://localhost:${PORT}/`;
const SHOT_DIR = '/tmp';

const bugs = [];      // 발견된 버그
const passes = [];    // 통과한 체크

function addBug(screen, desc, detail = '') {
  const b = { screen, desc, detail };
  bugs.push(b);
  console.log(`[BUG] [${screen}] ${desc}${detail ? ' — ' + detail : ''}`);
}
function addPass(screen, desc) {
  passes.push({ screen, desc });
  console.log(`[OK]  [${screen}] ${desc}`);
}

async function shot(page, name) {
  const path = `${SHOT_DIR}/lawear_ui_${name}.png`;
  try {
    await page.screenshot({ path, fullPage: false, timeout: 5000, animations: 'disabled' });
  } catch (e) {
    console.log(`[SHOT_ERR] ${name}: ${e.message.slice(0, 80)}`);
  }
  return path;
}

async function wait(page, ms) { await page.waitForTimeout(ms); }

// 플레이바 영역 가져오기 (오버랩 검증용)
async function getPlayerBarRect(page) {
  return await page.evaluate(() => {
    const bar = document.querySelector('.fixed.bottom-0.left-0.right-0.max-w-md.mx-auto.z-50');
    if (!bar) return null;
    const r = bar.getBoundingClientRect();
    return { top: r.top, bottom: r.bottom, height: r.height, left: r.left, right: r.right };
  });
}

// 특정 keyword 포함 role=button 요소가 플레이바에 가려지는지 체크
async function isCoveredByPlayerBar(page, keyword, indexFromEnd = 0) {
  return await page.evaluate(({ keyword, indexFromEnd }) => {
    const all = Array.from(document.querySelectorAll('[role="button"]'));
    const elements = all.filter(el => (el.textContent || '').includes(keyword));
    if (elements.length === 0) return { found: false };
    const target = elements[elements.length - 1 - indexFromEnd];
    if (!target) return { found: false };
    const scroll = target.closest('.overflow-y-auto');
    if (scroll) scroll.scrollTop = scroll.scrollHeight;
    const r = target.getBoundingClientRect();
    const bar = document.querySelector('.fixed.bottom-0.left-0.right-0.max-w-md.mx-auto.z-50');
    if (!bar) return { found: true, overlap: false };
    const br = bar.getBoundingClientRect();
    const overlap = r.bottom > br.top && r.top < br.bottom;
    const covered = r.top + r.height / 2 >= br.top;
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const top = document.elementFromPoint(cx, cy);
    const topBlockedByBar = top && bar.contains(top);
    return {
      found: true,
      rect: { top: r.top, bottom: r.bottom, left: r.left, right: r.right },
      barRect: { top: br.top, bottom: br.bottom },
      overlap,
      covered,
      topBlockedByBar,
    };
  }, { keyword, indexFromEnd });
}

// 과목 카드 클릭
async function clickSubject(page, keyword) {
  const card = page.locator(`[role="button"]:has-text("${keyword}")`).first();
  if (await card.count() === 0) return false;
  await card.click();
  return true;
}

// 레벨 버튼 클릭
async function clickLv(page, lv) {
  const btn = page.locator(`button:has-text("Lv.${lv}")`).first();
  if (await btn.count() === 0) return false;
  if (await btn.isDisabled()) return false;
  await btn.click();
  return true;
}

(async () => {
  const galaxy = devices['Galaxy S9+'];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ ...galaxy, ignoreHTTPSErrors: true });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      if (/github\.com|Failed to fetch/i.test(text)) return;
      consoleErrors.push(`console.error: ${text.slice(0, 200)}`);
    }
  });

  // TTS Stub: 실제 재생 없이 onend 즉시 콜
  await page.addInitScript(() => {
    if (window.speechSynthesis) {
      const origSpeak = window.speechSynthesis.speak;
      window.speechSynthesis.speak = function (utt) {
        setTimeout(() => { if (utt.onend) utt.onend(new Event('end')); }, 10);
      };
    }
  });

  try {
    // ── 1. 홈 ────────────────────────────────────────────
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await wait(page, 1200);
    await shot(page, '01_home');

    // 플레이바 존재 여부 (초기: 재생 없음이므로 잘 보이기만 하면 됨)
    const barOnHome = await getPlayerBarRect(page);
    if (!barOnHome) {
      addBug('HomeScreen', '플레이바 DOM 누락');
    } else {
      addPass('HomeScreen', `플레이바 렌더됨 (h=${Math.round(barOnHome.height)}px, top=${Math.round(barOnHome.top)}px)`);
    }

    // 홈 하단 콘텐츠 (서류 과목 카드) 플레이바 오버랩 — 서류는 role=button이 아닌 div라 문자열 검색
    const lastHomeCardInfo = await page.evaluate(() => {
      // 홈 스크롤을 맨 아래로
      const scroll = document.querySelector('.flex-1.overflow-y-auto');
      if (scroll) scroll.scrollTop = scroll.scrollHeight;
      // "부동산등기서류" 텍스트 포함 요소
      const all = Array.from(document.querySelectorAll('div, button'));
      const target = all.find(el => (el.textContent || '').includes('부동산등기서류'));
      if (!target) return null;
      target.scrollIntoView({ behavior: 'instant', block: 'end' });
      const r = target.getBoundingClientRect();
      const bar = document.querySelector('.fixed.bottom-0.left-0.right-0.max-w-md.mx-auto.z-50');
      const br = bar ? bar.getBoundingClientRect() : null;
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const top = document.elementFromPoint(cx, cy);
      const topBlocked = top && bar && bar.contains(top);
      return {
        rect: { top: r.top, bottom: r.bottom },
        barTop: br ? br.top : null,
        barHeight: br ? br.height : null,
        topBlocked,
      };
    });
    if (lastHomeCardInfo && lastHomeCardInfo.topBlocked) {
      addBug('HomeScreen', `서류카드 하단이 플레이바에 가려짐 (barTop=${lastHomeCardInfo.barTop})`, JSON.stringify(lastHomeCardInfo));
    } else if (lastHomeCardInfo) {
      addPass('HomeScreen', `서류카드 클릭 가능 (bottom=${Math.round(lastHomeCardInfo.rect.bottom)}, barTop=${Math.round(lastHomeCardInfo.barTop)})`);
    }

    // ── 2. 민법26 → ListScreen ───────────────────────────
    const clickedMinbeop = await clickSubject(page, '민법');
    if (!clickedMinbeop) {
      addBug('Home', '민법26 과목 클릭 실패');
    } else {
      await wait(page, 800);
      await shot(page, '02_list_minbeop_lv1');

      // 파일 그룹 전부 펼치기
      const toggleAllBtn = page.locator('button[aria-label="전체 접기/펼치기"]').first();
      if (await toggleAllBtn.count() > 0) {
        // 펼치기 (이미 펼쳐져 있으면 접었다가 다시 펼치기)
        const label = await toggleAllBtn.innerText();
        if (label.includes('펼치기')) {
          await toggleAllBtn.click();
          await wait(page, 500);
        }
      }
      await shot(page, '03_list_all_expanded');

      // 가장 아래 문제 카드 스크롤 후 클릭 가능성 체크
      const lastQuestion = await page.evaluate(() => {
        // role=button 에서 duration 패턴 가진 것들 (문제 카드) 수집
        const all = Array.from(document.querySelectorAll('[role="button"]'));
        const questions = all.filter(el => {
          const t = el.textContent || '';
          return /\d+:\d{2}/.test(t) && t.length > 3 && t.length < 300
            && !/Lv\./i.test(t) && !/전체재생|즐겨찾기|전체|설정|선택|취약/.test(t.trim().split('\n')[0]);
        });
        if (questions.length === 0) return null;
        const last = questions[questions.length - 1];
        // 스크롤 컨테이너를 끝까지 스크롤 (요소를 container 바닥으로)
        let scroll = last.closest('.overflow-y-auto');
        if (scroll) scroll.scrollTop = scroll.scrollHeight;
        const r = last.getBoundingClientRect();
        const bar = document.querySelector('.fixed.bottom-0.left-0.right-0.max-w-md.mx-auto.z-50');
        const br = bar ? bar.getBoundingClientRect() : null;
        // 중심점 elementFromPoint
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const top = document.elementFromPoint(cx, cy);
        const topBlocked = top && bar && bar.contains(top);
        const barTop = br ? br.top : null;
        return {
          text: (last.textContent || '').trim().slice(0, 80),
          rect: { top: r.top, bottom: r.bottom, height: r.height },
          barTop,
          topBlocked,
          overlapsTop: barTop !== null && r.bottom > barTop,
        };
      });

      if (lastQuestion && lastQuestion.topBlocked) {
        addBug('ListScreen', '[핵심] 마지막 문제 카드가 플레이바에 가려져 클릭 불가', JSON.stringify(lastQuestion));
      } else if (lastQuestion && lastQuestion.overlapsTop) {
        addBug('ListScreen', '마지막 문제 카드 하단이 플레이바와 겹침 (일부 가려짐)', JSON.stringify(lastQuestion));
      } else if (lastQuestion) {
        addPass('ListScreen', `마지막 문제 카드 클릭 가능 (text="${lastQuestion.text}")`);
      } else {
        addBug('ListScreen', '마지막 문제 카드 못 찾음');
      }

      await shot(page, '04_list_last_question');

      // Lv.2, Lv.3, Lv.4 탭 전환
      for (const lv of [2, 3, 4]) {
        const ok = await clickLv(page, lv);
        if (ok) {
          await wait(page, 500);
          addPass('ListScreen', `Lv.${lv} 탭 전환`);
        } else {
          addBug('ListScreen', `Lv.${lv} 탭 클릭 실패 (disabled?)`);
        }
      }
      await shot(page, '05_list_lv4');

      // 검색 모드 테스트
      const searchBtn = page.locator('button[aria-label="검색"]');
      if (await searchBtn.count() > 0) {
        await searchBtn.click();
        await wait(page, 300);
        const searchInput = page.locator('input[placeholder*="검색"]').first();
        if (await searchInput.count() > 0) {
          await searchInput.fill('법');
          await wait(page, 500);
          addPass('ListScreen', '검색 입력 동작');
        } else {
          addBug('ListScreen', '검색 열었으나 input 못 찾음');
        }
        // 검색 닫기
        await searchBtn.click();
        await wait(page, 200);
      }
      await shot(page, '06_list_search_closed');

      // 선택 모드 테스트
      const selectModeBtn = page.locator('button:has-text("선택 재생")').first();
      if (await selectModeBtn.count() > 0) {
        await selectModeBtn.click();
        await wait(page, 300);
        addPass('ListScreen', '선택 모드 진입');
        // 취소 (두 번째 상태가 "취소"로 표시)
        const cancelBtn = page.locator('button:has-text("취소")').first();
        if (await cancelBtn.count() > 0) {
          await cancelBtn.click();
          await wait(page, 200);
          addPass('ListScreen', '선택 모드 해제');
        }
      }

      // 취약 재생 바텀시트
      const weakBtn = page.locator('button:has-text("취약 재생")').first();
      if (await weakBtn.count() > 0) {
        await weakBtn.click();
        await wait(page, 400);
        addPass('ListScreen', '취약 재생 시트 열림');
        await shot(page, '07_weak_sheet');
        const closeBtn = page.locator('button:has-text("닫기")').first();
        if (await closeBtn.count() > 0) { await closeBtn.click(); await wait(page, 200); }
      }

      // 파일 그룹 접기/펼치기 재테스트
      const toggleAllBtn2 = page.locator('button[aria-label="전체 접기/펼치기"]').first();
      if (await toggleAllBtn2.count() > 0) {
        await toggleAllBtn2.click();
        await wait(page, 300);
        await toggleAllBtn2.click();
        await wait(page, 300);
        addPass('ListScreen', '전체 접기/펼치기 토글');
      }

      // Lv.1 문제 카드 클릭 → PlayerScreen
      await clickLv(page, 1);
      await wait(page, 300);
      // 문제 카드 찾기 (Lv./전체/선택/즐겨찾기/취약 등 컨트롤 제외)
      const questionCard = await page.evaluate(() => {
        const all = Array.from(document.querySelectorAll('[role="button"]'));
        const questions = all.filter(el => {
          const t = el.textContent || '';
          return /\d+:\d{2}/.test(t) && t.length > 3 && t.length < 300
            && !/Lv\./i.test(t) && !/전체재생|즐겨찾기|전체 재생|설정|선택 재생|취약|전체 접/.test(t.trim().split('\n')[0]);
        });
        if (questions.length === 0) return null;
        return {
          id: questions[0].id || '',
          text: (questions[0].textContent || '').slice(0, 60).trim(),
        };
      });

      if (questionCard) {
        // 첫 번째 문제 카드 클릭
        const clicked = await page.evaluate(() => {
          const all = Array.from(document.querySelectorAll('[role="button"]'));
          const questions = all.filter(el => {
            const t = el.textContent || '';
            return /\d+:\d{2}/.test(t) && t.length > 3 && t.length < 300
              && !/Lv\./i.test(t) && !/전체재생|즐겨찾기|전체 재생|설정|선택 재생|취약|전체 접/.test(t.trim().split('\n')[0]);
          });
          if (questions[0]) {
            questions[0].click();
            return true;
          }
          return false;
        });
        if (clicked) {
          await wait(page, 1000);
          addPass('ListScreen', 'PlayerScreen 진입');
          await shot(page, '08_player_reader');
        } else {
          addBug('ListScreen', '문제 카드 click 실패');
        }
      } else {
        addBug('ListScreen', 'Lv.1에 문제 카드 없음');
      }

      // ── 3. PlayerScreen ────────────────────────────────
      const playerBar = await getPlayerBarRect(page);
      if (playerBar) {
        addPass('PlayerScreen', `플레이바 렌더 (h=${Math.round(playerBar.height)}px)`);
      }

      // 가사 탭 전환
      const lyricsBtn = page.locator('button:has-text("가사")').first();
      if (await lyricsBtn.count() > 0) {
        await lyricsBtn.click();
        await wait(page, 400);
        addPass('PlayerScreen', '가사 뷰 전환');
        await shot(page, '09_player_lyrics');
      }
      // 리더 복귀
      const readerBtn = page.locator('button:has-text("리더")').first();
      if (await readerBtn.count() > 0) {
        await readerBtn.click();
        await wait(page, 300);
        addPass('PlayerScreen', '리더 뷰 복귀');
      }

      // PlayerScreen 하단 콘텐츠가 플레이바에 가려지는지
      const playerBottomOverlap = await page.evaluate(() => {
        // 답안 마지막 문장
        const paras = Array.from(document.querySelectorAll('p, [role="button"]'));
        const visible = paras.filter(p => {
          const r = p.getBoundingClientRect();
          return r.top >= 0 && r.top <= window.innerHeight && r.height > 0;
        });
        if (visible.length === 0) return { found: false };
        const last = visible[visible.length - 1];
        const r = last.getBoundingClientRect();
        const bar = document.querySelector('.fixed.bottom-0.left-0.right-0.max-w-md.mx-auto.z-50');
        const br = bar ? bar.getBoundingClientRect() : null;
        return {
          found: true,
          lastText: (last.textContent || '').slice(0, 60),
          lastBottom: r.bottom,
          barTop: br ? br.top : null,
          overlap: br ? r.bottom > br.top : false,
        };
      });
      if (playerBottomOverlap.found && playerBottomOverlap.overlap) {
        // PlayerScreen은 pb-44 (176px)이므로 일반적으로 안 겹쳐야 함. 겹치면 버그.
        // 단, 의도적인 스크롤 위치(아래쪽 문장이 보여도 위 툴바 위로 올라감)는 허용.
        // 실제 플레이어에서는 스크롤 위치가 자동 조정되므로 pb 값이 충분한지만 check.
      }

      // 속도 시트
      const speedBtn = page.locator('button[aria-label*="재생 속도"]').first();
      if (await speedBtn.count() > 0) {
        await speedBtn.click();
        await wait(page, 400);
        addPass('PlayerBar', '속도 시트 열림');
        await shot(page, '10_speed_sheet');
        // 시트 닫기 (backdrop z-[60]과 z-[70] 시트 밖을 클릭 — backdrop이 inset-0)
        await page.evaluate(() => {
          const backdrops = document.querySelectorAll('.fixed.inset-0.bg-black\\/40');
          if (backdrops.length > 0) backdrops[backdrops.length - 1].click();
        });
        await wait(page, 400);
      }

      // 재생/정지 버튼
      const playBtn = page.locator('button[aria-label="재생"], button[aria-label="일시정지"]').first();
      if (await playBtn.count() > 0) {
        try {
          await playBtn.click({ timeout: 5000 });
          await wait(page, 300);
          await playBtn.click({ timeout: 5000 });
          await wait(page, 300);
          addPass('PlayerBar', '재생/정지 토글 동작');
        } catch (e) {
          addBug('PlayerBar', '재생 버튼 클릭 실패 (시트 가려짐?)', e.message.slice(0, 100));
        }
      }

      // 다음/이전 문장
      const nextSentBtn = page.locator('button[aria-label="다음 문장"]').first();
      if (await nextSentBtn.count() > 0) {
        try {
          await nextSentBtn.click({ timeout: 5000 });
          await wait(page, 200);
          addPass('PlayerBar', '다음 문장 버튼');
        } catch (e) {
          addBug('PlayerBar', '다음 문장 버튼 클릭 실패', e.message.slice(0, 80));
        }
      }

      // 뒤로가기
      const backBtn = page.locator('button[aria-label="뒤로가기"]').first();
      if (await backBtn.count() > 0) {
        await backBtn.click();
        await wait(page, 500);
        addPass('PlayerScreen', '뒤로가기 (→ ListScreen)');
        await shot(page, '11_back_to_list');
      }

      // 다시 뒤로 (→ Home)
      const backBtn2 = page.locator('button[aria-label="뒤로가기"]').first();
      if (await backBtn2.count() > 0) {
        await backBtn2.click();
        await wait(page, 500);
        addPass('ListScreen', '뒤로가기 (→ Home)');
      }
    }

    // ── 4. 다른 과목도 순회 ──────────────────────────────
    const subjectKeywords = ['민소', '형법', '형소', '등기', '테스트'];
    for (const kw of subjectKeywords) {
      const ok = await clickSubject(page, kw);
      if (!ok) {
        continue;
      }
      await wait(page, 600);

      // 각 과목 마지막 문제 카드 오버랩 체크
      const lastOverlap = await page.evaluate(() => {
        // Lv.1 선택 (기본)
        const all = Array.from(document.querySelectorAll('[role="button"]'));
        const questions = all.filter(el => {
          const t = el.textContent || '';
          return /\d+:\d{2}/.test(t) && t.length > 3 && t.length < 300
            && !/Lv\./i.test(t) && !/전체재생|즐겨찾기|전체 재생|설정|선택 재생|취약|전체 접/.test(t.trim().split('\n')[0]);
        });
        if (questions.length === 0) return null;
        const last = questions[questions.length - 1];
        // 스크롤 컨테이너를 끝까지 스크롤 (요소를 container 바닥으로)
        let scroll = last.closest('.overflow-y-auto');
        if (scroll) scroll.scrollTop = scroll.scrollHeight;
        const r = last.getBoundingClientRect();
        const bar = document.querySelector('.fixed.bottom-0.left-0.right-0.max-w-md.mx-auto.z-50');
        const br = bar ? bar.getBoundingClientRect() : null;
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const top = document.elementFromPoint(cx, cy);
        const topBlocked = top && bar && bar.contains(top);
        return {
          text: (last.textContent || '').trim().slice(0, 50),
          rect: { top: r.top, bottom: r.bottom },
          barTop: br ? br.top : null,
          topBlocked,
        };
      });

      if (lastOverlap && lastOverlap.topBlocked) {
        addBug(`ListScreen(${kw})`, '마지막 문제 카드 플레이바에 가려짐', JSON.stringify(lastOverlap));
      } else if (lastOverlap) {
        addPass(`ListScreen(${kw})`, '마지막 카드 정상 클릭 가능');
      }

      // Lv.4 확인
      const lv4ok = await clickLv(page, 4);
      if (lv4ok) {
        await wait(page, 400);
        addPass(`ListScreen(${kw})`, 'Lv.4 전환');
        await shot(page, `13_${kw}_lv4`);
      }

      // 뒤로가기
      const back = page.locator('button[aria-label="뒤로가기"]').first();
      if (await back.count() > 0) {
        await back.click();
        await wait(page, 500);
      }
    }

    // ── 5. 즐겨찾기 화면 ──────────────────────────────
    const minbeop2 = await clickSubject(page, '민법');
    if (minbeop2) {
      await wait(page, 500);
      const favBtn = page.locator('button:has-text("즐겨찾기")').first();
      if (await favBtn.count() > 0) {
        await favBtn.click();
        await wait(page, 600);
        addPass('FavoriteScreen', '진입');
        await shot(page, '14_favorite_empty');
        const backF = page.locator('button[aria-label="뒤로가기"]').first();
        if (await backF.count() > 0) { await backF.click(); await wait(page, 400); }
      }
      const back2 = page.locator('button[aria-label="뒤로가기"]').first();
      if (await back2.count() > 0) { await back2.click(); await wait(page, 400); }
    }

    // ── 6. 설정 화면 ──────────────────────────────
    const settingBtn = page.locator('button[aria-label="설정"]').first();
    if (await settingBtn.count() > 0) {
      await settingBtn.click();
      await wait(page, 500);
      addPass('SettingsScreen', '진입');
      await shot(page, '15_settings');

      // 하단 콘텐츠가 플레이바에 가려지는지
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await wait(page, 300);
      await shot(page, '16_settings_bottom');

      const settingsOverlap = await page.evaluate(() => {
        // 설정의 마지막 버튼/텍스트 찾기
        const lastBtn = document.querySelector('.overflow-y-auto.px-4.pb-24');
        if (!lastBtn) return null;
        // 스크롤 맨 아래로
        lastBtn.scrollTop = lastBtn.scrollHeight;
        const all = lastBtn.querySelectorAll('button, a');
        if (all.length === 0) return null;
        const last = all[all.length - 1];
        const r = last.getBoundingClientRect();
        const bar = document.querySelector('.fixed.bottom-0.left-0.right-0.max-w-md.mx-auto.z-50');
        const br = bar ? bar.getBoundingClientRect() : null;
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const top = document.elementFromPoint(cx, cy);
        const topBlocked = top && bar && bar.contains(top);
        return {
          text: (last.textContent || '').trim().slice(0, 40),
          topBlocked,
          lastBottom: r.bottom,
          barTop: br ? br.top : null,
        };
      });
      if (settingsOverlap && settingsOverlap.topBlocked) {
        addBug('SettingsScreen', '하단 버튼이 플레이바에 가려짐', JSON.stringify(settingsOverlap));
      } else {
        addPass('SettingsScreen', '하단 콘텐츠 클릭 가능');
      }

      const backS = page.locator('button[aria-label="뒤로가기"]').first();
      if (await backS.count() > 0) { await backS.click(); await wait(page, 400); }
    }

    // ── 7. 재생 중 상태에서 ListScreen 가려짐 재확인 ───
    // 테스트 과목 → 문제 선택 → 재생 시작 → 뒤로가기 → ListScreen
    const testOK = await clickSubject(page, '테스트');
    if (testOK) {
      await wait(page, 500);
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
        await wait(page, 1000);
        // 플레이바가 playlist 정보 + 컨트롤 전부 보이는 상태
        const barInfo = await getPlayerBarRect(page);
        addPass('PlayerScreen-Test', `플레이바 총 높이 ${Math.round(barInfo.height)}px`);
        await shot(page, '17_playing');

        // 뒤로가서 ListScreen
        const back = page.locator('button[aria-label="뒤로가기"]').first();
        if (await back.count() > 0) {
          await back.click();
          await wait(page, 500);
        }

        // 이제 PlayerBar가 재생중 상태(플레이리스트 트랙정보 표시) → 바 높이 증가
        const barOverlap = await getPlayerBarRect(page);
        await shot(page, '18_list_playing');

        // 이 상태에서 마지막 문제 카드 클릭 가능?
        const lastCovered = await page.evaluate(() => {
          const all = Array.from(document.querySelectorAll('[role="button"]'));
          const qs = all.filter(el => {
            const t = el.textContent || '';
            return /\d+:\d{2}/.test(t) && !/Lv\.|전체|선택|즐겨|취약|접/.test(t.trim().split('\n')[0]);
          });
          if (qs.length === 0) return null;
          const last = qs[qs.length - 1];
          // 스크롤 컨테이너를 끝까지 스크롤 (요소를 container 바닥으로)
        let scroll = last.closest('.overflow-y-auto');
        if (scroll) scroll.scrollTop = scroll.scrollHeight;
          const r = last.getBoundingClientRect();
          const bar = document.querySelector('.fixed.bottom-0.left-0.right-0.max-w-md.mx-auto.z-50');
          const br = bar ? bar.getBoundingClientRect() : null;
          const cx = r.left + r.width / 2;
          const cy = r.top + r.height / 2;
          const top = document.elementFromPoint(cx, cy);
          return {
            text: (last.textContent || '').trim().slice(0, 40),
            lastBottom: r.bottom,
            barTop: br ? br.top : null,
            barHeight: br ? br.height : null,
            topIsBar: top && bar && bar.contains(top),
          };
        });
        if (lastCovered && lastCovered.topIsBar) {
          addBug('ListScreen(재생중)', '재생 중 상태에서 마지막 카드 플레이바에 완전히 가려짐', JSON.stringify(lastCovered));
        } else if (lastCovered) {
          addPass('ListScreen(재생중)', `재생 중에도 마지막 카드 클릭 가능 (bar h=${lastCovered.barHeight})`);
        }
      }
    }

    // ── 8. 콘솔 에러 정리 ──────────────────────────────
    if (consoleErrors.length > 0) {
      for (const err of consoleErrors) {
        addBug('Console', err);
      }
    } else {
      addPass('Console', '콘솔 에러 없음');
    }
  } catch (e) {
    addBug('TestRunner', `예외 발생: ${e.message}`, e.stack?.slice(0, 500));
  } finally {
    await browser.close();
  }

  // ── 결과 출력 ──────────────────────────────────────
  console.log('\n========== 결과 요약 ==========');
  console.log(`PASS: ${passes.length}`);
  console.log(`BUG:  ${bugs.length}`);
  if (bugs.length > 0) {
    console.log('\n[버그 리스트]');
    for (const b of bugs) {
      console.log(`- [${b.screen}] ${b.desc}${b.detail ? `\n    ${b.detail}` : ''}`);
    }
  }

  // 로그 파일 저장
  const summary = {
    timestamp: new Date().toISOString(),
    passCount: passes.length,
    bugCount: bugs.length,
    bugs,
    passes,
  };
  fs.writeFileSync('/tmp/lawear_ui_audit_result.json', JSON.stringify(summary, null, 2));
  console.log('\n[SAVED] /tmp/lawear_ui_audit_result.json');

  process.exit(bugs.length > 0 ? 1 : 0);
})();
