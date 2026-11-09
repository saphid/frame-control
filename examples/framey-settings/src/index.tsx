import {callable, definePlugin, routerHook, toaster} from '@decky/api';
import {ButtonItem, ConfirmModal, Navigation, PanelSection, PanelSectionRow, ToggleField, showModal, useParams} from '@decky/ui';
import {useEffect, useRef, useState} from 'react';

const getSetting = callable<[key: string, fallback: boolean], boolean>('get_setting');
const setSetting = callable<[key: string, value: boolean], boolean>('set_setting');

async function readEnabled() {
  const value = await getSetting('enabled', false);
  if (typeof value !== 'boolean') throw new Error('Backend returned an invalid setting value.');
  return value;
}

function Content() {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState('Loading setting…');
  const pending = useRef(false);
  const resetDialog = useRef<ReturnType<typeof showModal> | null>(null);
  const readReady = useRef(false);
  const active = useRef(true);
  const requestSequence = useRef(0);

  async function refresh() {
    if (!active.current || pending.current) return;
    const request = ++requestSequence.current;
    const isCurrent = () => active.current && request === requestSequence.current;
    pending.current = true;
    readReady.current = false;
    setBusy(true);
    try {
      const value = await readEnabled();
      if (!isCurrent()) return;
      readReady.current = true;
      setEnabled(value);
      setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
    } catch (error) {
      if (isCurrent()) setMessage(`Could not read setting: ${String(error)}. Reload saved setting before changing it.`);
    } finally {
      if (isCurrent()) {
        pending.current = false;
        setBusy(false);
      }
    }
  }

  useEffect(() => {
    active.current = true;
    void refresh();
    return () => {
      // Retire this view's callbacks, not a write already sent to the backend.
      // Advancing the sequence also protects a fresh effect setup/replay.
      active.current = false;
      requestSequence.current++;
      pending.current = false;
      readReady.current = false;
      resetDialog.current?.Close();
      resetDialog.current = null;
    };
  }, []);

  async function change(value: boolean) {
    // Two controller events can arrive before React redraws the disabled toggle.
    // Keep writes ordered so a late first reply cannot replace the final choice.
    if (!active.current || pending.current) return;
    if (!readReady.current) throw new Error('Reload saved setting before changing it.');
    const request = ++requestSequence.current;
    const isCurrent = () => active.current && request === requestSequence.current;
    pending.current = true;
    setBusy(true);
    try {
      const saved = await setSetting('enabled', value);
      if (!isCurrent()) return;
      if (saved !== true) throw new Error('Backend did not acknowledge the saved setting.');
      setEnabled(value);
      setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
      toaster.toast({title: 'Framey sample',
        body: <span>Setting saved: <strong>{value ? 'on' : 'off'}</strong></span>});
    } catch (error) {
      if (isCurrent()) {
        // A lost reply does not prove the backend failed to commit. Require a
        // fresh read rather than let another edit use the stale display value.
        readReady.current = false;
        const failure = new Error(`Could not confirm saved setting: ${String(error)}. Close any Reset dialog, then Reload saved setting before changing it.`);
        setMessage(failure.message);
        throw failure;
      }
      throw error;
    } finally {
      if (isCurrent()) {
        pending.current = false;
        setBusy(false);
      }
    }
  }

  function confirmReset() {
    if (!active.current || pending.current || !readReady.current || resetDialog.current) return;
    const dialog = showModal(<ConfirmModal strTitle="Reset example setting?"
      strDescription="This changes only the sample plugin's saved setting."
      strOKButtonText="Reset" strCancelButtonText="Keep setting"
      onOK={() => change(false)} />);
    resetDialog.current = dialog;
    void dialog.ClosedPromise.then(() => {
      if (resetDialog.current === dialog) resetDialog.current = null;
    });
  }

  return <PanelSection title="Framey settings sample">
    <PanelSectionRow>
      <ToggleField label="Example setting" description="Stored by the Decky Python backend"
        checked={enabled} disabled={busy || !readReady.current} onChange={(value: boolean) => {void change(value).catch(() => {});}} />
    </PanelSectionRow>
    <PanelSectionRow><ButtonItem disabled={busy} onClick={() => {void refresh();}}>Reload saved setting</ButtonItem></PanelSectionRow>
    <PanelSectionRow><ButtonItem disabled={busy || !readReady.current} onClick={confirmReset}>Reset example setting</ButtonItem></PanelSectionRow>
    <PanelSectionRow><ButtonItem onClick={() => Navigation.Navigate('/framey-sample/details/saved-setting')}>About this setting</ButtonItem></PanelSectionRow>
    <PanelSectionRow><p role="status">{message}</p></PanelSectionRow>
  </PanelSection>;
}

function Details() {
  const {topic} = useParams<{topic?: string}>();
  return <PanelSection title="Sample detail page">
    <PanelSectionRow><p>Topic: {topic || 'overview'}</p></PanelSectionRow>
    <PanelSectionRow><p>The toggle is stored by this plugin's Decky backend in the user's settings directory.</p></PanelSectionRow>
    <PanelSectionRow><ButtonItem onClick={() => Navigation.NavigateBack()}>Back to setting</ButtonItem></PanelSectionRow>
  </PanelSection>;
}

export default definePlugin(() => {
  routerHook.addRoute('/framey-sample/details/:topic?', Details);
  return Object.assign({
  name: 'Framey Settings Sample',
  icon: <span aria-hidden="true">⚙</span>,
  content: <Content />,
  onDismount: () => routerHook.removeRoute('/framey-sample/details/:topic?'),
}, {
  // Framey additions are ignored by Decky's own menu. Keep the main content
  // usable there too, while showing authors the extra VR settings view.
  settings: <Content />,
  frameyQuickActions: [{
    label: 'Read saved setting',
    onClick: async () => {
      const enabled = await readEnabled();
      return `Saved setting is ${enabled ? 'on' : 'off'}`;
    },
  }],
  });
});
