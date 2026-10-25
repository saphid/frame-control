// Own one Python relay. Async preparation can be cancelled before a process exists.
const ALIAS = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
function createObsSource({ prepare, spawn, onState = () => {}, supported = true }) {
  let child = null, attempt = 0;
  let state = { state: 'idle', alias: '', port: 15099, error: '', supported };
  const status = () => ({ ...state });
  function set(next, alias = state.alias, port = state.port, error = '') {
    state = { state: next, alias, port, error, supported };
    onState(status()); return status();
  }
  function stop() {
    ++attempt;
    if (!child) return set('idle');
    set('stopping');
    if (child.stdin && !child.stdin.writableEnded) child.stdin.end();
    return status();
  }
  async function start(alias, port = 15099) {
    if (!supported) return status();
    if (!ALIAS.test(alias || '')) throw new Error('Select a valid headset first.');
    if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('OBS port must be a whole number from 1024 to 65535.');
    if (child || state.state === 'starting') return status();
    const id = ++attempt;
    set('starting', alias, port);
    try {
      const { executable, args = [], env } = await prepare(alias);
      if (id !== attempt) return status();
      const proc = spawn(executable, [...args, '--frame', alias, '--port', String(port), '--control-stdin'],
                         { env, stdio: ['pipe', 'ignore', 'pipe'], windowsHide: true });
      child = proc;
      // The helper may exit between a click and closing its control pipe.
      proc.stdin.on('error', () => {});
      let output = '';
      proc.stderr.on('data', chunk => {
        output = (output + chunk.toString('utf8')).slice(-2048);
        if (child === proc && state.state === 'starting' && output.includes('Frame Control OBS stream is ready'))
          set('running', alias, port);
      });
      proc.once('error', error => {
        if (child !== proc) return;
        child = null; set('failed', alias, port, `Could not start OBS source: ${error.message}`);
      });
      // close follows stderr EOF, so the final failure message is available.
      proc.once('close', (code, signal) => {
        if (child !== proc) return;
        const stopping = state.state === 'stopping';
        child = null;
        set(stopping ? 'idle' : 'failed', alias, port,
            stopping ? '' : `OBS source stopped (${signal || code}). ${output.trim().split('\n').pop() || 'Check SteamVR and SSH.'}`);
      });
      return status();
    } catch (error) {
      if (id !== attempt) return status();
      return set('failed', alias, port, error.message);
    }
  }
  return { start, stop, status, get child() { return child; } };
}
module.exports = { createObsSource };
