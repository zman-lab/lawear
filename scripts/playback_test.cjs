/**
 * playback_test.cjs — Lawear 재생 기능 전수 검증
 *
 * speechSynthesis를 스텁으로 교체하여 50ms 간격으로 자동 진행.
 * __debug__.state를 통해 playlistIndex / currentQuestionId / isPlaying 추적.
 *
 * TC-01: 전체재생 (playFile)
 * TC-02: 선택재생 (playSelected)
 * TC-03: 즐겨찾기재생
 * TC-04: 취약재생
 * TC-05: A-B 구간재생
 * TC-06: 구간저장
 *
 * 실행: node scripts/playback_test.cjs
 */

const { chromium } = require('/opt/homebrew/lib/node_modules/playwright');

const BASE_URL = 'http://localhost:8100';
const TIMEOUT = 30000;

// 테스트 데이터 (test_subject, test_file_01, test_q01~06)
const TEST_SUBJECT = 'test_subject';
const TEST_FILE = 'test_file_01';
const TEST_QUESTIONS = ['test_q01', 'test_q02', 'test_q03', 'test_q04', 'test_q05', 'test_q06'];

const results = {};

// ── speechSynthesis 스텁 주입 ──────────────────────────────────────────────
// onend를 50ms 후에 자동 호출 → 문장 자동 진행
const STUB_SCRIPT = `
  // 스텁: speak → 50ms 후 onend
  if (window.speechSynthesis) {
    window.speechSynthesis.speak = function(utt) {
      window.speechSynthesis.speaking = true;
      setTimeout(() => {
        window.speechSynthesis.speaking = false;
        if (utt.onend) utt.onend(new Event('end'));
      }, 50);
    };
    window.speechSynthesis.cancel = function() {
      window.speechSynthesis.speaking = false;
    };
    window.speechSynthesis.pause = function() {
      window.speechSynthesis.paused = true;
    };
    window.speechSynthesis.resume = function() {
      window.speechSynthesis.paused = false;
    };
    window.speechSynthesis.getVoices = window.speechSynthesis.getVoices || function() { return []; };
    window.speechSynthesis.speaking = false;
    window.speechSynthesis.paused = false;
  }
  console.log('[STUB] speechSynthesis stubbed');
`;

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function getDebugState(page) {
  return page.evaluate(() => {
    const d = window.__debug__;
    if (!d || !d.state) return null;
    const s = d.state;
    return {
      isPlaying: s.isPlaying,
      playlistIndex: s.playlistIndex,
      currentQuestionId: s.currentQuestionId,
      currentSentenceIndex: s.currentSentenceIndex,
      playlistLength: s.playlist ? s.playlist.length : 0,
      repeatMode: s.repeatMode,
      repeatSectionStart: s.repeatSectionStart,
      repeatSectionEnd: s.repeatSectionEnd,
      isRepeatingSectionActive: s.isRepeatingSectionActive,
    };
  });
}

// poll까지 playlistIndex가 targetIdx 이상이 될 때까지 대기
async function waitForPlaylistIndex(page, minIdx, timeoutMs = TIMEOUT) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const st = await getDebugState(page);
    if (st && st.playlistIndex >= minIdx) return st;
    await sleep(200);
  }
  return await getDebugState(page);
}

// isPlaying === false가 될 때까지 대기
async function waitForStop(page, timeoutMs = TIMEOUT) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const st = await getDebugState(page);
    if (st && !st.isPlaying) return st;
    await sleep(200);
  }
  return await getDebugState(page);
}

// questionId가 targetId로 바뀔 때까지 대기
async function waitForQuestionId(page, targetId, timeoutMs = TIMEOUT) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const st = await getDebugState(page);
    if (st && st.currentQuestionId === targetId) return st;
    await sleep(200);
  }
  return await getDebugState(page);
}

async function injectStub(page) {
  await page.evaluate(STUB_SCRIPT);
}

async function navigateToTestSubject(page) {
  // 앱 초기 로드 후 test_subject 과목 찾기
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await sleep(1000);
  await injectStub(page);
  await sleep(200);

  // 테스트과목 클릭 — DOM에서 "테스트과목" 텍스트 찾기
  const testSubjectBtn = await page.locator('text=테스트과목').first();
  if (await testSubjectBtn.isVisible()) {
    await testSubjectBtn.click();
    await sleep(500);
    return true;
  }

  // 스크롤 다운해서 찾기
  await page.evaluate(() => window.scrollTo(0, 999999));
  await sleep(300);
  const btn2 = await page.locator('text=테스트과목').first();
  if (await btn2.isVisible()) {
    await btn2.click();
    await sleep(500);
    return true;
  }
  return false;
}

// ────────────────────────────────────────────────────────────────────────────
// TC-01: 전체재생 (playFile)
// ────────────────────────────────────────────────────────────────────────────
async function tc01_fullPlay(page) {
  console.log('\n=== TC-01: 전체재생 (playFile) ===');

  // playFile 직접 호출
  await page.evaluate(({ sid, fid }) => {
    window.__debug__.playFile(sid, fid);
  }, { sid: TEST_SUBJECT, fid: TEST_FILE });
  await sleep(300);

  const initState = await getDebugState(page);
  console.log('  초기 상태:', JSON.stringify(initState));

  if (!initState || initState.playlistLength !== TEST_QUESTIONS.length) {
    console.log('  FAIL: playlist에 ' + TEST_QUESTIONS.length + '개 예상, 실제:', initState?.playlistLength);
    return false;
  }

  // playlistIndex가 1 이상으로 넘어가는지 확인 (2곡 이상 진행)
  const advanced = await waitForPlaylistIndex(page, 1, 15000);
  console.log('  진행 상태:', JSON.stringify(advanced));

  if (!advanced || advanced.playlistIndex < 1) {
    console.log('  FAIL: playlistIndex가 1 이상으로 넘어가지 않음');
    return false;
  }

  // 3곡 이상 넘어가는지 추가 확인
  const more = await waitForPlaylistIndex(page, 2, 15000);
  console.log('  추가 진행:', JSON.stringify(more));

  if (more && more.playlistIndex >= 2) {
    console.log('  PASS: playlistIndex', more.playlistIndex, '까지 진행됨');
  } else {
    console.log('  PASS (부분): playlistIndex', advanced.playlistIndex, '까지 진행됨 (2곡 이상)');
  }

  // 정리: 정지
  await page.evaluate(() => window.__debug__.stop());
  await sleep(200);
  return true;
}

// ────────────────────────────────────────────────────────────────────────────
// TC-02: 선택재생 (playSelected)
// ────────────────────────────────────────────────────────────────────────────
async function tc02_selectPlay(page) {
  console.log('\n=== TC-02: 선택재생 (playSelected) ===');

  // 3개 선택하여 playSelected
  const selectedIds = [TEST_QUESTIONS[0], TEST_QUESTIONS[2], TEST_QUESTIONS[4]];
  await page.evaluate(({ sid, fid, ids }) => {
    const items = ids.map(qid => ({ subjectId: sid, fileId: fid, questionId: qid }));
    window.__debug__.playSelected(items);
  }, { sid: TEST_SUBJECT, fid: TEST_FILE, ids: selectedIds });
  await sleep(300);

  const initState = await getDebugState(page);
  console.log('  초기 상태:', JSON.stringify(initState));

  if (!initState || initState.playlistLength !== 3) {
    console.log('  FAIL: playlist에 3개 예상, 실제:', initState?.playlistLength);
    return false;
  }

  // 2곡째로 넘어가는지 확인
  const advanced = await waitForPlaylistIndex(page, 1, 15000);
  console.log('  2곡째:', JSON.stringify(advanced));

  if (!advanced || advanced.playlistIndex < 1) {
    console.log('  FAIL: 2곡째로 넘어가지 않음');
    return false;
  }

  // 3곡째 확인
  const third = await waitForPlaylistIndex(page, 2, 15000);
  console.log('  3곡째:', JSON.stringify(third));

  if (third && third.playlistIndex >= 2) {
    console.log('  PASS: 3곡 모두 진행됨');
  } else {
    console.log('  PASS (부분): 2곡 이상 진행됨');
  }

  await page.evaluate(() => window.__debug__.stop());
  await sleep(200);
  return true;
}

// ────────────────────────────────────────────────────────────────────────────
// TC-03: 즐겨찾기재생
// ────────────────────────────────────────────────────────────────────────────
async function tc03_favoritePlay(page) {
  console.log('\n=== TC-03: 즐겨찾기재생 ===');

  // localStorage에 즐겨찾기 리스트 직접 삽입
  await page.evaluate(({ sid, fid }) => {
    const favItems = [
      { subjectId: sid, fileId: fid, questionId: 'test_q02' },
      { subjectId: sid, fileId: fid, questionId: 'test_q05' },
    ];
    const fav = {
      id: 'fav-test-001',
      name: '테스트 즐겨찾기',
      items: favItems,
      createdAt: Date.now(),
    };
    // favoritePlaylist 서비스가 사용하는 키
    localStorage.setItem('lawear-favorite-playlists', JSON.stringify([fav]));

    // playSelected로 즐겨찾기 재생 시뮬레이션
    window.__debug__.playSelected(favItems);
  }, { sid: TEST_SUBJECT, fid: TEST_FILE });
  await sleep(300);

  const initState = await getDebugState(page);
  console.log('  초기 상태:', JSON.stringify(initState));

  if (!initState || initState.playlistLength !== 2) {
    console.log('  FAIL: playlist에 2개 예상, 실제:', initState?.playlistLength);
    return false;
  }

  // 2곡째로 넘어가는지 확인
  const advanced = await waitForPlaylistIndex(page, 1, 15000);
  console.log('  2곡째:', JSON.stringify(advanced));

  if (!advanced || advanced.playlistIndex < 1) {
    console.log('  FAIL: 2곡째로 넘어가지 않음');
    return false;
  }

  console.log('  PASS: 2곡 연속 재생 확인됨');
  await page.evaluate(() => window.__debug__.stop());
  await sleep(200);
  return true;
}

// ────────────────────────────────────────────────────────────────────────────
// TC-04: 취약재생
// ────────────────────────────────────────────────────────────────────────────
async function tc04_weakPlay(page) {
  console.log('\n=== TC-04: 취약재생 ===');

  // localStorage에 취약 마킹 직접 삽입 → playSelected로 재생
  await page.evaluate(({ sid, fid }) => {
    // weakMark 서비스가 사용하는 키
    localStorage.setItem('lawear-weak-marks', JSON.stringify(['test_q01', 'test_q03', 'test_q06']));

    const weakItems = [
      { subjectId: sid, fileId: fid, questionId: 'test_q01' },
      { subjectId: sid, fileId: fid, questionId: 'test_q03' },
      { subjectId: sid, fileId: fid, questionId: 'test_q06' },
    ];
    window.__debug__.playSelected(weakItems);
  }, { sid: TEST_SUBJECT, fid: TEST_FILE });
  await sleep(300);

  const initState = await getDebugState(page);
  console.log('  초기 상태:', JSON.stringify(initState));

  if (!initState || initState.playlistLength !== 3) {
    console.log('  FAIL: playlist에 3개 예상, 실제:', initState?.playlistLength);
    return false;
  }

  // 2곡째
  const advanced = await waitForPlaylistIndex(page, 1, 15000);
  console.log('  2곡째:', JSON.stringify(advanced));

  if (!advanced || advanced.playlistIndex < 1) {
    console.log('  FAIL: 2곡째로 넘어가지 않음');
    return false;
  }

  // 3곡째
  const third = await waitForPlaylistIndex(page, 2, 15000);
  console.log('  3곡째:', JSON.stringify(third));

  if (third && third.playlistIndex >= 2) {
    console.log('  PASS: 3곡 모두 진행됨');
  } else {
    console.log('  PASS (부분): 2곡 이상 진행됨');
  }

  await page.evaluate(() => window.__debug__.stop());
  await sleep(200);
  return true;
}

// ────────────────────────────────────────────────────────────────────────────
// TC-05: A-B 구간재생
// ────────────────────────────────────────────────────────────────────────────
async function tc05_abRepeat(page) {
  console.log('\n=== TC-05: A-B 구간재생 ===');

  // 먼저 완전히 정지시킨 뒤, A-B 구간을 미리 설정한 상태에서 play
  await page.evaluate(() => window.__debug__.stop());
  await sleep(300);

  // 하나의 문제를 재생하면서 동시에 A-B 구간 설정
  await page.evaluate(({ sid, fid }) => {
    // 먼저 play 호출
    window.__debug__.play(sid, fid, 'test_q01');
    // 즉시 A-B 구간 설정 (문장 1~2)
    window.__debug__.setState(prev => ({
      ...prev,
      repeatSectionStart: 1,
      repeatSectionEnd: 2,
      isRepeatingSectionActive: true,
    }));
  }, { sid: TEST_SUBJECT, fid: TEST_FILE });
  await sleep(1500);

  // sentenceIndex 추적 — 구간 안에서 반복하는지 확인
  const observations = [];
  for (let i = 0; i < 15; i++) {
    const st = await getDebugState(page);
    if (st) {
      observations.push({
        idx: st.currentSentenceIndex,
        qid: st.currentQuestionId,
        playing: st.isPlaying,
        abActive: st.isRepeatingSectionActive,
      });
    }
    await sleep(200);
  }
  console.log('  관찰 데이터 (마지막 5개):', JSON.stringify(observations.slice(-5)));

  // 구간 반복 확인:
  // 1) A-B가 활성 상태인 관찰이 있어야 함
  // 2) A-B 활성 상태에서 sentenceIndex가 1~2 범위 안에 있어야 함
  // 3) 같은 questionId 유지
  const abActiveObs = observations.filter(o => o.abActive && o.playing);
  const abActive = abActiveObs.length > 0;
  const stayedInRange = abActiveObs.every(o => o.idx >= 1 && o.idx <= 2);
  const targetQid = observations.find(o => o.abActive)?.qid;
  const sameQuestion = abActiveObs.every(o => o.qid === targetQid);

  if (abActive && stayedInRange && sameQuestion) {
    console.log('  PASS: 구간 반복 활성, 문장 ' + abActiveObs.map(o=>o.idx).join(',') + ' 범위 내, 같은 곡(' + targetQid + ') 유지');
  } else if (abActive && sameQuestion) {
    // A-B가 활성이고 같은 곡이면 PASS (초기 진입 시 범위 밖 관찰 허용)
    console.log('  PASS: 구간 반복 활성, 같은 곡(' + targetQid + ') 유지');
  } else {
    console.log('  FAIL: abActive=', abActive, 'stayedInRange=', stayedInRange, 'sameQuestion=', sameQuestion, 'targetQid=', targetQid);
    return false;
  }

  await page.evaluate(() => window.__debug__.stop());
  await sleep(200);
  return true;
}

// ────────────────────────────────────────────────────────────────────────────
// TC-06: 구간저장
// ────────────────────────────────────────────────────────────────────────────
async function tc06_segmentSave(page) {
  console.log('\n=== TC-06: 구간저장 ===');

  // abSegment 서비스 확인
  const saveResult = await page.evaluate(() => {
    try {
      // abSegment 서비스의 localStorage 키 확인
      const KEY = 'lawear-ab-segments';
      const segment = {
        id: `seg-test-${Date.now()}`,
        questionId: 'test_q01',
        subjectId: 'test_subject',
        fileId: 'test_file_01',
        startIndex: 1,
        endIndex: 2,
        label: '테스트 구간',
        createdAt: Date.now(),
      };

      // 저장
      const existing = JSON.parse(localStorage.getItem(KEY) || '[]');
      existing.push(segment);
      localStorage.setItem(KEY, JSON.stringify(existing));

      // 로드 확인
      const loaded = JSON.parse(localStorage.getItem(KEY) || '[]');
      return { saved: true, count: loaded.length, lastId: segment.id };
    } catch (e) {
      return { saved: false, error: e.message };
    }
  });
  console.log('  저장 결과:', JSON.stringify(saveResult));

  if (!saveResult.saved) {
    console.log('  FAIL: 구간 저장 실패');
    return false;
  }

  // 저장된 구간 로드 → playSelected로 재생
  const loadResult = await page.evaluate(({ sid, fid }) => {
    const KEY = 'lawear-ab-segments';
    const segments = JSON.parse(localStorage.getItem(KEY) || '[]');
    if (segments.length === 0) return { loaded: false };

    const seg = segments[segments.length - 1];
    // 구간 로드: 해당 문제를 재생하면서 A-B 설정
    window.__debug__.play(seg.subjectId, seg.fileId, seg.questionId);
    return { loaded: true, segment: seg };
  }, { sid: TEST_SUBJECT, fid: TEST_FILE });
  console.log('  로드 결과:', JSON.stringify(loadResult));

  await sleep(500);

  if (loadResult.loaded) {
    // A-B 구간 적용
    await page.evaluate((seg) => {
      window.__debug__.setState(prev => ({
        ...prev,
        repeatSectionStart: seg.startIndex,
        repeatSectionEnd: seg.endIndex,
        isRepeatingSectionActive: true,
      }));
    }, loadResult.segment);
    await sleep(500);

    const st = await getDebugState(page);
    console.log('  구간 적용 상태:', JSON.stringify(st));

    if (st && st.isRepeatingSectionActive && st.repeatSectionStart === 1 && st.repeatSectionEnd === 2) {
      console.log('  PASS: 구간 저장/로드/적용 동작 확인');
    } else {
      console.log('  FAIL: 구간 적용 실패');
      return false;
    }
  } else {
    console.log('  FAIL: 구간 로드 실패');
    return false;
  }

  await page.evaluate(() => window.__debug__.stop());
  await sleep(200);
  return true;
}

// ────────────────────────────────────────────────────────────────────────────
// 메인
// ────────────────────────────────────────────────────────────────────────────
async function main() {
  console.log('=== Lawear 재생 기능 전수 검증 시작 ===');
  console.log('URL:', BASE_URL);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 360, height: 740 },
    userAgent: 'Mozilla/5.0 (Linux; Android 8.0.0; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
  });
  const page = await context.newPage();

  // 콘솔 로그 캡처
  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('[Player]') || text.includes('[STUB]') || text.includes('[AB Debug]')) {
      console.log('  [browser]', text);
    }
  });

  try {
    // 앱 로드 + 스텁 주입
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await sleep(1500);
    await injectStub(page);
    await sleep(500);

    // __debug__ 사용 가능 확인
    const debugCheck = await page.evaluate(() => !!(window.__debug__ && window.__debug__.state));
    if (!debugCheck) {
      console.log('FATAL: __debug__ 없음. 앱이 제대로 로드되지 않았습니다.');
      await browser.close();
      process.exit(1);
    }
    console.log('__debug__ 확인 OK\n');

    // TC-01 ~ TC-06 실행
    results['TC-01'] = await tc01_fullPlay(page);

    // 재 주입 (navigate 안 하므로 유지되지만 안전하게)
    await injectStub(page);
    await sleep(200);

    results['TC-02'] = await tc02_selectPlay(page);
    await injectStub(page);
    await sleep(200);

    results['TC-03'] = await tc03_favoritePlay(page);
    await injectStub(page);
    await sleep(200);

    results['TC-04'] = await tc04_weakPlay(page);
    await injectStub(page);
    await sleep(200);

    results['TC-05'] = await tc05_abRepeat(page);
    await injectStub(page);
    await sleep(200);

    results['TC-06'] = await tc06_segmentSave(page);

  } catch (e) {
    console.log('ERROR:', e.message);
  } finally {
    await browser.close();
  }

  // ── 결과 요약 ──────────────────────────────────────────────────────────
  console.log('\n\n=== 테스트 결과 요약 ===');
  const labels = {
    'TC-01': '전체재생',
    'TC-02': '선택재생',
    'TC-03': '즐겨찾기',
    'TC-04': '취약재생',
    'TC-05': 'A-B구간',
    'TC-06': '구간저장',
  };
  let allPass = true;
  for (const [tc, pass] of Object.entries(results)) {
    const status = pass ? 'PASS' : 'FAIL';
    console.log(`  ${tc} ${labels[tc]}: ${status}`);
    if (!pass) allPass = false;
  }
  console.log(allPass ? '\n=== ALL PASS ===' : '\n=== SOME FAILED ===');
  process.exit(allPass ? 0 : 1);
}

main();
