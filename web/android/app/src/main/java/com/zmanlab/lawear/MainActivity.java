package com.zmanlab.lawear;

import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.util.Log;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;
import com.zmanlab.lawear.plugins.ttsfile.TTSFilePlugin;

public class MainActivity extends BridgeActivity {
    private PowerManager.WakeLock wakeLock;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(TTSFilePlugin.class);
        super.onCreate(savedInstanceState);

        // WebView 백그라운드 JS 실행 유지
        WebView webView = getBridge().getWebView();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            webView.setRendererPriorityPolicy(
                WebView.RENDERER_PRIORITY_IMPORTANT, false);
        }

        // Partial WakeLock — CPU 깨우기용 (TTS가 백그라운드에서 끊기지 않도록)
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "lawear:tts");
            wakeLock.acquire();

            Log.d("TTSFile", "[Battery] 자동 요청 비활성화 — 설정에서 수동 활성화 가능");
        }

        // AudioFocus, silencePlayer 제거:
        // TtsPlaybackService (Foreground Service)가 오디오 세션을 직접 관리.
        // Activity에서 AudioFocus를 잡으면 Service와 충돌할 수 있음.
    }

    @Override
    public void onStop() {
        super.onStop();
        // Capacitor가 WebView를 멈추므로 즉시 다시 깨움 — JS 콜백 수신 유지
        getBridge().getWebView().onResume();
        getBridge().getWebView().resumeTimers();
    }

    @Override
    public void onDestroy() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        super.onDestroy();
    }
}
