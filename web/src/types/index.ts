// ---- TTS Voice (네이티브/웹 통합) ----
export interface TTSVoice {
  voiceURI: string;
  name: string;
  lang: string;
}

// ---- TTS Engine (설치된 엔진 정보) ----
export interface TTSEngine {
  /** 패키지명 (예: com.google.android.tts) */
  name: string;
  /** 표시명 (예: Google 텍스트 음성 변환 엔진) */
  label: string;
}

export type Theme = 'dark' | 'light';
export type Level = 1 | 2 | 3;
export type ViewMode = 'reader' | 'lyrics';
export type Speed = number;

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
  answer_lv2?: string[];  // Lv.2 핵심요약 답안
  answer_lv3?: string[];  // Lv.3 슈퍼심플 답안
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
  /** 북마크 재생 시 해당 문장부터 시작 (미지정 시 0) */
  sentenceIndex?: number;
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
  repeatSectionStart: number | null;
  repeatSectionEnd: number | null;
  isRepeatingSectionActive: boolean;
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
