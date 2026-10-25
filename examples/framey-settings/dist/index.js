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
    async function refresh() {
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
            setBusy(false);
        }
    }
    SP_REACT.useEffect(() => { void refresh(); }, []);
    async function change(value) {
        setBusy(true);
        try {
            await setSetting('enabled', value);
            setEnabled(value);
            setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
            toaster.toast({ title: 'Framey sample', body: 'Setting saved' });
        }
        catch (error) {
            setMessage(`Could not save setting: ${String(error)}`);
        }
        finally {
            setBusy(false);
        }
    }
    return SP_JSX.jsxs(DFL.PanelSection, { title: "Framey settings sample", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Example setting", description: "Stored by the Decky Python backend", checked: enabled, disabled: busy, onChange: (value) => { void change(value); } }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { disabled: busy, onClick: () => { void refresh(); }, children: "Reload saved setting" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("p", { role: "status", children: message }) })] });
}
var index = definePlugin(() => Object.assign({
    name: 'Framey Settings Sample',
    icon: SP_JSX.jsx("span", { "aria-hidden": "true", children: "\u2699" }),
    content: SP_JSX.jsx(Content, {}),
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
}));

export { index as default };
//# sourceMappingURL=index.js.map
