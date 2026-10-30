package com.saphid.framecontrol

import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.saphid.framecontrol.core.FrameSettings
import com.saphid.framecontrol.core.InstallLink
import com.saphid.framecontrol.core.PendingHostKey
import com.saphid.framecontrol.core.Phase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The one screen: setup, connecting, waiting or failed, natively; the Frame Control page
 * in a web view once connected. The activity handles rotation and resizing itself
 * (android:configChanges), so the web view and its tunnel carry on through them.
 */
class MainActivity : ComponentActivity(), WebShell.Host {
    private lateinit var vm: MainViewModel
    private lateinit var ui: Ui
    private lateinit var root: FrameLayout

    private var shell: WebShell? = null
    private var screen: Screen? = null
    private var finder: FrameFinder? = null
    private var screenJob: Job? = null
    private var screenRestart: Job? = null
    private var hostKeyDialog: AlertDialog? = null
    private var hostKeyDialogId = -1
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private var documentCallback: ((Uri?) -> Unit)? = null
    private val createFile = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val callback = documentCallback
        documentCallback = null
        val uri = if (result.resultCode == RESULT_OK) result.data?.data else null
        try {
            if (callback != null) callback(uri)
            else if (uri != null) {
                // A picker may return after process death or Activity recreation.
                NativeSaves.discardDocument(this, uri)
                toast("Save was interrupted. Please try again.")
            }
        } finally { releasePickerSession() }
    }

    /** What's on screen, so a new step updates the text instead of rebuilding the view. */
    private sealed interface Screen {
        object Setup : Screen
        class Connecting(val step: TextView) : Screen
        class Failed(val phase: Phase.Failed) : Screen
        object Web : Screen
    }

    val deviceName: String get() = vm.deviceName

    private val pickMany = registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        deliverFiles(uris.takeIf { it.isNotEmpty() }?.toTypedArray())
    }
    private val pickOne = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        deliverFiles(uri?.let { arrayOf(it) })
    }

    /** Back steps through the page's history (its tabs) first; then the system decides. */
    private val back = object : OnBackPressedCallback(false) {
        override fun handleOnBackPressed() {
            shell?.takeIf { it.canGoBack() }?.goBack()
            historyChanged()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge(SystemBarStyle.dark(Color.TRANSPARENT), SystemBarStyle.dark(Color.TRANSPARENT))
        super.onCreate(savedInstanceState)
        vm = ViewModelProvider(this)[MainViewModel::class.java]
        ui = Ui(this)
        root = FrameLayout(this).apply { setBackgroundColor(getColor(R.color.frame_background)) }
        setContentView(root)
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            v.setPadding(bars.left, bars.top, bars.right, maxOf(bars.bottom, ime.bottom))
            WindowInsetsCompat.CONSUMED
        }
        onBackPressedDispatcher.addCallback(this, back)
        handleIntent(intent)
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch { vm.controller.phase.collect { render(it) } }
                launch { vm.controller.hostKey.collect { showHostKey(it) } }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        vm.setForeground(true)
    }

    override fun onStop() {
        super.onStop()
        vm.setForeground(false)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    override fun onDestroy() {
        screenRestart?.cancel()
        finder?.stop()
        finder = null
        destroyShell()
        hostKeyDialog?.dismiss()
        documentCallback?.invoke(null)
        documentCallback = null
        fileCallback?.onReceiveValue(null)
        fileCallback = null
        PickerSessionService.release()
        super.onDestroy()
    }

    // MARK: frame-control://install links

    private fun handleIntent(intent: Intent?) {
        val data = intent?.takeIf { it.action == Intent.ACTION_VIEW }?.dataString ?: return
        val link = InstallLink.parse(data) ?: return
        if (vm.pendingInstallLinks.size < 5) vm.pendingInstallLinks.addLast(link)
        shell?.deliverInstallLinks()
    }

    override fun takeInstallLinks(): List<InstallLink> = vm.pendingInstallLinks.toList().also { vm.pendingInstallLinks.clear() }

    // MARK: WebShell.Host

    override val pairing: FrameSettings? get() = vm.controller.pairing?.settings

    override fun fetchAsset(url: String) = vm.controller.fetchAsset(url)

    override fun showSetup() = vm.controller.showSetup()

    override fun createDocument(name: String, mime: String, result: (Uri?) -> Unit) {
        if (documentCallback != null) { result(null); return }
        documentCallback = result
        try {
            holdPickerSession()
            createFile.launch(Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = mime.takeIf { it.matches(Regex("[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+")) } ?: "application/octet-stream"
                putExtra(Intent.EXTRA_TITLE, name)
            })
        } catch (_: ActivityNotFoundException) {
            documentCallback = null; releasePickerSession(); result(null)
        } catch (_: IllegalStateException) {
            documentCallback = null; releasePickerSession(); result(null)
        }
    }

    override fun pickFiles(params: WebChromeClient.FileChooserParams, callback: ValueCallback<Array<Uri>>) {
        fileCallback?.onReceiveValue(null)
        fileCallback = callback
        val types = params.acceptTypes.orEmpty().flatMap { it.split(',') }.map { it.trim() }.filter { it.isNotEmpty() }.map {
            when {
                it.equals(".apk", ignoreCase = true) -> "application/vnd.android.package-archive"
                '/' in it -> it
                else -> "*/*"
            }
        }.distinct().ifEmpty { listOf("*/*") }.toTypedArray()
        try {
            holdPickerSession()
            if (params.mode == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE) pickMany.launch(types) else pickOne.launch(types)
        } catch (e: ActivityNotFoundException) {
            deliverFiles(null)
            Toast.makeText(this, "No app here can pick files", Toast.LENGTH_LONG).show()
        } catch (_: IllegalStateException) {
            deliverFiles(null)
            toast("File selection couldn't start. Please try again.")
        }
    }

    private fun holdPickerSession() {
        PickerSessionService.hold(this)
    }

    private fun releasePickerSession() {
        if (fileCallback == null && documentCallback == null) PickerSessionService.release()
    }

    private fun deliverFiles(uris: Array<Uri>?) {
        val callback = fileCallback
        fileCallback = null
        try {
            if (callback != null) callback.onReceiveValue(uris)
            else if (!uris.isNullOrEmpty()) toast("File selection was interrupted. Please choose files again.")
        } finally { releasePickerSession() }
    }

    /** A chooser result belongs to its original page, never a replacement session. */
    private fun destroyShell() {
        if (shell == null) return
        if (fileCallback != null) deliverFiles(null)
        shell?.destroy()
        shell = null
    }

    override fun historyChanged() {
        back.isEnabled = shell?.canGoBack() == true
    }

    override fun rendererGone() {
        // The page's renderer died (memory pressure): a fresh web view on the same tunnel.
        val phase = vm.controller.phase.value as? Phase.Ready
        destroyShell()
        screen = null
        if (phase != null) render(phase)
    }

    // MARK: screens

    private fun render(phase: Phase) {
        if (phase is Phase.Ready) {
            val replace = shell?.url != phase.url
            if (replace) {
                destroyShell()
                shell = WebShell(this, phase.url, phase.port, lifecycleScope, this)
            }
            if (replace || screen !is Screen.Web) show { shell!!.view to Screen.Web }
            historyChanged()
            return
        }
        destroyShell()
        historyChanged()
        when (phase) {
            is Phase.Setup -> if (screen !is Screen.Setup) show { setupScreen() to Screen.Setup }
            is Phase.Connecting -> (screen as? Screen.Connecting)?.step?.let { it.text = phase.step }
                ?: show { val (view, step) = connectingScreen(phase.step); view to Screen.Connecting(step) }
            is Phase.Failed -> if ((screen as? Screen.Failed)?.phase != phase) show { failedScreen(phase) to Screen.Failed(phase) }
            is Phase.Ready -> {}
        }
    }

    private fun show(make: () -> Pair<View, Screen>) {
        screenRestart?.cancel()
        screenRestart = null
        screenJob?.cancel()
        screenJob = null
        finder?.stop()
        finder = null
        currentFocus?.clearFocus()
        root.removeAllViews()
        val (view, which) = make()
        root.addView(view, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        screen = which
    }

    private fun scrolling(content: View, centred: Boolean = false): View = ScrollView(this).apply {
        isFillViewport = true
        val inner = MaxWidth(this@MainActivity, ui.dp(if (centred) 480 else 600)).apply {
            addView(content, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                if (centred) Gravity.CENTER else Gravity.TOP))
        }
        content.setPadding(ui.dp(20), ui.dp(20), ui.dp(20), ui.dp(28))
        if (centred) (content as? LinearLayout)?.gravity = Gravity.CENTER_HORIZONTAL
        addView(inner, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
    }

    private fun icon(sizeDp: Int) = ImageView(this).apply {
        setImageResource(R.mipmap.ic_launcher)
        contentDescription = null
        layoutParams = LinearLayout.LayoutParams(ui.dp(sizeDp), ui.dp(sizeDp))
    }

    private fun centredText(view: TextView) = view.apply { gravity = Gravity.CENTER_HORIZONTAL }

    private fun connectingScreen(step: String): Pair<View, TextView> = with(ui) {
        val stepText = centredText(text(step, 17f, bold = true))
        val hostText = centredText(muted(pairing?.label ?: ""))
        val col = column(16,
            icon(76),
            ProgressBar(this@MainActivity).apply { isIndeterminate = true },
            stepText,
            hostText,
            plainButton("Change headset") { vm.controller.showSetup() },
        )
        stepText.accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
        scrolling(col, centred = true) to stepText
    }

    private fun failedScreen(phase: Phase.Failed): View = with(ui) {
        if (phase.retrying && !phase.needsPairing) return waitingScreen(phase)
        val col = column(14,
            icon(64),
            centredText(title(if (phase.needsPairing) "Pair with the Frame again" else "Can't reach the Frame", 20f)),
            centredText(muted(phase.message, 15f)).apply { setTextIsSelectable(true) },
        )
        when {
            phase.needsPairing -> col.add(primaryButton("Pair again") { vm.controller.showSetup() }, 8)
            phase.canRetry -> col.add(primaryButton("Try again") { vm.controller.connect() }, 8)
        }
        if (!phase.needsPairing) col.add(plainButton(if (phase.canRetry) "Change headset" else "Back") { vm.controller.showSetup() })
        scrolling(col, centred = true)
    }

    /** A paired Frame that isn't answering is almost always asleep: say how to wake it, and connect the moment it does. */
    private fun waitingScreen(phase: Phase.Failed): View = with(ui) {
        val target = pairing
        val col = column(16,
            icon(76),
            centredText(title("Waiting for your Frame", 20f)),
            centredText(text("Put the headset on, or press its power button, to wake it. Frame Control connects by itself as soon as it's awake.", 15f)),
            card(
                tip("Same Wi-Fi as this $deviceName, or both on Tailscale."),
                tip("Asleep, the Frame drops off the network entirely; nothing can wake it remotely."),
            ),
            centredText(muted(phase.message, 13f)),
            plainButton("Connect to a different Frame") { vm.controller.showSetup() },
        )
        if (target != null) {
            screenJob?.cancel()
            screenJob = lifecycleScope.launch {
                    while (true) {
                        delay(3_000)
                        if (FrameFinder.sshAnswers(target.host, target.port)) {
                            vm.controller.retryQuietly()
                            return@launch
                        }
                    }
            }
        }
        scrolling(col, centred = true)
    }

    private fun setupScreen(): View = with(ui) {
        val saved = pairing
        val address = field("frame.local, an IP, or a Tailscale name").apply { setText(saved?.host ?: "") }
        val port = field("22", InputType.TYPE_CLASS_NUMBER).apply { setText(saved?.port?.takeIf { it != 22 }?.toString() ?: "") }
        val user = field("steamos").apply { setText(saved?.user ?: "steamos") }
        val password = field("Developer Mode password", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD).apply {
            importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
            imeOptions = EditorInfo.IME_ACTION_GO
        }

        val finder = FrameFinder(this@MainActivity, lifecycleScope).also { this@MainActivity.finder = it }
        val searching = ProgressBar(this@MainActivity).apply { isIndeterminate = true; layoutParams = LinearLayout.LayoutParams(dp(22), dp(22)) }
        val foundText = text("Looking for it on this network…", 15f, R.color.frame_muted).apply {
            setPadding(dp(10), 0, 0, 0)
            accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
        }
        val help = column(8,
            text("Still can't see it? Check:", 14f, bold = true),
            tip("The Frame and this $deviceName are on the same Wi-Fi."),
            tip("Developer Mode is on: on the Frame, Steam Settings → System → Enable Developer Mode."),
            tip("Or type its address below: its IP is in Steam Settings → Internet."),
        ).apply { visibility = View.GONE }

        fun target(): FrameSettings? {
            val typed = address.text.toString().trim()
            val host = typed.ifEmpty { finder.found.value?.host ?: "frame.local" }
            return FrameSettings.parse(host, user.text.toString(), port.text.toString())
        }

        val connectButton = primaryButton("Connect") {}
        fun updateConnectLabel() {
            val typed = address.text.toString().trim()
            connectButton.text = when {
                typed.isNotEmpty() -> "Connect to $typed"
                finder.found.value != null -> "Connect"
                else -> "Connect to frame.local"
            }
        }

        fun search() {
            if (this@MainActivity.finder !== finder) return
            val typed = address.text.toString().trim()
            val probe = FrameSettings.parse(typed.ifEmpty { "frame.local" }, "steamos", port.text.toString())
            finder.start(probe?.host ?: "frame.local", probe?.port ?: 22)
            help.visibility = View.GONE
            screenJob?.cancel()
            screenJob = lifecycleScope.launch {
                launch { delay(8_000); if (finder.found.value == null) help.visibility = View.VISIBLE }
                finder.found.collect { found ->
                    searching.visibility = if (found == null) View.VISIBLE else View.GONE
                    foundText.setTextColor(getColor(if (found == null) R.color.frame_muted else R.color.frame_green))
                    foundText.text = when {
                        found == null -> "Looking for it on this network…"
                        found.name == found.host -> "Found your Frame · ${found.host}"
                        else -> "Found your Frame · ${found.name} · ${found.host}"
                    }
                    if (found != null) help.visibility = View.GONE
                    updateConnectLabel()
                }
            }
        }

        fun connect() {
            val t = target() ?: return toast("Enter the headset's address, port and user name.")
            val text = password.text
            if (text.isEmpty()) { password.requestFocus(); return }
            val chars = CharArray(text.length).also { text.getChars(0, text.length, it, 0) }
            text.clear()
            finder.stop()
            vm.controller.pair(t, chars)
        }
        connectButton.setOnClickListener { connect() }
        password.setOnEditorActionListener { _, action, _ -> if (action == EditorInfo.IME_ACTION_GO) { connect(); true } else false }

        val showPassword = plainButton("Show") {}.apply {
            setOnClickListener {
                val hidden = (password.inputType and InputType.TYPE_MASK_VARIATION) == InputType.TYPE_TEXT_VARIATION_PASSWORD
                val at = password.selectionEnd
                password.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS or
                    (if (hidden) InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD else InputType.TYPE_TEXT_VARIATION_PASSWORD)
                password.setSelection(at.coerceAtLeast(0))
                text = if (hidden) "Hide" else "Show"
                contentDescription = if (hidden) "Hide password" else "Show password"
            }
            contentDescription = "Show password"
        }
        val passwordRow = row(password, showPassword).apply {
            password.layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        }

        val watcher = object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: Editable?) {
                updateConnectLabel()
                // A typed address replaces the search, once typing pauses.
                screenRestart?.cancel()
                screenRestart = lifecycleScope.launch { delay(700); search() }
            }
        }
        address.addTextChangedListener(watcher)
        port.addTextChangedListener(watcher)

        val keyLine = muted("…", 12f).apply { typeface = Typeface.MONOSPACE; setTextIsSelectable(true) }
        val keyPlace = muted("", 13f)
        lifecycleScope.launch {
            val (line, where) = withContext(Dispatchers.IO) { runCatching { vm.controller.authorizedKeysLine to vm.signer.protection() }.getOrNull() } ?: return@launch
            keyLine.text = line
            keyPlace.text = "The private half stays in this $deviceName's $where and can't be copied out."
        }

        val col = column(18)
        col.add(column(8,
            icon(56),
            title("Connect to your Steam Frame"),
            muted("One time only. After this, the app connects by itself whenever your Frame is awake.", 15f),
        ))
        if (saved != null) {
            col.add(card(
                text("Paired with ${saved.label}", 16f, bold = true),
                primaryButton("Reconnect") { vm.controller.connect() },
            ))
        }
        col.add(card(
            text("Get the Frame ready", 17f, bold = true),
            tip("Turn it on, on the same Wi-Fi as this $deviceName (or both on Tailscale)."),
            tip("Steam Settings → System → Enable Developer Mode. That turns on SSH."),
            tip("Steam Settings → Developer → Set User Password. There's no default password."),
            tip("The user is steamos. The address is frame.local, or the IP in Steam Settings → Internet."),
        ))
        col.add(card(
            text("1  Wake your Frame", 17f, bold = true),
            row(searching, foundText),
            text("Put the headset on, or press its power button, so it's awake.", 14f),
            help,
        ))
        col.add(card(
            text("2  Enter its Developer Mode password", 17f, bold = true),
            passwordRow,
            muted("It's only used now, to add this $deviceName's key to the Frame. It isn't saved. " +
                "Before it's sent, you'll check the Frame's identity.", 13f),
            connectButton,
        ))
        col.add(card(
            text("Headset address", 17f, bold = true),
            label("Address"), address,
            row(column(4, label("Port"), port).apply { layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f) },
                View(this@MainActivity).apply { layoutParams = LinearLayout.LayoutParams(dp(12), 1) },
                column(4, label("User"), user).apply { layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 2f) }),
            muted("Typing an address here uses it instead of searching.", 13f),
        ))
        col.add(card(
            text("Already reach the Frame over SSH?", 17f, bold = true),
            muted("Add this $deviceName's key to ~/.ssh/authorized_keys there, then connect without a password.", 14f),
            keyLine,
            keyPlace,
            row(
                plainButton("Copy key") { copyKey() },
                View(this@MainActivity).apply { layoutParams = LinearLayout.LayoutParams(0, 1, 1f) },
                plainButton("Connect with the key") {
                    val t = target() ?: return@plainButton toast("Enter the headset's address, port and user name.")
                    finder.stop()
                    vm.controller.useKey(t)
                },
            ),
        ))
        if (saved != null) {
            col.add(plainButton("Forget ${saved.label}", R.color.frame_red) { confirmForget(saved) }.apply { gravity = Gravity.START or Gravity.CENTER_VERTICAL })
        }
        col.add(row(
            plainButton("Privacy") { showText("Privacy", R.raw.privacy) },
            plainButton("Open-source licences") { showText("Open-source licences", R.raw.third_party_notices) },
        ))
        search()
        scrolling(col)
    }

    private fun copyKey() {
        lifecycleScope.launch {
            val line = withContext(Dispatchers.IO) { runCatching { vm.controller.authorizedKeysLine }.getOrNull() } ?: return@launch
            getSystemService(ClipboardManager::class.java)?.setPrimaryClip(ClipData.newPlainText("Frame Control SSH public key", line))
            toast("Copied this $deviceName's public key")
        }
    }

    private fun confirmForget(saved: FrameSettings) {
        AlertDialog.Builder(this)
            .setTitle("Forget ${saved.label}?")
            .setMessage("This $deviceName stops trusting it and goes back to setup. The Frame keeps this $deviceName's key line: " +
                "remove it from ~/.ssh/authorized_keys there to revoke this $deviceName.")
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton("Forget") { _, _ -> screen = null; vm.controller.forget() }
            .show()
    }

    private fun showText(title: String, raw: Int) {
        val body = resources.openRawResource(raw).use { it.readBytes().toString(Charsets.UTF_8) }
        val view = ScrollView(this).apply {
            addView(ui.text(body, 13f).apply { setPadding(ui.dp(22), ui.dp(12), ui.dp(22), ui.dp(12)); setTextIsSelectable(true) })
        }
        AlertDialog.Builder(this).setTitle(title).setView(view).setPositiveButton(android.R.string.ok, null).show()
    }

    // MARK: first-connection host key check

    private fun showHostKey(pending: PendingHostKey?) {
        if (pending == null) {
            hostKeyDialog?.dismiss()
            hostKeyDialog = null
            hostKeyDialogId = -1
            return
        }
        if (pending.id == hostKeyDialogId) return
        hostKeyDialog?.dismiss()
        val q = pending.question
        val file = when {
            q.key.type == "ssh-ed25519" -> "ssh_host_ed25519_key.pub"
            q.key.type.startsWith("ecdsa-") -> "ssh_host_ecdsa_key.pub"
            q.key.type == "ssh-rsa" -> "ssh_host_rsa_key.pub"
            else -> null
        }
        val body = ui.column(12).apply {
            setPadding(ui.dp(22), ui.dp(8), ui.dp(22), 0)
            with(ui) {
                if (q.previous != null) {
                    add(text("This is not the identity this $deviceName trusted for ${q.settings.label} before. " +
                        "Only continue if the Frame was reset or SteamOS reinstalled.", 15f, R.color.frame_orange, bold = true))
                    add(muted("Before: ${q.previous.fingerprint}", 12f).apply { typeface = Typeface.MONOSPACE })
                }
                add(text("Frame Control is connecting to ${q.settings.label} as ${q.settings.user} for the first time. " +
                    "Nothing has been sent to it yet. Its SSH identity (${q.key.type}) is:", 15f))
                add(text(q.key.fingerprint, 15f, bold = true).apply {
                    typeface = Typeface.MONOSPACE
                    setTextIsSelectable(true)
                    background = rounded(getColor(R.color.frame_field), 8)
                    setPadding(dp(12), dp(10), dp(12), dp(10))
                })
                add(muted(if (file != null) "To check it, run  ssh-keygen -lf /etc/ssh/$file  in a terminal on the Frame (desktop mode). " +
                    "It should print the same SHA256 text." else "Check it against the Frame's own host key before continuing.", 13f))
                add(muted("If it ever changes later, Frame Control refuses to connect.", 13f))
            }
        }
        hostKeyDialogId = pending.id
        hostKeyDialog = AlertDialog.Builder(this)
            .setTitle("Is this your Frame?")
            .setView(ScrollView(this).apply { addView(body) })
            .setCancelable(false)
            .setNegativeButton("Cancel") { _, _ -> vm.controller.answerHostKey(pending.id, false) }
            .setPositiveButton("Trust and continue") { _, _ -> vm.controller.answerHostKey(pending.id, true) }
            .create()
            .also { dialog ->
                dialog.setOnKeyListener { _, keyCode, event ->
                    if (keyCode == android.view.KeyEvent.KEYCODE_BACK && event.action == android.view.KeyEvent.ACTION_UP) {
                        vm.controller.answerHostKey(pending.id, false)
                        dialog.dismiss()
                        true
                    } else false
                }
                dialog.show()
            }
    }

    private fun toast(text: String) = Toast.makeText(this, text, Toast.LENGTH_LONG).show()
}
