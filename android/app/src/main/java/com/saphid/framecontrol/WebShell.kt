package com.saphid.framecontrol

import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.ClipboardManager
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.graphics.Bitmap
import android.net.Uri
import android.webkit.JsPromptResult
import android.webkit.JsResult
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebStorage
import android.webkit.WebView
import android.webkit.URLUtil
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.saphid.framecontrol.core.FrameSettings
import com.saphid.framecontrol.core.AssetPolicy
import com.saphid.framecontrol.core.RemoteAsset
import com.saphid.framecontrol.core.TunnelDownload
import com.saphid.framecontrol.core.SaveTransfer
import com.saphid.framecontrol.core.InstallLink
import com.saphid.framecontrol.core.OriginPolicy
import java.io.ByteArrayInputStream
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * The Frame Control page, served by the server on the headset through this phone's
 * tunnel, in a web view. One web view per tunnel: its origin rules name that tunnel's
 * port, and the next connection gets a fresh one.
 *
 * window.frameApp (the bridge the desktop and iPhone apps provide) is injected only into
 * the tunnel's exact origin, through androidx.webkit's origin-checked message listener;
 * there's no addJavascriptInterface object for other pages or frames to reach.
 */
@SuppressLint("SetJavaScriptEnabled")
class WebShell(
    private val activity: MainActivity,
    val url: String,
    port: Int,
    private val scope: CoroutineScope,
    private val host: Host,
) {
    interface Host {
        val pairing: FrameSettings?
        fun showSetup()
        fun pickFiles(params: WebChromeClient.FileChooserParams, callback: ValueCallback<Array<Uri>>)
        fun takeInstallLinks(): List<InstallLink>
        fun historyChanged()
        fun rendererGone()
        fun fetchAsset(url: String): RemoteAsset
        fun createDocument(name: String, mime: String, result: (Uri?) -> Unit)
    }

    val policy = OriginPolicy(port)
    val view: WebView = WebView(activity)
    private var proxy: JavaScriptReplyProxy? = null
    private var installReady = false
    private val assetSlots = Semaphore(4)
    @Volatile private var destroyed = false
    private val saves = NativeSaves(activity)
    private var choosingDestination = false
    private val sessionKey = Uri.parse(url).getQueryParameter("key") ?: error("Missing UI key")

    init {
        // Each tunnel is a new origin; nothing from an earlier one is worth keeping.
        WebStorage.getInstance().deleteAllData()
        WebView.setWebContentsDebuggingEnabled(activity.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0)
        view.setBackgroundColor(activity.getColor(R.color.frame_background))
        view.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            setGeolocationEnabled(false)
            setSupportMultipleWindows(false)
            javaScriptCanOpenWindowsAutomatically = false
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
            // Only the app's own page loads here; links out go to the browser, which has its own checks.
            safeBrowsingEnabled = false
        }
        view.webViewClient = Client()
        view.webChromeClient = Chrome()
        view.setDownloadListener { link, _, disposition, mime, _ ->
            when {
                link.startsWith("blob:${policy.origin}/") -> view.evaluateJavascript(
                    "window.frameAndroidDownloadBlob?.(${JSONObject.quote(link)}).catch(e => alert(e.message))", null)
                policy.decide(link) == OriginPolicy.Decision.STAY -> download(link, URLUtil.guessFileName(link, disposition, mime), mime ?: "application/octet-stream")
                policy.decide(link) == OriginPolicy.Decision.EXTERNAL -> openExternal(link)
                else -> toast("Download origin blocked")
            }
        }
        // Without both (a WebView older than 2021), the page runs without the bridge: no
        // clipboard, saving or install links, the rest as normal.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER) &&
            WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            val rules = setOf(policy.origin)
            WebViewCompat.addWebMessageListener(view, "frameAppNative", rules) { _, message, origin, mainFrame, reply ->
                val sameOrigin = origin.scheme == "http" && origin.host == "127.0.0.1" && origin.port == port
                if (mainFrame && sameOrigin) receive(message, reply)
            }
            WebViewCompat.addDocumentStartJavaScript(view, activity.resources.openRawResource(R.raw.android_bridge).bufferedReader().use { it.readText() }, rules)
        }
        view.loadUrl(url)
    }

    fun destroy() {
        destroyed = true
        saves.close()
        proxy = null
        view.stopLoading()
        (view.parent as? android.view.ViewGroup)?.removeView(view)
        view.destroy()
    }

    fun canGoBack() = view.canGoBack()
    fun goBack() = view.goBack()

    /** Hands queued frame-control://install links to the page once it listens for them. */
    @SuppressLint("RequiresFeature")  // a reply proxy only exists once the listener was added
    fun deliverInstallLinks() {
        val reply = proxy ?: return
        if (!installReady) return
        for (link in host.takeInstallLinks()) {
            reply.postMessage(JSONObject().put("installLink", JSONObject().put("kind", link.kind).put("target", link.target)).toString())
        }
    }

    // MARK: bridge

    @SuppressLint("RequiresFeature")  // only called by the listener, which needs WEB_MESSAGE_LISTENER
    private fun receive(message: WebMessageCompat, reply: JavaScriptReplyProxy) {
        proxy = reply
        val request = runCatching { JSONObject(message.data ?: "") }.getOrNull() ?: return
        val id = request.optInt("id", -1)
        fun answer(value: Any? = null, error: String? = null) {
            val out = JSONObject().put("id", id)
            if (error != null) out.put("error", error) else out.put("value", value ?: JSONObject.NULL)
            if (!destroyed) reply.postMessage(out.toString())
        }
        when (request.optString("name")) {
            "readClipboard" -> {
                val clip = activity.getSystemService(ClipboardManager::class.java)?.primaryClip
                answer(clip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(activity)?.toString() ?: "")
            }
            "setUpConnection" -> {
                answer()
                // Not from inside the web view's own callback: going to setup destroys it.
                view.post { host.showSetup() }
            }
            "open" -> {
                val (msg, err) = open(request.optString("arg"))
                answer(msg?.let { JSONObject().put("message", it) }, err)
            }
            "startSave" -> {
                val arg = request.optJSONObject("arg") ?: return answer(error = "Invalid save")
                val size = arg.optLong("size", -2)
                if (choosingDestination || saves.active || size !in 0..SaveTransfer.MAX_SIZE) return answer(error = "Save unavailable or file too large")
                val name = NativeSaves.safeName(arg.optString("name"))
                if (arg.optBoolean("image")) {
                    saveWork({ saves.beginImage(name, size, arg.optString("head")) }, ::answer)
                } else {
                    choosingDestination = true
                    host.createDocument(name, arg.optString("mime").ifBlank { "application/octet-stream" }) { uri ->
                        choosingDestination = false
                        if (destroyed) { uri?.let { NativeSaves.discardDocument(activity, it) }; return@createDocument }
                        if (uri == null) answer(error = "Save cancelled")
                        else startDocument(uri, size, ::answer)
                    }
                }
            }
            "saveChunk", "finishSave", "abortSave" -> {
                val arg = request.optJSONObject("arg") ?: return answer(error = "Invalid save")
                val token = arg.optString("token")
                saveWork({
                    when (request.optString("name")) {
                        "saveChunk" -> saves.append(token, arg.optLong("offset", -1), arg.optString("data"))
                        "finishSave" -> saves.finish(token)
                        else -> saves.abort(token)
                    }
                    null
                }, ::answer)
            }
            "installLinkReady" -> {
                installReady = true
                answer()
                deliverInstallLinks()
            }
            else -> answer(error = "unknown request")
        }
    }

    /** SSH, SFTP, Steam Link and remote desktop open in the apps that handle them, as on the iPhone. */
    private fun open(what: String): Pair<String?, String?> {
        val s = host.pairing ?: return null to "Not paired with a Frame"
        val h = if (':' in s.host) "[${s.host}]" else s.host
        val (target, app, store) = when (what) {
            "terminal" -> Triple("ssh://${s.user}@$h:${s.port}", "an SSH app such as Termux or ConnectBot", "https://play.google.com/store/search?q=ssh%20client&c=apps")
            "sftp" -> Triple("sftp://${s.user}@$h:${s.port}", "an SFTP app", "https://play.google.com/store/search?q=sftp&c=apps")
            "steamlink" -> Triple("steamlink://", "Steam Link", "https://play.google.com/store/apps/details?id=com.valvesoftware.steamlink")
            "rdp" -> Triple("rdp://full%20address=s:${s.host}:3389", "Windows App (Microsoft Remote Desktop)", "https://play.google.com/store/apps/details?id=com.microsoft.rdc.androidx")
            else -> return null to "Can't open $what on this ${activity.deviceName}"
        }
        return try {
            activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(target)).addCategory(Intent.CATEGORY_BROWSABLE))
            "Opening $app" to null
        } catch (e: ActivityNotFoundException) {
            openExternal(store)
            null to "Install $app to open this; opening Google Play"
        }
    }

    private fun saveWork(work: () -> Any?, answer: (Any?, String?) -> Unit) {
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try { answer(withContext(Dispatchers.IO) { work() }, null) }
            catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { answer(null, e.message ?: "Couldn't save the file") }
        }
    }

    private fun startDocument(uri: Uri, size: Long, answer: (Any?, String?) -> Unit) {
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            var token: String? = null
            var delivered = false
            try {
                val id = withContext(Dispatchers.IO) { saves.beginDocument(uri, size).also { token = it } }
                answer(id, null)
                delivered = true
            } catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { answer(null, e.message ?: "Couldn't open destination") }
            finally {
                if (!delivered) {
                    token?.let { saves.abort(it) }
                    if (token == null) NativeSaves.discardDocument(activity, uri)
                }
            }
        }
    }

    private fun download(url: String, name: String, mime: String) {
        if (choosingDestination || saves.active) { toast("A save is already running"); return }
        choosingDestination = true
        host.createDocument(NativeSaves.safeName(name), mime) { uri ->
            choosingDestination = false
            if (uri == null) return@createDocument
            if (destroyed) { NativeSaves.discardDocument(activity, uri); return@createDocument }
            scope.launch(start = CoroutineStart.UNDISPATCHED) {
                var token: String? = null
                try {
                    withContext(Dispatchers.IO) {
                        val id = saves.beginDocument(uri, -1).also { token = it }
                        TunnelDownload.copy(url, policy, sessionKey, { !destroyed }) { offset, bytes -> saves.append(id, offset, bytes) }
                        saves.finish(id)
                    }
                    toast("Saved $name")
                } catch (e: kotlinx.coroutines.CancellationException) { throw e }
                catch (e: Exception) { if (!destroyed) toast(e.message ?: "Couldn't save the file") }
                finally {
                    token?.let { saves.abort(it) }
                    // Cancellation before IO dispatch must also remove the empty file.
                    if (token == null) NativeSaves.discardDocument(activity, uri)
                }
            }
        }
    }

    private fun openExternal(link: String) {
        try {
            activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(link)).addCategory(Intent.CATEGORY_BROWSABLE))
        } catch (e: ActivityNotFoundException) {
            toast("No app here opens web links")
        }
    }

    private fun toast(text: String) = Toast.makeText(activity, text, Toast.LENGTH_LONG).show()

    // MARK: navigation: the tunnel's page stays here; web links open in the browser; nothing else loads

    private inner class Client : WebViewClient() {
        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
            val url = request.url.toString()
            if (policy.decide(url, false) == OriginPolicy.Decision.STAY) return null
            // WebView handles blob/data image bytes in the renderer without network.
            // Every HTTP(S) request outside the exact tunnel is intercepted here.
            fun blocked() = WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", emptyMap(), ByteArrayInputStream(byteArrayOf()))
            if (destroyed || request.isForMainFrame || request.method != "GET" || !AssetPolicy.allows(url)) return blocked()
            return try {
                if (!assetSlots.tryAcquire(20, TimeUnit.SECONDS)) return blocked()
                try {
                    if (destroyed) return blocked()
                    val asset = host.fetchAsset(url)
                    WebResourceResponse(asset.mime, null, 200, "OK", mapOf("X-Content-Type-Options" to "nosniff", "Cache-Control" to "no-store", "Access-Control-Allow-Origin" to policy.origin), ByteArrayInputStream(asset.bytes))
                } finally { assetSlots.release() }
            } catch (_: Exception) { blocked() }
        }

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val link = request.url.toString()
            return when (policy.decide(link, request.isForMainFrame)) {
                OriginPolicy.Decision.STAY -> false
                // Only a tap opens the browser, so a script can't send the user away by itself.
                OriginPolicy.Decision.EXTERNAL -> { if (request.hasGesture()) openExternal(link); true }
                OriginPolicy.Decision.BLOCK -> true
            }
        }

        override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
            // Loads that skip shouldOverrideUrlLoading (a form POST, history) still may not leave the tunnel.
            if (url != "about:blank" && policy.decide(url) != OriginPolicy.Decision.STAY) view.stopLoading()
        }

        override fun doUpdateVisitedHistory(view: WebView, url: String, isReload: Boolean) = host.historyChanged()

        override fun onRenderProcessGone(view: WebView, detail: android.webkit.RenderProcessGoneDetail): Boolean {
            host.rendererGone()
            return true
        }
    }

    // MARK: file picking, and alert()/confirm(), which the page uses before removing things

    private inner class Chrome : WebChromeClient() {
        override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
            host.pickFiles(params, callback)
            return true
        }

        override fun onJsAlert(view: WebView, url: String, message: String, result: JsResult): Boolean {
            AlertDialog.Builder(activity).setMessage(message)
                .setPositiveButton(android.R.string.ok) { _, _ -> result.confirm() }
                .setOnCancelListener { result.confirm() }
                .show()
            return true
        }

        override fun onJsConfirm(view: WebView, url: String, message: String, result: JsResult): Boolean {
            AlertDialog.Builder(activity).setMessage(message)
                .setNegativeButton(android.R.string.cancel) { _, _ -> result.cancel() }
                .setPositiveButton(android.R.string.ok) { _, _ -> result.confirm() }
                .setOnCancelListener { result.cancel() }
                .show()
            return true
        }

        override fun onJsPrompt(view: WebView, url: String, message: String, defaultValue: String?, result: JsPromptResult): Boolean {
            result.cancel()
            return true
        }
    }

}
