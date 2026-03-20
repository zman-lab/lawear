import { useState, useEffect, useCallback } from 'react';
import { Browser } from '@capacitor/browser';
import { Capacitor } from '@capacitor/core';
import { PlayerProvider } from './context/PlayerContext';
import { HomeScreen } from './components/screens/HomeScreen';
import { ListScreen } from './components/screens/ListScreen';
import { PlayerScreen } from './components/screens/PlayerScreen';
import { SettingsScreen } from './components/screens/SettingsScreen';
import { FavoriteScreen } from './components/screens/FavoriteScreen';
import { PlayerBar } from './components/player/PlayerBar';
import { SleepOverlay } from './components/SleepOverlay';
import { log } from './services/logger';
import { runCleanup } from './services/cleanup';
import { APP_VERSION } from './version';
import { GITHUB_OWNER, GITHUB_REPO, GITHUB_API } from './config';

type Screen =
  | { type: 'home' }
  | { type: 'list'; subjectId: string }
  | { type: 'player'; subjectId: string; fileId: string; questionId: string }
  | { type: 'settings' }
  | { type: 'favorites' };

interface UpdateInfo {
  version: string;
  downloadUrl: string;
  notes: string;
}

export default function App() {
  const [screen, setScreen] = useState<Screen>({ type: 'home' });
  const [history, setHistory] = useState<Screen[]>([]);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);

  // 앱 시작 시 자동 업데이트 확인
  const checkUpdate = useCallback(async () => {
    try {
      const res = await fetch(
        `${GITHUB_API}/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`,
        { cache: 'no-store', headers: { Accept: 'application/vnd.github+json' } },
      );
      if (!res.ok) return;
      const data = await res.json();
      const remote = (data.tag_name as string).replace(/^v/, '');
      if (remote === APP_VERSION) return;

      const apkAsset = (data.assets as Array<{ browser_download_url: string; name: string }>)
        ?.find((a) => a.name.endsWith('.apk'));
      if (!apkAsset) return;

      setUpdateInfo({
        version: remote,
        downloadUrl: apkAsset.browser_download_url,
        notes: data.body ?? '',
      });
    } catch {
      // 네트워크 실패 시 무시
    }
  }, []);

  useEffect(() => {
    checkUpdate();
    runCleanup();
  }, [checkUpdate]);

  const handleUpdate = useCallback(async () => {
    if (!updateInfo) return;
    if (Capacitor.isNativePlatform()) {
      await Browser.open({ url: updateInfo.downloadUrl });
    } else {
      window.open(updateInfo.downloadUrl, '_blank');
    }
    setUpdateInfo(null);
  }, [updateInfo]);

  const navigate = (next: Screen) => {
    log.nav('screen_change', { to: next.type, ...(next.type === 'list' ? {subjectId: next.subjectId} : next.type === 'player' ? {subjectId: next.subjectId, fileId: next.fileId, questionId: next.questionId} : {}) });
    setHistory((prev) => [...prev, screen]);
    setScreen(next);
  };

  const goBack = () => {
    const prev = history[history.length - 1];
    log.nav('go_back', { to: prev?.type ?? 'none' });
    if (prev) {
      setHistory((h) => h.slice(0, -1));
      setScreen(prev);
    }
  };

  return (
    <PlayerProvider>
      <div
        className="max-w-md mx-auto h-screen relative bg-bg-primary overflow-hidden"
        data-theme="dark"
      >
        {screen.type === 'home' && (
          <HomeScreen
            onSelectSubject={(id) => navigate({ type: 'list', subjectId: id })}
            onOpenSettings={() => navigate({ type: 'settings' })}
          />
        )}
        {screen.type === 'list' && (
          <ListScreen
            subjectId={screen.subjectId}
            onBack={goBack}
            onSelectQuestion={(sid, fid, qid) =>
              navigate({ type: 'player', subjectId: sid, fileId: fid, questionId: qid })
            }
            onOpenFavorites={() => navigate({ type: 'favorites' })}
          />
        )}
        {screen.type === 'player' && (
          <PlayerScreen
            subjectId={screen.subjectId}
            fileId={screen.fileId}
            questionId={screen.questionId}
            onBack={goBack}
          />
        )}
        {screen.type === 'settings' && (
          <SettingsScreen onBack={goBack} />
        )}
        {screen.type === 'favorites' && (
          <FavoriteScreen onBack={goBack} />
        )}
        <PlayerBar />
        <SleepOverlay />

        {/* 업데이트 다이얼로그 */}
        {updateInfo && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60">
            <div className="mx-6 w-full max-w-sm bg-[#161b22] border border-[#21262d] rounded-2xl overflow-hidden">
              <div className="px-5 pt-5 pb-3 space-y-2">
                <p className="text-white font-bold text-base">업데이트 가능</p>
                <p className="text-cyan-400 text-sm">v{APP_VERSION} → v{updateInfo.version}</p>
                {updateInfo.notes && (
                  <p className="text-[#8b949e] text-xs leading-relaxed whitespace-pre-line">{updateInfo.notes}</p>
                )}
              </div>
              <div className="flex border-t border-[#21262d]">
                <button
                  className="flex-1 py-3.5 text-sm text-[#8b949e] active:bg-white/5 transition-colors"
                  onClick={() => setUpdateInfo(null)}
                >
                  나중에
                </button>
                <div className="w-px bg-[#21262d]" />
                <button
                  className="flex-1 py-3.5 text-sm text-cyan-400 font-medium active:bg-white/5 transition-colors"
                  onClick={handleUpdate}
                >
                  업데이트
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PlayerProvider>
  );
}
