package com.zmanlab.lawear;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;
import com.zmanlab.lawear.plugins.ttsfile.TTSFilePlugin;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(TTSFilePlugin.class);
        super.onCreate(savedInstanceState);
    }
}
