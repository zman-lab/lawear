import { useState, useEffect, useCallback } from 'react';
import { usePlayer } from '../../context/PlayerContext';
import { VoiceSheet } from '../player/VoiceSheet';
import { SpeedSheet } from '../player/SpeedSheet';
import { RepeatModeSheet } from '../player/RepeatModeSheet';
import type { RepeatMode } from '../../types';
import {
  getCacheSizeBySubject,
  getTotalCacheSize,
  getTotalCacheCount,
  clearAllCache,
  formatBytes,
  type CacheSizeInfo,
} from '../../services/audioCache';
import {
  isRenderingSupported,
  enqueue,
  startQueue,
  stopQueue,
  clearQueue,
  setRenderOptions,
  onProgress,
  getProgress,
  type RenderItem,
  type RenderProgress,
} from '../../services/renderQueue';
import { subjects } from '../../data/ttsData';
import { APP_VERSION, BUILD_DATE } from '../../version';
import { GITHUB_OWNER, GITHUB_REPO, GITHUB_API } from '../../config';

interface SettingsScreenProps {
  onBack: () => void;
}


const REPEAT_MODE_LABELS: Record<RepeatMode, string> = {
  'stop-after-one': '1곡 후 정지',
  'stop-after-all': '전곡 후 정지',
  'repeat-all': '전곡 반복',
  'repeat-one': '1곡 반복',
  shuffle: '셔플',
};

/** 과목의 모든 문제를 RenderItem[]으로 변환 */
function getSubjectRenderItems(subjectId: string): RenderItem[] {
  const subject = subjects.find((s) => s.id === subjectId);
  if (!subject) return [];
  const items: RenderItem[] = [];
  for (const file of subject.files) {
    for (const q of file.questions) {
      const { problem, toc, answer } = q.content;
      const tocSentences = toc.map((t) => `${t.number} ${t.text}`);
      const text = [...problem, ...tocSentences, ...answer].join('\n');
      items.push({ subjectId, fileId: file.id, questionId: q.id, text });
    }
  }
  return items;
}

export function SettingsScreen({ onBack }: SettingsScreenProps) {
  const { state, voices } = usePlayer();
  const { selectedVoiceURI, speed, repeatMode } = state;

  const [showVoiceSheet, setShowVoiceSheet] = useState(false);
  const [showSpeedSheet, setShowSpeedSheet] = useState(false);
  const [showRepeatSheet, setShowRepeatSheet] = useState(false);

  // ── 버전 확인 상태 ──────────────────────────────────────────────────────
  const [versionStatus, setVersionStatus] = useState<'idle' | 'checking' | 'latest' | 'update' | 'error'>('idle');
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [changelog, setChangelog] = useState<string | null>(null);

  const checkForUpdate = useCallback(async () => {
    setVersionStatus('checking');
    try {
      const res = await fetch(
        `${GITHUB_API}/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`,
        { cache: 'no-store', headers: { Accept: 'application/vnd.github+json' } },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // tag_name: "v0.1.0.0" → "0.1.0.0"
      const remote = (data.tag_name as string).replace(/^v/, '');
      setLatestVersion(remote);
      // APK asset URL 찾기
      const apkAsset = (data.assets as Array<{ browser_download_url: string; name: string }>)
        ?.find((a) => a.name.endsWith('.apk'));
      setDownloadUrl(apkAsset?.browser_download_url ?? data.html_url);
      setChangelog(data.body ?? null);
      setVersionStatus(remote === APP_VERSION ? 'latest' : 'update');
    } catch {
      setVersionStatus('error');
    }
  }, []);

  // ── 캐시 관련 상태 ──────────────────────────────────────────────────────
  const [cacheBySubject, setCacheBySubject] = useState<Record<string, CacheSizeInfo>>({});
  const [totalCacheSize, setTotalCacheSize] = useState(0);
  const [totalCacheCount, setTotalCacheCount] = useState(0);
  const [isClearing, setIsClearing] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const loadCacheInfo = useCallback(async () => {
    const [bySubject, size, count] = await Promise.all([
      getCacheSizeBySubject(),
      getTotalCacheSize(),
      getTotalCacheCount(),
    ]);
    setCacheBySubject(bySubject);
    setTotalCacheSize(size);
    setTotalCacheCount(count);
  }, []);

  useEffect(() => {
    loadCacheInfo();
  }, [loadCacheInfo]);

  const handleClearAll = useCallback(async () => {
    setIsClearing(true);
    try {
      await clearAllCache();
      await loadCacheInfo();
    } finally {
      setIsClearing(false);
      setShowClearConfirm(false);
    }
  }, [loadCacheInfo]);

  // ── 렌더링 상태 ──────────────────────────────────────────────────────────
  const [renderProgress, setRenderProgress] = useState<RenderProgress>(getProgress);
  const [renderingSubjectId, setRenderingSubjectId] = useState<string | null>(null);

  useEffect(() => {
    onProgress((progress) => {
      setRenderProgress(progress);
      // 렌더링 완료 시 캐시 정보 새로고침
      if (!progress.isRunning && (progress.completed > 0 || progress.errors > 0)) {
        loadCacheInfo();
        setRenderingSubjectId(null);
      }
    });
    return () => onProgress(null);
  }, [loadCacheInfo]);

  const handleStartRender = useCallback((subjectId: string) => {
    clearQueue();
    const items = getSubjectRenderItems(subjectId);
    if (items.length === 0) return;

    setRenderOptions(selectedVoiceURI, speed);
    enqueue(items);
    setRenderingSubjectId(subjectId);
    startQueue();
  }, [selectedVoiceURI, speed]);

  const handleStopRender = useCallback(() => {
    stopQueue();
  }, []);

  // 현재 선택된 음성 이름 찾기
  const currentVoiceName = selectedVoiceURI
    ? voices.find((v) => v.voiceURI === selectedVoiceURI)?.name ?? '알 수 없는 음성'
    : '자동 (한국어 기본)';

  // 한국어 음성 수
  const koreanVoiceCount = voices.filter((v) => v.lang.startsWith('ko')).length;
  const totalVoiceCount = voices.length;

  const canRender = isRenderingSupported();
  const isRendering = renderProgress.isRunning;

  return (
    <div
      className="absolute inset-0 flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1e3a5f 0%, #0d1117 50%)' }}
    >
      {/* 헤더 */}
      <header className="px-4 pt-4 pb-3 flex items-center gap-3 shrink-0">
        <button
          className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center min-w-[32px]"
          onClick={onBack}
          aria-label="뒤로가기"
        >
          <svg
            className="w-4 h-4 text-white/60"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="font-bold text-white">설정</h2>
        </div>
      </header>

      {/* 설정 목록 */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-3">
        {/* TTS 음성 섹션 */}
        <p className="text-[10px] font-bold text-[#8b949e]/60 uppercase tracking-widest pt-1 pb-1">
          TTS 음성
        </p>

        <div className="bg-[#161b22] border border-[#21262d] rounded-xl overflow-hidden">
          {/* 현재 음성 */}
          <button
            className="w-full px-4 py-3.5 flex items-center justify-between active:bg-white/[0.04] transition-colors"
            onClick={() => setShowVoiceSheet(true)}
          >
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <div className="w-9 h-9 rounded-lg bg-blue-500/15 flex items-center justify-center shrink-0">
                <svg className="w-4.5 h-4.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-sm text-white font-medium">음성</p>
                <p className="text-[11px] text-blue-400 truncate">{currentVoiceName}</p>
              </div>
            </div>
            <svg className="w-4 h-4 text-white/20 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          <div className="h-px bg-[#21262d] mx-4" />

          {/* 음성 정보 */}
          <div className="px-4 py-3">
            <div className="flex items-center gap-3 text-[11px] text-[#8b949e]">
              <span>한국어 {koreanVoiceCount}개</span>
              <span className="text-[#8b949e]/30">|</span>
              <span>전체 {totalVoiceCount}개</span>
            </div>
          </div>
        </div>

        {/* 재생 설정 섹션 */}
        <p className="text-[10px] font-bold text-[#8b949e]/60 uppercase tracking-widest pt-3 pb-1">
          재생
        </p>

        <div className="bg-[#161b22] border border-[#21262d] rounded-xl overflow-hidden">
          {/* 재생 속도 */}
          <button
            className="w-full px-4 py-3.5 flex items-center justify-between active:bg-white/[0.04] transition-colors"
            onClick={() => setShowSpeedSheet(true)}
          >
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <div className="w-9 h-9 rounded-lg bg-emerald-500/15 flex items-center justify-center shrink-0">
                <svg className="w-4.5 h-4.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-sm text-white font-medium">재생 속도</p>
                <p className="text-[11px] text-emerald-400">{speed.toFixed(1)}x</p>
              </div>
            </div>
            <svg className="w-4 h-4 text-white/20 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          <div className="h-px bg-[#21262d] mx-4" />

          {/* 반복 모드 */}
          <button
            className="w-full px-4 py-3.5 flex items-center justify-between active:bg-white/[0.04] transition-colors"
            onClick={() => setShowRepeatSheet(true)}
          >
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <div className="w-9 h-9 rounded-lg bg-violet-500/15 flex items-center justify-center shrink-0">
                <svg className="w-4.5 h-4.5 text-violet-400" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-sm text-white font-medium">반복 모드</p>
                <p className="text-[11px] text-violet-400">{REPEAT_MODE_LABELS[repeatMode]}</p>
              </div>
            </div>
            <svg className="w-4 h-4 text-white/20 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* 오프라인 저장 섹션 */}
        <p className="text-[10px] font-bold text-[#8b949e]/60 uppercase tracking-widest pt-3 pb-1">
          오프라인 저장
        </p>

        <div className="bg-[#161b22] border border-[#21262d] rounded-xl overflow-hidden">
          {/* 캐시 요약 */}
          <div className="px-4 py-3.5 flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <div className="w-9 h-9 rounded-lg bg-amber-500/15 flex items-center justify-center shrink-0">
                <svg className="w-4.5 h-4.5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-sm text-white font-medium">캐시된 오디오</p>
                <p className="text-[11px] text-amber-400">
                  {totalCacheCount > 0
                    ? `${totalCacheCount}건 - ${formatBytes(totalCacheSize)}`
                    : '캐시된 파일 없음'}
                </p>
              </div>
            </div>
          </div>

          {/* 렌더링 진행률 */}
          {isRendering && (
            <>
              <div className="h-px bg-[#21262d] mx-4" />
              <div className="px-4 py-3 space-y-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-amber-400">
                    렌더링 중...{' '}
                    {renderProgress.completed + renderProgress.skipped}/{renderProgress.total}
                  </span>
                  <button
                    className="text-red-400/60 px-2 py-0.5 bg-red-500/10 rounded"
                    onClick={handleStopRender}
                  >
                    중단
                  </button>
                </div>
                {/* 프로그레스 바 */}
                <div className="h-1.5 bg-[#21262d] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500 rounded-full transition-all duration-300"
                    style={{
                      width: renderProgress.total > 0
                        ? `${((renderProgress.completed + renderProgress.skipped) / renderProgress.total) * 100}%`
                        : '0%',
                    }}
                  />
                </div>
                {renderProgress.errors > 0 && (
                  <p className="text-[10px] text-red-400/60">
                    오류 {renderProgress.errors}건
                  </p>
                )}
              </div>
            </>
          )}

          {/* 과목별 캐시 현황 + 렌더링 버튼 */}
          <div className="h-px bg-[#21262d] mx-4" />
          <div className="px-4 py-3 space-y-2">
            {subjects.map((subject) => {
              const info = cacheBySubject[subject.id];
              const totalQ = subject.totalQuestions;
              const cachedQ = info?.count ?? 0;
              const isThisRendering = isRendering && renderingSubjectId === subject.id;

              return (
                <div key={subject.id} className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className="text-[#8b949e]">{subject.name}</span>
                      <span className="text-[#8b949e]/40">
                        {cachedQ}/{totalQ}
                      </span>
                    </div>
                    {info && (
                      <p className="text-[10px] text-[#8b949e]/40">{formatBytes(info.totalBytes)}</p>
                    )}
                  </div>
                  {canRender && (
                    <button
                      className={`text-[10px] px-2.5 py-1 rounded-md transition-colors ${
                        isThisRendering
                          ? 'bg-amber-500/15 text-amber-400'
                          : cachedQ >= totalQ
                            ? 'bg-emerald-500/10 text-emerald-400/60'
                            : 'bg-amber-500/10 text-amber-400 active:bg-amber-500/20'
                      }`}
                      onClick={() => handleStartRender(subject.id)}
                      disabled={isRendering || cachedQ >= totalQ}
                    >
                      {isThisRendering
                        ? '저장 중...'
                        : cachedQ >= totalQ
                          ? '완료'
                          : cachedQ > 0
                            ? '이어서 저장'
                            : '저장'}
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          <div className="h-px bg-[#21262d] mx-4" />

          {/* 캐시 전체 삭제 버튼 */}
          {!showClearConfirm ? (
            <button
              className="w-full px-4 py-3.5 flex items-center justify-center active:bg-white/[0.04] transition-colors disabled:opacity-40"
              onClick={() => setShowClearConfirm(true)}
              disabled={totalCacheCount === 0}
            >
              <span className="text-sm text-red-400/80">
                캐시 전체 삭제
              </span>
            </button>
          ) : (
            <div className="px-4 py-3.5 space-y-2">
              <p className="text-[11px] text-[#8b949e] text-center">
                캐시된 오디오 {totalCacheCount}건 ({formatBytes(totalCacheSize)})을 삭제합니다.
              </p>
              <div className="flex gap-2">
                <button
                  className="flex-1 py-2 rounded-lg bg-[#21262d] text-sm text-[#8b949e] active:bg-[#30363d] transition-colors"
                  onClick={() => setShowClearConfirm(false)}
                  disabled={isClearing}
                >
                  취소
                </button>
                <button
                  className="flex-1 py-2 rounded-lg bg-red-500/20 text-sm text-red-400 active:bg-red-500/30 transition-colors disabled:opacity-40"
                  onClick={handleClearAll}
                  disabled={isClearing}
                >
                  {isClearing ? '삭제 중...' : '삭제'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 안내 문구 */}
        <p className="text-[10px] text-[#8b949e]/40 leading-relaxed px-1">
          {canRender
            ? '과목별 "저장" 버튼으로 TTS 오디오를 기기에 저장합니다. 저장된 오디오는 실시간 TTS 대신 재생되어 배터리를 절약합니다. WAV 형식으로 저장되며, 과목당 약 200~500MB의 저장 공간이 필요합니다.'
            : '렌더링된 MP3 파일은 기기 내부 저장소에 보관됩니다. 캐시된 오디오가 있으면 실시간 TTS 대신 MP3로 재생하여 배터리를 절약합니다.'}
        </p>

        {/* 앱 정보 */}
        <p className="text-[10px] font-bold text-[#8b949e]/60 uppercase tracking-widest pt-3 pb-1">
          앱 정보
        </p>

        <div className="bg-[#161b22] border border-[#21262d] rounded-xl overflow-hidden">
          {/* 현재 버전 */}
          <div className="px-4 py-3.5 flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <div className="w-9 h-9 rounded-lg bg-cyan-500/15 flex items-center justify-center shrink-0">
                <svg className="w-4.5 h-4.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-sm text-white font-medium">버전</p>
                <p className="text-[11px] text-cyan-400">v{APP_VERSION}</p>
              </div>
            </div>
          </div>

          <div className="h-px bg-[#21262d] mx-4" />

          {/* 빌드 날짜 */}
          <div className="px-4 py-3 flex items-center justify-between">
            <p className="text-[11px] text-[#8b949e]">빌드 날짜</p>
            <p className="text-[11px] text-[#8b949e]/80">{BUILD_DATE}</p>
          </div>

          <div className="h-px bg-[#21262d] mx-4" />

          {/* 최신 버전 확인 버튼 */}
          <button
            className="w-full px-4 py-3.5 flex items-center justify-center active:bg-white/[0.04] transition-colors disabled:opacity-40"
            onClick={checkForUpdate}
            disabled={versionStatus === 'checking'}
          >
            {versionStatus === 'checking' ? (
              <span className="text-sm text-cyan-400/80">확인 중...</span>
            ) : versionStatus === 'latest' ? (
              <span className="text-sm text-emerald-400">최신 버전입니다</span>
            ) : versionStatus === 'error' ? (
              <span className="text-sm text-red-400/80">확인 실패 (탭하여 재시도)</span>
            ) : (
              <span className="text-sm text-cyan-400/80">최신 버전 확인</span>
            )}
          </button>

          {/* 업데이트 가능 시 표시 */}
          {versionStatus === 'update' && latestVersion && (
            <>
              <div className="h-px bg-[#21262d] mx-4" />
              <div className="px-4 py-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-amber-400">새 버전 사용 가능</span>
                  <span className="text-[11px] text-amber-400/80">v{latestVersion}</span>
                </div>
                {changelog && (
                  <p className="text-[11px] text-[#8b949e] leading-relaxed">{changelog}</p>
                )}
                {downloadUrl && (
                  <a
                    href={downloadUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block w-full py-2.5 rounded-lg bg-cyan-500/20 text-sm text-cyan-400 text-center active:bg-cyan-500/30 transition-colors"
                  >
                    APK 다운로드 (v{latestVersion})
                  </a>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* 바텀시트들 */}
      <VoiceSheet isOpen={showVoiceSheet} onClose={() => setShowVoiceSheet(false)} />
      <SpeedSheet isOpen={showSpeedSheet} onClose={() => setShowSpeedSheet(false)} />
      <RepeatModeSheet isOpen={showRepeatSheet} onClose={() => setShowRepeatSheet(false)} />
    </div>
  );
}
