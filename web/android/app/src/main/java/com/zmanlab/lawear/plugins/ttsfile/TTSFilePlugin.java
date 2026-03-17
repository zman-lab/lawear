package com.zmanlab.lawear.plugins.ttsfile;

import android.content.Intent;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

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
 */
@CapacitorPlugin(name = "TTSFile")
public class TTSFilePlugin extends Plugin {

    private TextToSpeech tts;
    private final CountDownLatch ttsReady = new CountDownLatch(1);
    private boolean ttsInitialized = false;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override
    public void load() {
        tts = new TextToSpeech(getContext(), status -> {
            if (status == TextToSpeech.SUCCESS) {
                tts.setLanguage(Locale.KOREAN);
                ttsInitialized = true;
            }
            ttsReady.countDown();
        });
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
    }
}
