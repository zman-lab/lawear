import { useState } from 'react';
import { PlayerProvider } from './context/PlayerContext';
import { HomeScreen } from './components/screens/HomeScreen';
import { ListScreen } from './components/screens/ListScreen';
import { PlayerScreen } from './components/screens/PlayerScreen';
import { SettingsScreen } from './components/screens/SettingsScreen';
import { PlayerBar } from './components/player/PlayerBar';
import { log } from './services/logger';

type Screen =
  | { type: 'home' }
  | { type: 'list'; subjectId: string }
  | { type: 'player'; subjectId: string; fileId: string; questionId: string }
  | { type: 'settings' };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ type: 'home' });
  const [history, setHistory] = useState<Screen[]>([]);

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
        <PlayerBar />
      </div>
    </PlayerProvider>
  );
}
