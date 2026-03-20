package com.zmanlab.lawear.services;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.os.Binder;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import com.zmanlab.lawear.MainActivity;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * TtsPlaybackService — Foreground Service로 TTS 재생
 *
 * Android 14에서 Activity Context로 생성한 TTS 인스턴스는
 * 백그라운드 진입 후 ~5초 뒤 강제 중단됨.
 * Service Context로 TTS를 초기화해야 백그라운드에서도 재생 유지.
 */
public class TtsPlaybackService extends Service {

    private static final String TAG = "TtsPlaybackService";
    public static final String CHANNEL_ID = "lawear_tts_channel";
    private static final int NOTIFICATION_ID = 1001;

    // Binder — Plugin이 직접 메서드 호출
    public class LocalBinder extends Binder {
        public TtsPlaybackService getService() {
            return TtsPlaybackService.this;
        }
    }

    private final IBinder binder = new LocalBinder();

    // TTS
    private TextToSpeech tts;
    private volatile boolean ttsReady = false;

    // AudioFocus — 알림 소리 등에 의해 TTS가 중단되지 않도록
    private AudioManager audioManager;
    private AudioFocusRequest audioFocusRequest;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    // 시퀀스 상태
    private volatile boolean sequencePlaying = false;
    private volatile int sequenceIndex = -1;
    private List<String> sequenceTexts = new ArrayList<>();
    private float sequenceRate = 1.0f;

    // 콜백 인터페이스 — Plugin → JS 이벤트 전달
    public interface SequenceCallback {
        void onSentenceStart(int index);
        void onSentenceDone(int index);
        void onSequenceComplete(int index);
    }

    private SequenceCallback callback;

    // ──────────────────────────────────────────────────────────────────────

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "onCreate");

        // 알림 채널 생성 (API 26+)
        createNotificationChannel();

        // Foreground Service 시작 (알림 필수)
        Notification notification = buildNotification("학습 준비 중", 0);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            // Android 14+: foregroundServiceType 명시 필수
            startForeground(NOTIFICATION_ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }

        // AudioFocus 확보 — 알림 소리에 TTS가 중단되지 않도록
        audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
        if (audioManager != null) {
            AudioAttributes attrs = new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build();
            audioFocusRequest = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                    .setAudioAttributes(attrs)
                    .setWillPauseWhenDucked(false)
                    .setAcceptsDelayedFocusGain(true)
                    .setOnAudioFocusChangeListener(focusChange -> {
                        // 어떤 포커스 변경이든 TTS 재생을 중단하지 않음
                        // 화면 꺼짐/알림 등으로 포커스 잃어도 즉시 재요청
                        Log.d(TAG, "AudioFocus change: " + focusChange);
                        if (focusChange == AudioManager.AUDIOFOCUS_LOSS
                                || focusChange == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) {
                            // 즉시 재요청 (딜레이 없음)
                            mainHandler.post(() -> {
                                if (sequencePlaying && audioManager != null) {
                                    audioManager.requestAudioFocus(audioFocusRequest);
                                }
                            });
                        }
                    }, mainHandler)
                    .build();
            audioManager.requestAudioFocus(audioFocusRequest);
        }

        // TTS 초기화 — Service Context 사용 (핵심!)
        tts = new TextToSpeech(this, status -> {
            if (status == TextToSpeech.SUCCESS) {
                tts.setLanguage(Locale.KOREAN);
                ttsReady = true;
                Log.i(TAG, "TTS initialized (Service Context)");
            } else {
                Log.e(TAG, "TTS initialization failed: " + status);
            }
        });
    }

    @Override
    public IBinder onBind(Intent intent) {
        return binder;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        Log.i(TAG, "onTaskRemoved — app destroyed, stopping service");
        stopSelf();
    }

    @Override
    public void onDestroy() {
        Log.i(TAG, "onDestroy");
        if (tts != null) {
            tts.stop();
            tts.shutdown();
        }
        super.onDestroy();
    }

    // ── 공개 API ───────────────────────────────────────────────────────────

    public void setCallback(SequenceCallback cb) {
        this.callback = cb;
    }

    /**
     * 시퀀스 재생 시작
     *
     * @param texts      문장 배열
     * @param startIndex 시작 인덱스
     * @param rate       재생 속도
     */
    public void speakSequence(List<String> texts, int startIndex, float rate) {
        if (!ttsReady) {
            Log.e(TAG, "speakSequence: TTS not ready");
            return;
        }

        // 기존 재생 중단
        stopInternal();

        sequenceTexts = new ArrayList<>(texts);
        sequenceRate = rate;
        sequencePlaying = true;

        tts.setSpeechRate(rate);
        speakAtIndex(startIndex);
    }

    public void stop() {
        stopInternal();
        updateNotification("학습 일시정지", sequenceIndex);
    }

    public void updateRate(float rate) {
        sequenceRate = rate;
        tts.setSpeechRate(rate);
        // 현재 문장은 기존 rate로 끝까지, 다음 문장부터 적용
    }

    public void jumpToIndex(int index) {
        if (sequenceTexts.isEmpty()) return;
        if (index < 0 || index >= sequenceTexts.size()) {
            Log.w(TAG, "jumpToIndex: index out of range " + index);
            return;
        }
        tts.stop();
        speakAtIndex(index);
    }

    public boolean isTtsReady() {
        return ttsReady;
    }

    public int getCurrentIndex() {
        return sequenceIndex;
    }

    // ── 내부 구현 ──────────────────────────────────────────────────────────

    private void stopInternal() {
        sequencePlaying = false;
        sequenceIndex = -1;
        if (tts != null) {
            tts.stop();
        }
    }

    private void speakAtIndex(int index) {
        if (!sequencePlaying || index >= sequenceTexts.size()) {
            // 시퀀스 완료
            sequencePlaying = false;
            updateNotification("학습 완료", index);
            if (callback != null) {
                callback.onSequenceComplete(index);
            }
            return;
        }

        sequenceIndex = index;
        String text = sequenceTexts.get(index);
        String utteranceId = "seq_" + index + "_" + System.currentTimeMillis();

        // 알림 업데이트
        updateNotification("학습 중", index + 1);

        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override
            public void onStart(String id) {
                if (id.equals(utteranceId)) {
                    Log.d(TAG, "onStart index=" + index);
                    if (callback != null) {
                        callback.onSentenceStart(index);
                    }
                }
            }

            @Override
            public void onDone(String id) {
                if (id.equals(utteranceId) && sequencePlaying) {
                    Log.d(TAG, "onDone index=" + index);
                    if (callback != null) {
                        callback.onSentenceDone(index);
                    }
                    // JS 의존 없이 네이티브에서 바로 다음 문장 재생
                    speakAtIndex(index + 1);
                }
            }

            @Override
            public void onError(String id) {
                if (id.equals(utteranceId) && sequencePlaying) {
                    Log.w(TAG, "onError index=" + index + " — skipping to next");
                    // 에러 시에도 다음 문장으로
                    speakAtIndex(index + 1);
                }
            }
        });

        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId);
    }

    // ── 알림 ───────────────────────────────────────────────────────────────

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "LawEar TTS",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("법무사 시험 학습 TTS 재생");
            channel.setShowBadge(false);
            channel.setSound(null, null);

            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    private Notification buildNotification(String statusText, int sentenceNum) {
        Intent launchIntent = new Intent(this, MainActivity.class);
        launchIntent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, 0, launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        String contentText = sentenceNum > 0
                ? statusText + " (" + sentenceNum + "번 문장)"
                : statusText;

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("LawEar 학습 중")
                .setContentText(contentText)
                .setSmallIcon(android.R.drawable.ic_media_play)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setSilent(true)
                .build();
    }

    private void updateNotification(String statusText, int sentenceNum) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm != null) {
            nm.notify(NOTIFICATION_ID, buildNotification(statusText, sentenceNum));
        }
    }
}
