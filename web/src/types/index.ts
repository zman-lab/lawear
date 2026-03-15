// ---- TTS Voice (네이티브/웹 통합) ----
export interface TTSVoice {
  voiceURI: string;
  name: string;
  lang: string;
}

export type Theme = 'dark' | 'light';
export type Level = 1 | 2 | 3;
export type ViewMode = 'reader' | 'lyrics';
export type Speed = 0.5 | 0.8 | 1.0 | 1.2 | 1.5 | 2.0 | 2.5 | 3.0;

export type RepeatMode = 'repeat-all' | 'repeat-one' | 'stop-after-one' | 'stop-after-all' | 'shuffle';

export interface SleepTimer {
  endTime: number;
  totalSeconds: number;
}

export interface Subject {
  id: string;
  name: string;
  shortName: string;
  colorClass: string;       // e.g. 'blue', 'emerald', 'rose'
  files: FileGroup[];
  totalQuestions: number;
  completedQuestions: number;
}

export interface FileGroup {
  id: string;
  name: string;
  questions: Question[];
}

export interface Question {
  id: string;
  label: string;
  subtitle: string;
  duration: string;
  content: TTSContent;
}

export interface TTSContent {
  problem: string[];
  toc: TocItem[];
  answer: string[];
}

export interface TocItem {
  number: string;
  text: string;
  indent: number;
}

export interface PlaylistItem {
  subjectId: string;
  fileId: string;
  questionId: string;
}

export interface PlayerState {
  isPlaying: boolean;
  currentSubjectId: string | null;
  currentFileId: string | null;
  currentQuestionId: string | null;
  currentSentenceIndex: number;
  speed: Speed;
  repeatMode: RepeatMode;
  sleepTimer: SleepTimer | null;
  selectedVoiceURI: string | null;
  level: Level;
  viewMode: ViewMode;
  playlist: PlaylistItem[];
  playlistIndex: number;
}

// ---- 레거시 보일러플레이트 타입 (기존 컴포넌트 호환) ----
export type NavItem = {
  label: string;
  path: string;
  group?: string;
  icon?: React.ReactNode;
  children?: NavItem[];
};

export type BadgeVariant = 'success' | 'warning' | 'error' | 'info';
export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export type ChartType = 'line' | 'bar' | 'doughnut';
export interface ChartData {
  labels: string[];
  datasets: {
    label?: string;
    data: number[];
    backgroundColor?: string | string[];
    borderColor?: string | string[];
    borderWidth?: number;
    fill?: boolean;
    tension?: number;
  }[];
}

export interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export type TableColumn<T = Record<string, unknown>> = {
  key: string;
  label: string;
  header?: string;
  sortable?: boolean;
  render?: (value: unknown, row: T) => React.ReactNode;
  width?: string;
};
