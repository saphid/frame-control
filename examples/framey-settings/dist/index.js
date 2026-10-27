const manifest = {"name":"Framey Settings Sample"};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api;
try {
    api = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api._version}. Some features may not work.`);
}
const callable = api.callable;
const routerHook = api.routerHook;
const toaster = api.toaster;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

const getSetting = callable('get_setting');
const setSetting = callable('set_setting');
function Content() {
    const [enabled, setEnabled] = SP_REACT.useState(false);
    const [busy, setBusy] = SP_REACT.useState(true);
    const [message, setMessage] = SP_REACT.useState('Loading setting…');
    const pending = SP_REACT.useRef(false);
    const resetModalOpen = SP_REACT.useRef(false);
    async function refresh() {
        if (pending.current)
            return;
        pending.current = true;
        setBusy(true);
        try {
            const value = await getSetting('enabled', false);
            setEnabled(value);
            setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
        }
        catch (error) {
            setMessage(`Could not read setting: ${String(error)}`);
        }
        finally {
            pending.current = false;
            setBusy(false);
        }
    }
    SP_REACT.useEffect(() => { void refresh(); }, []);
    async function change(value) {
        // Two controller events can arrive before React redraws the disabled toggle.
        // Keep writes ordered so a late first reply cannot replace the final choice.
        if (pending.current)
            return;
        pending.current = true;
        setBusy(true);
        try {
            await setSetting('enabled', value);
            setEnabled(value);
            setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
            toaster.toast({ title: 'Framey sample',
                body: SP_JSX.jsxs("span", { children: ["Setting saved: ", SP_JSX.jsx("strong", { children: value ? 'on' : 'off' })] }) });
        }
        catch (error) {
            setMessage(`Could not save setting: ${String(error)}`);
        }
        finally {
            pending.current = false;
            setBusy(false);
        }
    }
    function confirmReset() {
        if (pending.current || resetModalOpen.current)
            return;
        const dialog = DFL.showModal(SP_JSX.jsx(DFL.ConfirmModal, { strTitle: "Reset example setting?", strDescription: "This changes only the sample plugin's saved setting.", strOKButtonText: "Reset", strCancelButtonText: "Keep setting", onOK: () => { void change(false); } }));
        resetModalOpen.current = true;
        void dialog.ClosedPromise.then(() => { resetModalOpen.current = false; });
    }
    return SP_JSX.jsxs(DFL.PanelSection, { title: "Framey settings sample", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Example setting", description: "Stored by the Decky Python backend", checked: enabled, disabled: busy, onChange: (value) => { void change(value); } }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { disabled: busy, onClick: () => { void refresh(); }, children: "Reload saved setting" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { disabled: busy, onClick: confirmReset, children: "Reset example setting" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { onClick: () => DFL.Navigation.Navigate('/framey-sample/details/saved-setting'), children: "About this setting" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("p", { role: "status", children: message }) })] });
}
function Details() {
    const { topic } = DFL.useParams();
    return SP_JSX.jsxs(DFL.PanelSection, { title: "Sample detail page", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs("p", { children: ["Topic: ", topic || 'overview'] }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("p", { children: "The toggle is stored by this plugin's Decky backend in the user's settings directory." }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { onClick: () => DFL.Navigation.NavigateBack(), children: "Back to setting" }) })] });
}
var index = definePlugin(() => {
    routerHook.addRoute('/framey-sample/details/:topic?', Details);
    return Object.assign({
        name: 'Framey Settings Sample',
        icon: SP_JSX.jsx("span", { "aria-hidden": "true", children: "\u2699" }),
        content: SP_JSX.jsx(Content, {}),
        onDismount: () => routerHook.removeRoute('/framey-sample/details/:topic?'),
    }, {
        // Framey additions are ignored by Decky's own menu. Keep the main content
        // usable there too, while showing authors the extra VR settings view.
        settings: SP_JSX.jsx(Content, {}),
        frameyQuickActions: [{
                label: 'Read saved setting',
                onClick: async () => {
                    const enabled = await getSetting('enabled', false);
                    return `Saved setting is ${enabled ? 'on' : 'off'}`;
                },
            }],
    });
});

export { index as default };
//# sourceMappingURL=index.js.map
