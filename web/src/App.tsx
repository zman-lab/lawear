import { useState } from 'react';
import { PlayerProvider } from './context/PlayerContext';
import { HomeScreen } from './components/screens/HomeScreen';
import { ListScreen } from './components/screens/ListScreen';
import { PlayerScreen } from './components/screens/PlayerScreen';
import { PlayerBar } from './components/player/PlayerBar';

type Screen =
  | { type: 'home' }
  | { type: 'list'; subjectId: string }
  | { type: 'player'; subjectId: string; fileId: string; questionId: string };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ type: 'home' });
  const [history, setHistory] = useState<Screen[]>([]);

  const navigate = (next: Screen) => {
    setHistory((prev) => [...prev, screen]);
    setScreen(next);
  };

  const goBack = () => {
    const prev = history[history.length - 1];
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
        <PlayerBar />
      </div>
    </PlayerProvider>
  );
}
