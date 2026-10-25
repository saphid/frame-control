import {callable, definePlugin, toaster} from '@decky/api';
import {ButtonItem, PanelSection, PanelSectionRow, ToggleField} from '@decky/ui';
import {useEffect, useState} from 'react';

const getSetting = callable<[key: string, fallback: boolean], boolean>('get_setting');
const setSetting = callable<[key: string, value: boolean], boolean>('set_setting');

function Content() {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState('Loading setting…');

  async function refresh() {
    setBusy(true);
    try {
      const value = await getSetting('enabled', false);
      setEnabled(value);
      setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
    } catch (error) {
      setMessage(`Could not read setting: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {void refresh();}, []);

  async function change(value: boolean) {
    setBusy(true);
    try {
      await setSetting('enabled', value);
      setEnabled(value);
      setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
      toaster.toast({title: 'Framey sample', body: 'Setting saved'});
    } catch (error) {
      setMessage(`Could not save setting: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  return <PanelSection title="Framey settings sample">
    <PanelSectionRow>
      <ToggleField label="Example setting" description="Stored by the Decky Python backend"
        checked={enabled} disabled={busy} onChange={(value: boolean) => {void change(value);}} />
    </PanelSectionRow>
    <PanelSectionRow><ButtonItem disabled={busy} onClick={() => {void refresh();}}>Reload saved setting</ButtonItem></PanelSectionRow>
    <PanelSectionRow><p role="status">{message}</p></PanelSectionRow>
  </PanelSection>;
}

export default definePlugin(() => ({
  name: 'Framey Settings Sample',
  icon: <span aria-hidden="true">⚙</span>,
  content: <Content />,
}));
