package com.zmanlab.lawear;

import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;
import com.zmanlab.lawear.plugins.ttsfile.TTSFilePlugin;

public class MainActivity extends BridgeActivity {
    private PowerManager.WakeLock wakeLock;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(TTSFilePlugin.class);
        super.onCreate(savedInstanceState);

        // WebView 백그라운드 JS 실행 유지 — renderer priority를 높여서 시스템이 throttle하지 않도록
        WebView webView = getBridge().getWebView();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            webView.setRendererPriorityPolicy(
                WebView.RENDERER_PRIORITY_IMPORTANT, false);
        }

        // Partial WakeLock — 화면 꺼져도 CPU 유지 (TTS onEnd 콜백 수신용)
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "lawear:tts");
            wakeLock.acquire();
        }
    }

    @Override
    public void onDestroy() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        super.onDestroy();
    }
}
