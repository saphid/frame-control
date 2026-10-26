import {callable, definePlugin, routerHook, toaster} from '@decky/api';
import {ButtonItem, Navigation, PanelSection, PanelSectionRow, ToggleField, useParams} from '@decky/ui';
import {useEffect, useRef, useState} from 'react';

const getSetting = callable<[key: string, fallback: boolean], boolean>('get_setting');
const setSetting = callable<[key: string, value: boolean], boolean>('set_setting');

function Content() {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState('Loading setting…');
  const pending = useRef(false);

  async function refresh() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    try {
      const value = await getSetting('enabled', false);
      setEnabled(value);
      setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
    } catch (error) {
      setMessage(`Could not read setting: ${String(error)}`);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  useEffect(() => {void refresh();}, []);

  async function change(value: boolean) {
    // Two controller events can arrive before React redraws the disabled toggle.
    // Keep writes ordered so a late first reply cannot replace the final choice.
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    try {
      await setSetting('enabled', value);
      setEnabled(value);
      setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
      toaster.toast({title: 'Framey sample',
        body: <span>Setting saved: <strong>{value ? 'on' : 'off'}</strong></span>});
    } catch (error) {
      setMessage(`Could not save setting: ${String(error)}`);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return <PanelSection title="Framey settings sample">
    <PanelSectionRow>
      <ToggleField label="Example setting" description="Stored by the Decky Python backend"
        checked={enabled} disabled={busy} onChange={(value: boolean) => {void change(value);}} />
    </PanelSectionRow>
    <PanelSectionRow><ButtonItem disabled={busy} onClick={() => {void refresh();}}>Reload saved setting</ButtonItem></PanelSectionRow>
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
      const enabled = await getSetting('enabled', false);
      return `Saved setting is ${enabled ? 'on' : 'off'}`;
    },
  }],
  });
});
