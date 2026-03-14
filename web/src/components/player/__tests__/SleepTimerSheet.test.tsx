import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { SleepTimerSheet } from '../SleepTimerSheet';
import type { PlayerState } from '../../../types';

// ── usePlayer mock ──────────────────────────────────────────────────────────
const mockSetSleepTimer = vi.fn();
const mockOnClose = vi.fn();

const defaultPlayerState: PlayerState = {
  isPlaying: false,
  currentSubjectId: null,
  currentFileId: null,
  currentQuestionId: null,
  currentSentenceIndex: 0,
  speed: 1.0,
  repeatMode: 'stop-after-one',
  sleepTimer: null,
  selectedVoiceURI: null,
  level: 1,
  viewMode: 'reader',
};

interface MockPlayerValue {
  state: PlayerState;
  setSleepTimer: typeof mockSetSleepTimer;
  sleepTimerRemaining: number | null;
}

let mockPlayerValue: MockPlayerValue = {
  state: { ...defaultPlayerState },
  setSleepTimer: mockSetSleepTimer,
  sleepTimerRemaining: null,
};

vi.mock('../../../context/PlayerContext', () => ({
  usePlayer: () => mockPlayerValue,
}));

// ── jsdom scroll 동작 보완 ──────────────────────────────────────────────────
// jsdom은 실제 스크롤이 안 되므로 scrollTo를 모킹
beforeEach(() => {
  Element.prototype.scrollTo = vi.fn(function (this: Element, options?: ScrollToOptions) {
    if (options && typeof options.top === 'number') {
      Object.defineProperty(this, 'scrollTop', {
        value: options.top,
        writable: true,
        configurable: true,
      });
      // scroll 이벤트 발생
      this.dispatchEvent(new Event('scroll'));
    }
  }) as unknown as typeof Element.prototype.scrollTo;

  mockSetSleepTimer.mockClear();
  mockOnClose.mockClear();
  mockPlayerValue = {
    state: { ...defaultPlayerState },
    setSleepTimer: mockSetSleepTimer,
    sleepTimerRemaining: null,
  };
});

// ── 테스트 ──────────────────────────────────────────────────────────────────

describe('SleepTimerSheet', () => {
  // 1. 기본 렌더링
  it('시트가 열릴 때 프리셋 버튼들이 표시된다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);

    expect(screen.getByText('슬립 타이머')).toBeInTheDocument();
    expect(screen.getByText('5분')).toBeInTheDocument();
    expect(screen.getByText('10분')).toBeInTheDocument();
    expect(screen.getByText('15분')).toBeInTheDocument();
    expect(screen.getByText('30분')).toBeInTheDocument();
    expect(screen.getByText('1시간')).toBeInTheDocument();
    expect(screen.getByText('직접설정')).toBeInTheDocument();
    expect(screen.getByText('취소')).toBeInTheDocument();
  });

  // isOpen=false일 때 렌더링 안 됨
  it('isOpen=false이면 아무것도 렌더링하지 않는다', () => {
    const { container } = render(<SleepTimerSheet isOpen={false} onClose={mockOnClose} />);
    expect(container.innerHTML).toBe('');
  });

  // 2. 프리셋 선택
  it.each([
    { label: '5분', seconds: 300 },
    { label: '10분', seconds: 600 },
    { label: '15분', seconds: 900 },
    { label: '30분', seconds: 1800 },
    { label: '1시간', seconds: 3600 },
  ])('프리셋 "$label" 클릭 시 $seconds초로 타이머 설정', ({ label, seconds }) => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(label));
    expect(mockSetSleepTimer).toHaveBeenCalledWith(seconds);
    expect(mockOnClose).toHaveBeenCalled();
  });

  // 3. 커스텀 모드 전환
  it('"직접설정" 클릭 시 스크롤 피커가 표시된다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('직접설정'));

    // 시간, 분, 초 라벨이 표시되어야 함
    expect(screen.getByText('시간')).toBeInTheDocument();
    expect(screen.getByText('분')).toBeInTheDocument();
    expect(screen.getByText('초')).toBeInTheDocument();
    // 뒤로, 시작 버튼
    expect(screen.getByText('뒤로')).toBeInTheDocument();
    expect(screen.getByText('시작')).toBeInTheDocument();
    // 프리셋 버튼은 사라짐
    expect(screen.queryByText('5분')).not.toBeInTheDocument();
  });

  // 4. 스크롤 피커 초기값 렌더링
  it('커스텀 모드에서 초기값이 올바르게 렌더링된다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('직접설정'));

    // 기본값: 0시 15분 0초 -> 분 피커에 15가 선택된 상태
    // aria-selected=true인 아이템 확인
    const selectedMinuteItem = screen.getByTestId('picker-item-분-15');
    expect(selectedMinuteItem).toHaveAttribute('aria-selected', 'true');

    const selectedHourItem = screen.getByTestId('picker-item-시간-0');
    expect(selectedHourItem).toHaveAttribute('aria-selected', 'true');

    const selectedSecondItem = screen.getByTestId('picker-item-초-0');
    expect(selectedSecondItem).toHaveAttribute('aria-selected', 'true');
  });

  // 5. 피커 아이템 클릭으로 값 변경
  it('피커 아이템 클릭 시 값이 변경된다', async () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('직접설정'));

    // 시간 피커에서 2 클릭
    const hourItem = screen.getByTestId('picker-item-시간-2');
    fireEvent.click(hourItem);

    // 클릭 후 시작 버튼 클릭하여 총 시간 확인
    // (2시 15분 0초 = 7200 + 900 = 8100초)
    await act(async () => {
      fireEvent.click(screen.getByTestId('start-btn'));
    });
    expect(mockSetSleepTimer).toHaveBeenCalledWith(8100);
  });

  // 6. 경계값 테스트 - 시간 범위
  it('시간 피커에 0~12 범위의 값이 존재한다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('직접설정'));

    expect(screen.getByTestId('picker-item-시간-0')).toBeInTheDocument();
    expect(screen.getByTestId('picker-item-시간-12')).toBeInTheDocument();
    expect(screen.queryByTestId('picker-item-시간-13')).not.toBeInTheDocument();
  });

  // 분 범위
  it('분 피커에 0~59 범위의 값이 존재한다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('직접설정'));

    expect(screen.getByTestId('picker-item-분-0')).toBeInTheDocument();
    expect(screen.getByTestId('picker-item-분-59')).toBeInTheDocument();
    expect(screen.queryByTestId('picker-item-분-60')).not.toBeInTheDocument();
  });

  // 초 범위
  it('초 피커에 0~59 범위의 값이 존재한다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('직접설정'));

    expect(screen.getByTestId('picker-item-초-0')).toBeInTheDocument();
    expect(screen.getByTestId('picker-item-초-59')).toBeInTheDocument();
    expect(screen.queryByTestId('picker-item-초-60')).not.toBeInTheDocument();
  });

  // 7. 0시 0분 0초 방지
  it('0시 0분 0초이면 시작 버튼이 비활성화된다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('직접설정'));

    // 기본값이 0시 15분 0초이므로, 분을 0으로 바꿔야 함
    const minuteZero = screen.getByTestId('picker-item-분-0');
    fireEvent.click(minuteZero);

    // 시작 버튼이 disabled
    const startBtn = screen.getByTestId('start-btn');
    expect(startBtn).toBeDisabled();

    // 클릭해도 setSleepTimer 호출 안 됨
    fireEvent.click(startBtn);
    expect(mockSetSleepTimer).not.toHaveBeenCalled();
  });

  // 8. backdrop 클릭 시 닫기
  it('backdrop 클릭 시 onClose가 호출된다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByTestId('sleep-timer-backdrop'));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  // 9. 취소 버튼
  it('취소 버튼 클릭 시 onClose가 호출되고 타이머 설정 안 됨', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByTestId('cancel-btn'));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
    expect(mockSetSleepTimer).not.toHaveBeenCalled();
  });

  // 10. 활성 타이머 표시
  it('타이머가 활성 상태이면 남은 시간과 해제 버튼이 표시된다', () => {
    mockPlayerValue = {
      state: {
        ...defaultPlayerState,
        sleepTimer: { endTime: Date.now() + 300000, totalSeconds: 300 },
      },
      setSleepTimer: mockSetSleepTimer,
      sleepTimerRemaining: 295,
    };

    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);

    expect(screen.getByTestId('active-timer-display')).toBeInTheDocument();
    expect(screen.getByText('타이머 활성')).toBeInTheDocument();
    expect(screen.getByTestId('timer-remaining')).toBeInTheDocument();
    expect(screen.getByText('해제')).toBeInTheDocument();
  });

  // 11. 해제 버튼 클릭
  it('해제 버튼 클릭 시 setSleepTimer(null)과 onClose가 호출된다', () => {
    mockPlayerValue = {
      state: {
        ...defaultPlayerState,
        sleepTimer: { endTime: Date.now() + 300000, totalSeconds: 300 },
      },
      setSleepTimer: mockSetSleepTimer,
      sleepTimerRemaining: 295,
    };

    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByTestId('cancel-timer-btn'));
    expect(mockSetSleepTimer).toHaveBeenCalledWith(null);
    expect(mockOnClose).toHaveBeenCalled();
  });

  // 12. 시트 열고 닫기 반복 시 커스텀 모드 초기화
  it('시트를 닫았다 열면 커스텀 모드가 초기화된다', () => {
    const { rerender } = render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);

    // 커스텀 모드 진입
    fireEvent.click(screen.getByText('직접설정'));
    expect(screen.getByText('뒤로')).toBeInTheDocument();

    // 시트 닫기
    rerender(<SleepTimerSheet isOpen={false} onClose={mockOnClose} />);

    // 시트 다시 열기
    rerender(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);

    // 프리셋 모드로 돌아와야 함
    expect(screen.getByText('5분')).toBeInTheDocument();
    expect(screen.queryByText('뒤로')).not.toBeInTheDocument();
  });

  // 13. 최대값 계산 (12시 59분 59초 = 46799초)
  it('12시 59분 59초는 46799초로 정확히 계산된다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('직접설정'));

    // 시간 12, 분 59, 초 59 선택
    fireEvent.click(screen.getByTestId('picker-item-시간-12'));
    fireEvent.click(screen.getByTestId('picker-item-분-59'));
    fireEvent.click(screen.getByTestId('picker-item-초-59'));

    fireEvent.click(screen.getByTestId('start-btn'));
    expect(mockSetSleepTimer).toHaveBeenCalledWith(46799);
  });

  // 14. 닫기 버튼 (헤더)
  it('헤더 닫기 버튼 클릭 시 onClose가 호출된다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByLabelText('닫기'));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  // 15. 뒤로 버튼으로 프리셋 모드 복귀
  it('뒤로 버튼 클릭 시 프리셋 모드로 돌아간다', () => {
    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);

    // 커스텀 모드 진입
    fireEvent.click(screen.getByText('직접설정'));
    expect(screen.queryByText('5분')).not.toBeInTheDocument();

    // 뒤로
    fireEvent.click(screen.getByTestId('back-btn'));
    expect(screen.getByText('5분')).toBeInTheDocument();
    expect(screen.getByText('직접설정')).toBeInTheDocument();
  });
});

describe('SleepTimerSheet - formatRemaining', () => {
  // formatRemaining은 컴포넌트 내부 함수이므로 렌더링을 통해 테스트
  it('시간이 포함된 남은 시간을 H:MM:SS 형식으로 표시한다', () => {
    mockPlayerValue = {
      state: {
        ...defaultPlayerState,
        sleepTimer: { endTime: Date.now() + 3661000, totalSeconds: 3661 },
      },
      setSleepTimer: mockSetSleepTimer,
      sleepTimerRemaining: 3661, // 1:01:01
    };

    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByTestId('timer-remaining').textContent).toBe('1:01:01');
  });

  it('시간 없이 남은 시간을 M:SS 형식으로 표시한다', () => {
    mockPlayerValue = {
      state: {
        ...defaultPlayerState,
        sleepTimer: { endTime: Date.now() + 65000, totalSeconds: 65 },
      },
      setSleepTimer: mockSetSleepTimer,
      sleepTimerRemaining: 65, // 1:05
    };

    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByTestId('timer-remaining').textContent).toBe('1:05');
  });

  it('1초 남았을 때 0:01로 표시한다', () => {
    mockPlayerValue = {
      state: {
        ...defaultPlayerState,
        sleepTimer: { endTime: Date.now() + 1000, totalSeconds: 1 },
      },
      setSleepTimer: mockSetSleepTimer,
      sleepTimerRemaining: 1,
    };

    render(<SleepTimerSheet isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByTestId('timer-remaining').textContent).toBe('0:01');
  });
});
