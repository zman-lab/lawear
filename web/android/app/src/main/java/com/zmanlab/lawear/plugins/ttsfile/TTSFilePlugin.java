package com.zmanlab.lawear.plugins.ttsfile;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.IBinder;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.util.Log;
import android.view.WindowManager;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.zmanlab.lawear.services.TtsPlaybackService;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * TTSFile Capacitor Plugin
 *
 * Android TextToSpeech.synthesizeToFile() 래핑.
 * TTS 텍스트를 WAV 파일로 저장하고, 설치된 TTS 엔진 목록을 반환한다.
 *
 * speakSequence / stopSequence / updateSequenceRate / jumpSequence 는
 * TtsPlaybackService (Foreground Service)에 위임 — 백그라운드 5초 컷 방지.
 */
@CapacitorPlugin(name = "TTSFile")
public class TTSFilePlugin extends Plugin {

    private static final String TAG = "TTSFilePlugin";

    // synthesizeToFile 전용 TTS (Plugin Context — 파일 저장 용도)
    private TextToSpeech tts;
    private final CountDownLatch ttsReady = new CountDownLatch(1);
    private boolean ttsInitialized = false;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    // ── TtsPlaybackService 바인딩 ─────────────────────────────────────────

    private TtsPlaybackService playbackService;
    private boolean serviceBound = false;
    private PluginCall sequenceCall = null;

    private final ServiceConnection serviceConnection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder binder) {
            TtsPlaybackService.LocalBinder lb = (TtsPlaybackService.LocalBinder) binder;
            playbackService = lb.getService();
            serviceBound = true;
            Log.i(TAG, "TtsPlaybackService connected");

            // 콜백 등록 — Service → Plugin → JS
            playbackService.setCallback(new TtsPlaybackService.SequenceCallback() {
                @Override
                public void onSentenceStart(int index) {
                    if (sequenceCall != null) {
                        JSObject ev = new JSObject();
                        ev.put("event", "start");
                        ev.put("index", index);
                        sequenceCall.resolve(ev);
                    }
                }

                @Override
                public void onSentenceDone(int index) {
                    // JS에는 start/complete 이벤트만 전달 (done은 내부 처리)
                }

                @Override
                public void onSequenceComplete(int completedIndex) {
                    if (sequenceCall != null) {
                        JSObject ev = new JSObject();
                        ev.put("event", "complete");
                        ev.put("index", completedIndex);
                        sequenceCall.resolve(ev);
                        sequenceCall = null;
                    }
                }
            });
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            playbackService = null;
            serviceBound = false;
            Log.w(TAG, "TtsPlaybackService disconnected");
        }
    };

    // ──────────────────────────────────────────────────────────────────────

    @Override
    public void load() {
        // synthesizeToFile 용 TTS (Plugin Context)
        tts = new TextToSpeech(getContext(), status -> {
            if (status == TextToSpeech.SUCCESS) {
                tts.setLanguage(Locale.KOREAN);
                ttsInitialized = true;
            }
            ttsReady.countDown();
        });

        // TtsPlaybackService 시작 + 바인딩
        Intent serviceIntent = new Intent(getContext(), TtsPlaybackService.class);
        getContext().startForegroundService(serviceIntent);
        getContext().bindService(serviceIntent, serviceConnection, Context.BIND_AUTO_CREATE);
    }

    // ── synthesizeToFile ──────────────────────────────────────────────────────

    @PluginMethod
    public void synthesizeToFile(PluginCall call) {
        String text = call.getString("text");
        String fileName = call.getString("fileName");
        float rate = call.getFloat("rate", 1.0f);
        String voiceName = call.getString("voiceName");

        if (text == null || fileName == null) {
            call.reject("text and fileName are required");
            return;
        }

        executor.execute(() -> {
            try {
                if (!ttsReady.await(10, TimeUnit.SECONDS) || !ttsInitialized) {
                    call.reject("TTS initialization failed");
                    return;
                }

                // 음성 설정
                tts.setSpeechRate(rate);
                if (voiceName != null) {
                    for (Voice voice : tts.getVoices()) {
                        if (voice.getName().equals(voiceName)) {
                            tts.setVoice(voice);
                            break;
                        }
                    }
                }

                File filesDir = getContext().getFilesDir();
                File outputFile = new File(filesDir, fileName);

                int maxLen = tts.getMaxSpeechInputLength();
                if (maxLen <= 0) maxLen = 4000;

                if (text.length() <= maxLen) {
                    // 단일 합성
                    synthesizeSingle(text, outputFile);
                } else {
                    // 청크 분할 + 합성 + WAV 결합
                    synthesizeChunked(text, outputFile, maxLen);
                }

                JSObject ret = new JSObject();
                ret.put("filePath", fileName);
                ret.put("size", outputFile.length());
                call.resolve(ret);

            } catch (Exception e) {
                call.reject("Synthesis failed: " + e.getMessage());
            }
        });
    }

    private void synthesizeSingle(String text, File outputFile) throws Exception {
        outputFile.getParentFile().mkdirs();
        CountDownLatch latch = new CountDownLatch(1);
        final Exception[] error = { null };

        String utteranceId = "synth_" + System.currentTimeMillis();

        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) {}
            @Override public void onDone(String id) {
                if (id.equals(utteranceId)) latch.countDown();
            }
            @Override public void onError(String id) {
                if (id.equals(utteranceId)) {
                    error[0] = new Exception("TTS synthesis error");
                    latch.countDown();
                }
            }
        });

        int result = tts.synthesizeToFile(text, null, outputFile, utteranceId);
        if (result != TextToSpeech.SUCCESS) {
            throw new Exception("synthesizeToFile returned error code: " + result);
        }

        if (!latch.await(120, TimeUnit.SECONDS)) {
            throw new Exception("Synthesis timeout (120s)");
        }
        if (error[0] != null) throw error[0];
    }

    private void synthesizeChunked(String text, File outputFile, int maxLen) throws Exception {
        List<String> chunks = splitText(text, maxLen);
        File tempDir = new File(getContext().getCacheDir(), "tts_chunks");
        tempDir.mkdirs();

        List<File> tempFiles = new ArrayList<>();

        try {
            for (int i = 0; i < chunks.size(); i++) {
                File tempFile = new File(tempDir, "chunk_" + i + ".wav");
                synthesizeSingle(chunks.get(i), tempFile);
                tempFiles.add(tempFile);
            }

            if (tempFiles.size() == 1) {
                outputFile.getParentFile().mkdirs();
                tempFiles.get(0).renameTo(outputFile);
            } else {
                concatenateWavFiles(tempFiles, outputFile);
            }
        } finally {
            for (File f : tempFiles) f.delete();
            tempDir.delete();
        }
    }

    private List<String> splitText(String text, int maxLen) {
        List<String> chunks = new ArrayList<>();
        int start = 0;
        while (start < text.length()) {
            int end = Math.min(start + maxLen, text.length());
            if (end < text.length()) {
                // 문장 경계에서 분할 (마지막 마침표/물음표/느낌표)
                int boundary = -1;
                for (int i = end; i > start + maxLen / 2; i--) {
                    char c = text.charAt(i);
                    if (c == '.' || c == '?' || c == '!' || c == '\n') {
                        boundary = i + 1;
                        break;
                    }
                }
                if (boundary > start) {
                    end = boundary;
                }
            }
            chunks.add(text.substring(start, end).trim());
            start = end;
        }
        return chunks;
    }

    private void concatenateWavFiles(List<File> inputs, File output) throws IOException {
        output.getParentFile().mkdirs();

        // 첫 파일 헤더에서 오디오 포맷 읽기
        DataInputStream header = new DataInputStream(new FileInputStream(inputs.get(0)));
        byte[] riff = new byte[44];
        header.readFully(riff);
        header.close();

        short numChannels = (short) ((riff[22] & 0xFF) | ((riff[23] & 0xFF) << 8));
        int sampleRate = (riff[24] & 0xFF) | ((riff[25] & 0xFF) << 8) |
                          ((riff[26] & 0xFF) << 16) | ((riff[27] & 0xFF) << 24);
        short bitsPerSample = (short) ((riff[34] & 0xFF) | ((riff[35] & 0xFF) << 8));
        int byteRate = sampleRate * numChannels * bitsPerSample / 8;
        short blockAlign = (short) (numChannels * bitsPerSample / 8);

        // 전체 PCM 데이터 크기 계산
        long totalDataSize = 0;
        for (File f : inputs) {
            totalDataSize += f.length() - 44;
        }

        DataOutputStream out = new DataOutputStream(new FileOutputStream(output));

        // RIFF 헤더
        out.writeBytes("RIFF");
        writeLittleEndianInt(out, (int)(totalDataSize + 36));
        out.writeBytes("WAVE");

        // fmt 청크
        out.writeBytes("fmt ");
        writeLittleEndianInt(out, 16);
        writeLittleEndianShort(out, (short) 1); // PCM
        writeLittleEndianShort(out, numChannels);
        writeLittleEndianInt(out, sampleRate);
        writeLittleEndianInt(out, byteRate);
        writeLittleEndianShort(out, blockAlign);
        writeLittleEndianShort(out, bitsPerSample);

        // data 청크
        out.writeBytes("data");
        writeLittleEndianInt(out, (int) totalDataSize);

        // PCM 데이터 결합
        byte[] buffer = new byte[8192];
        for (File f : inputs) {
            FileInputStream fis = new FileInputStream(f);
            fis.skip(44);
            int read;
            while ((read = fis.read(buffer)) > 0) {
                out.write(buffer, 0, read);
            }
            fis.close();
        }

        out.close();
    }

    private void writeLittleEndianInt(DataOutputStream out, int value) throws IOException {
        out.write(value & 0xFF);
        out.write((value >> 8) & 0xFF);
        out.write((value >> 16) & 0xFF);
        out.write((value >> 24) & 0xFF);
    }

    private void writeLittleEndianShort(DataOutputStream out, short value) throws IOException {
        out.write(value & 0xFF);
        out.write((value >> 8) & 0xFF);
    }

    // ── speakSequence (TtsPlaybackService에 위임) ─────────────────────────

    @PluginMethod(returnType = PluginMethod.RETURN_CALLBACK)
    public void speakSequence(PluginCall call) {
        call.setKeepAlive(true);

        try {
            JSArray textsArr = call.getArray("texts");
            int startIndex = call.getInt("startIndex", 0);
            float rate = call.getFloat("rate", 1.0f);
            // 트랙 정보 (선택적) — 알림 제목에 표시됨
            // 형식: "민사소송법 · Case 01"
            String trackTitle = call.getString("trackTitle");

            if (textsArr == null || textsArr.length() == 0) {
                call.reject("texts array required");
                return;
            }

            if (!serviceBound || playbackService == null) {
                call.reject("TtsPlaybackService not ready");
                return;
            }

            List<String> texts = new ArrayList<>();
            for (int i = 0; i < textsArr.length(); i++) {
                texts.add(textsArr.getString(i));
            }

            // 트랙 정보가 있으면 Service에 전달 (알림 제목 업데이트)
            if (trackTitle != null && !trackTitle.isEmpty()) {
                playbackService.setTrackInfo(trackTitle);
            }

            sequenceCall = call;
            playbackService.speakSequence(texts, startIndex, rate);

        } catch (Exception e) {
            call.reject("speakSequence failed: " + e.getMessage());
        }
    }

    @PluginMethod
    public void stopSequence(PluginCall call) {
        if (serviceBound && playbackService != null) {
            playbackService.stop();
        }
        call.resolve();
    }

    @PluginMethod
    public void updateSequenceRate(PluginCall call) {
        float rate = call.getFloat("rate", 1.0f);
        if (serviceBound && playbackService != null) {
            playbackService.updateRate(rate);
        }
        call.resolve();
    }

    @PluginMethod
    public void jumpSequence(PluginCall call) {
        int index = call.getInt("index", 0);
        if (!serviceBound || playbackService == null) {
            call.reject("TtsPlaybackService not ready");
            return;
        }
        playbackService.jumpToIndex(index);
        call.resolve();
    }

    // ── getEngines ──────────────────────────────────────────────────────────

    @PluginMethod
    public void getEngines(PluginCall call) {
        try {
            ttsReady.await(5, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            call.reject("TTS not ready");
            return;
        }

        List<TextToSpeech.EngineInfo> engines = tts.getEngines();
        JSArray arr = new JSArray();
        for (TextToSpeech.EngineInfo engine : engines) {
            JSObject obj = new JSObject();
            obj.put("name", engine.name);
            obj.put("label", engine.label);
            arr.put(obj);
        }

        // 현재 기본 엔진
        String defaultEngine = tts.getDefaultEngine();

        JSObject ret = new JSObject();
        ret.put("engines", arr);
        ret.put("defaultEngine", defaultEngine);
        call.resolve(ret);
    }

    // ── setSleepMode (밝기 조절 + FLAG_KEEP_SCREEN_ON) ───────────────────────

    @PluginMethod
    public void setSleepMode(PluginCall call) {
        boolean enabled = Boolean.TRUE.equals(call.getBoolean("enabled", false));
        Activity activity = getActivity();
        if (activity == null) {
            call.resolve();
            return;
        }
        activity.runOnUiThread(() -> {
            WindowManager.LayoutParams lp = activity.getWindow().getAttributes();
            if (enabled) {
                // 슬립: 밝기 최소 (0.01f), 화면은 시스템에 의해 켜짐 유지
                lp.screenBrightness = 0.01f;
                activity.getWindow().setAttributes(lp);
                // FLAG_KEEP_SCREEN_ON 추가 (화면이 꺼지지 않도록)
                activity.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            } else {
                // 슬립 해제: 밝기 시스템 기본값 복원
                lp.screenBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE;
                activity.getWindow().setAttributes(lp);
                // FLAG_KEEP_SCREEN_ON 제거 (재생 정지 후 시스템이 화면 끌 수 있도록)
                activity.getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            }
            call.resolve();
        });
    }

    // ── openTTSSettings ───────────────────────────────────────────────────

    @PluginMethod
    public void openTTSSettings(PluginCall call) {
        try {
            Intent intent = new Intent("com.android.settings.TTS_SETTINGS");
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            call.resolve();
        } catch (Exception e) {
            call.reject("Failed to open TTS settings: " + e.getMessage());
        }
    }

    // ── cleanup ─────────────────────────────────────────────────────────────

    @Override
    protected void handleOnDestroy() {
        executor.shutdownNow();
        if (tts != null) {
            tts.stop();
            tts.shutdown();
        }
        if (serviceBound) {
            getContext().unbindService(serviceConnection);
            serviceBound = false;
        }
    }
}
