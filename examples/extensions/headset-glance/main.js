let nextId = 0;
const pending = new Map();

window.addEventListener('message', event => {
  if (event.source !== parent || event.data?.type !== 'frame-control:response') return;
  const resolve = pending.get(event.data.id);
  if (resolve) {
    pending.delete(event.data.id);
    resolve(event.data.value);
  }
});

function request(action) {
  return new Promise(resolve => {
    const id = ++nextId;
    pending.set(id, resolve);
    parent.postMessage({type: 'frame-control:request', id, action}, '*');
  });
}

async function refresh() {
  const status = await request('status');
  document.getElementById('summary').textContent = status.connected
    ? `Frame OS ${status.os.version || 'unknown'} · Battery ${status.battery.percent ?? '?'}% · SteamVR ${status.steamvr ? 'running' : 'stopped'}`
    : 'No headset status is available yet.';
}

document.getElementById('refresh').addEventListener('click', refresh);
refresh();
