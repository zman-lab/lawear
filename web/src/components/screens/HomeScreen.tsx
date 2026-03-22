import { useState, useEffect } from 'react';
import { subjects } from '../../data/ttsData';
import type { Subject } from '../../types';
import { loadExamDate, calcDday, formatDday } from '../../services/examDate';
import { getReviewSummary, type ReviewItem } from '../../services/ebbinghaus';
import { usePlayer } from '../../context/PlayerContext';

interface HomeScreenProps {
  onSelectSubject: (subjectId: string) => void;
  onOpenSettings: () => void;
}

const SUBJECT_STYLES: Record<
  string,
  { gradient: string; border: string; iconBg: string; shadow: string }
> = {
  blue: {
    gradient: 'from-blue-900/50 to-[#161b22]/80',
    border: 'border-blue-500/10',
    iconBg: 'bg-blue-600',
    shadow: 'shadow-blue-600/20',
  },
  emerald: {
    gradient: 'from-emerald-900/50 to-[#161b22]/80',
    border: 'border-emerald-500/10',
    iconBg: 'bg-emerald-600',
    shadow: 'shadow-emerald-600/20',
  },
  rose: {
    gradient: 'from-rose-900/50 to-[#161b22]/80',
    border: 'border-rose-500/10',
    iconBg: 'bg-rose-600',
    shadow: 'shadow-rose-600/20',
  },
  violet: {
    gradient: 'from-violet-900/50 to-[#161b22]/80',
    border: 'border-violet-500/10',
    iconBg: 'bg-violet-600',
    shadow: 'shadow-violet-600/20',
  },
  amber: {
    gradient: 'from-amber-900/50 to-[#161b22]/80',
    border: 'border-amber-500/10',
    iconBg: 'bg-amber-600',
    shadow: 'shadow-amber-600/20',
  },
};

// 진행률 링 (SVG)
const RING_CIRCUMFERENCE = 2 * Math.PI * 14; // r=14

function ProgressRing({ percent }: { percent: number }) {
  const offset = RING_CIRCUMFERENCE * (1 - percent / 100);
  return (
    <svg
      className="w-10 h-10 mx-auto"
      viewBox="0 0 36 36"
      style={{ transform: 'rotate(-90deg)' }}
    >
      <circle cx="18" cy="18" r="14" fill="none" stroke="#21262d" strokeWidth="3" />
      <circle
        cx="18"
        cy="18"
        r="14"
        fill="none"
        stroke="#388bfd"
        strokeWidth="3"
        strokeDasharray={RING_CIRCUMFERENCE}
        strokeDashoffset={offset}
        strokeLinecap="round"
      />
    </svg>
  );
}

// 논술 과목 카드
function SubjectCard({
  subject,
  onClick,
}: {
  subject: Subject;
  onClick: () => void;
}) {
  const style = SUBJECT_STYLES[subject.colorClass] ?? SUBJECT_STYLES['blue'];
  const progress =
    subject.totalQuestions > 0
      ? Math.round((subject.completedQuestions / subject.totalQuestions) * 100)
      : 0;
  const fileCount = subject.files.length;
  const extra = progress === 0 ? ' · 준비중' : '';

  return (
    <div
      className={`bg-gradient-to-br ${style.gradient} rounded-2xl p-4 border ${style.border} cursor-pointer active:scale-[0.97] transition-transform`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className="flex items-center gap-3.5">
        <div
          className={`w-12 h-12 rounded-xl ${style.iconBg} flex items-center justify-center text-sm font-black text-white shadow-lg ${style.shadow} shrink-0`}
        >
          {subject.shortName}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-white text-[15px]">{subject.name}</p>
          <p className="text-[11px] text-[#8b949e] mt-0.5">
            {fileCount} 파일 · {subject.totalQuestions} 설문{extra}
          </p>
          {subject.totalQuestions > 0 && (
            <div className="flex items-center gap-2 mt-2">
              <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="text-[10px] text-[#8b949e]">
                {subject.completedQuestions}/{subject.totalQuestions}
              </span>
            </div>
          )}
        </div>
        <svg
          className="w-4 h-4 text-white/20 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>
  );
}

// 복습 카드 (가로 스크롤용)
const REVIEW_LEVEL_LABELS = ['1일', '3일', '7일', '14일', '30일'];

function ReviewCard({
  item,
  onClick,
}: {
  item: ReviewItem;
  onClick: () => void;
}) {
  const style = SUBJECT_STYLES[item.colorClass] ?? SUBJECT_STYLES['blue'];
  const levelLabel = REVIEW_LEVEL_LABELS[item.reviewLevel] ?? `Lv.${item.reviewLevel + 1}`;

  return (
    <div
      className={`shrink-0 w-40 bg-gradient-to-br ${style.gradient} rounded-xl p-3 border ${style.border} cursor-pointer active:scale-[0.97] transition-transform`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${style.iconBg} text-white`}>
          {item.subjectName}
        </span>
        {item.isWeakMarked && <span className="text-[10px]" title="취약 마킹">&#x1F6A9;</span>}
      </div>
      <p className="text-xs font-semibold text-white truncate">{item.questionTitle}</p>
      <div className="flex items-center justify-between mt-2">
        <span className="text-[10px] text-[#8b949e]">{levelLabel} 복습</span>
        {item.daysOverdue > 0 && (
          <span className="text-[10px] text-red-400 font-bold">+{item.daysOverdue}일</span>
        )}
      </div>
    </div>
  );
}

const ESSAY_SUBJECT_IDS = ['2nd_minso_2026', '2nd_minbeop_2026', '2nd_hyung_2026', '2nd_hyungso_2026', '2nd_budeung_2026', 'test_subject'];

export function HomeScreen({ onSelectSubject, onOpenSettings }: HomeScreenProps) {
  const { playSelected } = usePlayer();
  const essaySubjects = subjects.filter((s) => ESSAY_SUBJECT_IDS.includes(s.id));

  // 복습 추천 데이터
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([]);
  const [reviewDueCount, setReviewDueCount] = useState(0);
  const [showAllReview, setShowAllReview] = useState(false);

  useEffect(() => {
    const summary = getReviewSummary();
    setReviewItems(summary.items);
    setReviewDueCount(summary.overdueCount);
  }, []);

  // 통계 계산
  const totalQuestions = subjects.reduce((sum, s) => sum + s.totalQuestions, 0);
  const completedQuestions = subjects.reduce((sum, s) => sum + s.completedQuestions, 0);
  const overallProgress =
    totalQuestions > 0 ? Math.round((completedQuestions / totalQuestions) * 100) : 0;

  // D-day 계산
  const [ddayStr, setDdayStr] = useState<string>('');
  const [examDateStr, setExamDateStr] = useState<string | null>(null);
  useEffect(() => {
    const dateStr = loadExamDate();
    setExamDateStr(dateStr);
    const days = calcDday(dateStr);
    setDdayStr(formatDday(days));
  }, []);

  return (
    <div
      className="absolute inset-0 flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1e3a5f 0%, #0d1117 50%)' }}
    >
      {/* 헤더 */}
      <header className="px-5 pt-5 pb-2 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white">
            Law<span className="text-blue-400">Ear</span>
          </h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-[11px] text-[#8b949e]">법무사 2차 · TTS 학습</p>
            {ddayStr && (
              <span
                className={`text-[11px] font-bold px-1.5 py-0.5 rounded-md ${
                  ddayStr === 'D-Day'
                    ? 'bg-red-500/20 text-red-400'
                    : ddayStr.startsWith('D+')
                    ? 'bg-gray-500/20 text-gray-400'
                    : 'bg-blue-500/20 text-blue-400'
                }`}
              >
                {ddayStr}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* 웨이브 (항상 꺼짐 상태 — 홈에서는 재생 없음) */}
          <div className="flex items-end gap-[1px] h-[10px] opacity-30">
            {[0, 1, 2, 3].map((i) => (
              <span
                key={i}
                className="inline-block w-[2.5px] rounded-sm bg-[#388bfd]"
                style={{ height: '3px' }}
              />
            ))}
          </div>
          <button
            className="w-8 h-8 rounded-full bg-[#161b22] border border-[#21262d] flex items-center justify-center"
            onClick={onOpenSettings}
            aria-label="설정"
          >
            <svg
              className="w-4 h-4 text-[#8b949e]"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.573-1.066z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </div>
      </header>

      {/* 통계 카드 3개 */}
      <div className="px-5 py-3 grid grid-cols-3 gap-2.5 shrink-0">
        {/* 전체 진행 */}
        <div className="bg-[#161b22]/60 border border-[#21262d] rounded-xl p-3 text-center">
          <ProgressRing percent={overallProgress} />
          <p className="text-sm font-bold text-white mt-1">{overallProgress}%</p>
          <p className="text-[10px] text-[#8b949e]">전체 진행</p>
        </div>
        {/* 완료 설문 */}
        <div className="bg-[#161b22]/60 border border-[#21262d] rounded-xl p-3 text-center">
          <p className="text-2xl font-bold text-blue-400">{completedQuestions}</p>
          <p className="text-[10px] text-[#8b949e] mt-0.5">완료 설문</p>
          <p className="text-[10px] text-[#8b949e] opacity-50">/ {totalQuestions}</p>
        </div>
        {/* D-day */}
        <div
          className="bg-[#161b22]/60 border border-[#21262d] rounded-xl p-3 text-center cursor-pointer active:scale-[0.97] transition-transform"
          onClick={onOpenSettings}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && onOpenSettings()}
          aria-label="시험 날짜 설정"
        >
          {ddayStr ? (
            <>
              <p
                className={`text-2xl font-bold ${
                  ddayStr === 'D-Day'
                    ? 'text-red-400'
                    : ddayStr.startsWith('D+')
                    ? 'text-gray-400'
                    : 'text-blue-400'
                }`}
              >
                {ddayStr}
              </p>
              {examDateStr && (
                <p className="text-[10px] text-[#8b949e]/60 mt-0.5 truncate">
                  {examDateStr.slice(5).replace('-', '/')}
                </p>
              )}
            </>
          ) : (
            <>
              <p className="text-xl font-bold text-[#8b949e]/40">D-?</p>
              <p className="text-[10px] text-[#8b949e]/40 mt-0.5">날짜 설정</p>
            </>
          )}
        </div>
      </div>

      {/* 스크롤 영역 */}
      <div className="flex-1 overflow-y-auto px-5 pb-24 space-y-2.5">
        {/* 복습 추천 섹션 */}
        {reviewItems.length > 0 && (
          <div className="pt-1">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] font-bold text-[#8b949e]/60 uppercase tracking-widest">
                오늘의 복습 ({reviewDueCount}개)
              </p>
              {reviewItems.length > 10 && (
                <button
                  className="text-[10px] text-blue-400 font-medium"
                  onClick={() => setShowAllReview(!showAllReview)}
                >
                  {showAllReview ? '접기' : `더보기 (${reviewItems.length})`}
                </button>
              )}
            </div>
            <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-hide">
              {(showAllReview ? reviewItems : reviewItems.slice(0, 10)).map((item) => (
                <ReviewCard
                  key={item.questionId}
                  item={item}
                  onClick={() => {
                    playSelected([{ subjectId: item.subjectId, fileId: item.fileId, questionId: item.questionId }]);
                  }}
                />
              ))}
            </div>
            {reviewItems.length > 1 && (
              <button
                className="w-full mt-1 py-2 rounded-xl bg-blue-600/20 border border-blue-500/20 text-blue-400 text-xs font-bold active:scale-[0.98] transition-transform"
                onClick={() => {
                  const playlist = reviewItems.map((item) => ({
                    subjectId: item.subjectId,
                    fileId: item.fileId,
                    questionId: item.questionId,
                  }));
                  playSelected(playlist);
                }}
              >
                모두 복습하기
              </button>
            )}
          </div>
        )}

        {/* 논술 5과목 */}
        <p className="text-[10px] font-bold text-[#8b949e]/60 uppercase tracking-widest pt-1 pb-1">
          논술 5과목
        </p>
        {essaySubjects.map((subject) => (
          <SubjectCard
            key={subject.id}
            subject={subject}
            onClick={() => onSelectSubject(subject.id)}
          />
        ))}

        {/* 서류 과목 */}
        <p className="text-[10px] font-bold text-[#8b949e]/60 uppercase tracking-widest pt-3 pb-1">
          서류 과목
        </p>
        <div className="bg-[#161b22]/40 rounded-2xl p-4 border border-[#21262d]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-400">
              민서
            </div>
            <div>
              <p className="text-sm text-gray-400">민사서류</p>
              <p className="text-[11px] text-[#8b949e]/50">2순위 · 준비중</p>
            </div>
          </div>
        </div>
        <div className="bg-[#161b22]/40 rounded-2xl p-4 border border-[#21262d]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-400">
              등서
            </div>
            <div>
              <p className="text-sm text-gray-400">부동산등기서류</p>
              <p className="text-[11px] text-[#8b949e]/50">보류 · 준비중</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
