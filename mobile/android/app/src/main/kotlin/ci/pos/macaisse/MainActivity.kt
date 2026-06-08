package ci.pos.macaisse

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.android.RenderMode

class MainActivity : FlutterActivity() {
    // TextureView avoids BLASTBufferQueue overflow on Huawei/some Android devices
    // where SurfaceView saturates the buffer queue (max frames 4 max:2+2 error).
    override fun getRenderMode(): RenderMode = RenderMode.texture
}
