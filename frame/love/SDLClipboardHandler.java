// Altered SDL source: tolerate Android environments without a clipboard service.
// Original: love2d/love-android 55feb38fa144f4734c26742389f279fb07d955c0
// love/src/jni/SDL2/android-project/app/src/main/java/org/libsdl/app/SDLActivity.java
// Upstream file SHA-256: 88e49e925b1c89f593fcd404925a43762a194ba108c48bb5140e794c292358fd
// See LICENSE.SDL.txt for the original SDL license.
package org.libsdl.app;
import android.content.ClipboardManager;
import android.content.ClipData;
import android.content.Context;

class SDLClipboardHandler implements
    ClipboardManager.OnPrimaryClipChangedListener {

    protected ClipboardManager mClipMgr;

    SDLClipboardHandler() {
       mClipMgr = (ClipboardManager) SDL.getContext().getSystemService(Context.CLIPBOARD_SERVICE);
       if (mClipMgr != null) mClipMgr.addPrimaryClipChangedListener(this);
    }

    public boolean clipboardHasText() {
       return mClipMgr != null && mClipMgr.hasPrimaryClip();
    }

    public String clipboardGetText() {
        if (mClipMgr == null) return null;
        ClipData clip = mClipMgr.getPrimaryClip();
        if (clip != null) {
            ClipData.Item item = clip.getItemAt(0);
            if (item != null) {
                CharSequence text = item.getText();
                if (text != null) {
                    return text.toString();
                }
            }
        }
        return null;
    }

    public void clipboardSetText(String string) {
       if (mClipMgr == null) return;
       mClipMgr.removePrimaryClipChangedListener(this);
       ClipData clip = ClipData.newPlainText(null, string);
       mClipMgr.setPrimaryClip(clip);
       mClipMgr.addPrimaryClipChangedListener(this);
    }

    @Override
    public void onPrimaryClipChanged() {
        SDLActivity.onNativeClipboardChanged();
    }
}

