/* Private user catalogs. Loading this module never fetches game content. */
(function(root) {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function sourceRows(sources, busy) {
    return sources.map(s => `<div class="nxnative-source"><div><strong>${escape(s.name)}</strong><p class="sub">${escape(s.location || '')}</p>${s.error ? `<p class="sub warn">${escape(s.error)}</p>` : ''}</div><button type="button" class="small" data-nx-remove="${escape(s.id)}" ${busy ? 'disabled' : ''} aria-label="Remove ${escape(s.name)}">Remove</button></div>`).join('') || '<p class="sub">No game sources yet. Add a catalog or folder above.</p>';
  }
  function gameRows(games, query, busy) {
    const q = query.trim().toLocaleLowerCase();
    const shown = games.filter(g => `${g.name} ${g.title_id || ''} ${g.version || ''}`.toLocaleLowerCase().includes(q));
    return shown.map(g => `<div class="nxnative-game"><div><strong>${escape(g.name)}</strong><p class="sub">${escape([g.version, g.title_id].filter(Boolean).join(' · '))}</p><p class="sub">${escape(g.installable ? 'Prepared NxNative package' : g.reason || 'Needs preparation on a supported build computer.')}</p></div><button type="button" class="small ${g.installable ? 'action' : ''}" ${g.installable ? `data-nx-install="${escape(g.id)}" data-nx-source="${escape(g.source_id)}"` : 'data-nx-prepare'} ${busy ? 'disabled' : ''}>${g.installable ? 'Install' : 'Preparation steps'}</button></div>`).join('') || `<p class="sub">${q ? 'No games match your search.' : 'Games from your sources will appear here.'}</p>`;
  }
  function guideSection(guide) {
    return `<h3>${escape(guide.title || 'Prepare on a Mac')}</h3><ol>${(guide.steps || []).map(step => `<li>${escape(step)}</li>`).join('')}</ol>${guide.command ? `<pre style="white-space:pre-wrap;overflow-wrap:anywhere">${escape(guide.command)}</pre>` : ''}${guide.requirements?.length ? `<p class="sub">Needs: ${guide.requirements.map(escape).join(' · ')}</p>` : ''}`;
  }
  function mount({document, api, onInstalled = () => {}, onInstallApk = () => {}, mobile = () => false, sleep = ms => new Promise(resolve => setTimeout(resolve, ms))}) {
    const get = id => document.getElementById(id);
    const state = {sources:[], games:[], busy:false, loaded:false};
    const status = message => { get('nxnativeStatus').textContent = message || ''; };
    function render() {
      get('nxnativeSources').innerHTML = sourceRows(state.sources, state.busy);
      get('nxnativeGames').innerHTML = gameRows(state.games, get('nxnativeSearch').value, state.busy);
      get('nxnativeRefresh').disabled = state.busy;
      for (const element of get('nxnativeAdd').elements) element.disabled = state.busy;
    }
    async function load() {
      const data = await api('/api/nxnative');
      state.sources = data.sources || []; state.games = data.games || []; state.loaded = true;
      if (data.preparation) {
        const guide = data.preparation;
        get('nxnativeGuide').innerHTML = guideSection(guide) + (guide.love ? guideSection(guide.love) + '<button type="button" class="small" data-nx-install-apk>Install a prepared APK</button>' : '');
      }
      render(); return data;
    }
    async function action(body, label) {
      if (state.busy) return;
      state.busy = true; render(); status(label + '…');
      let success = false;
      try {
        let result = await api('/api/nxnative', body);
        if (result.job) {
          const id = result.job;
          for (;;) {
            const job = await api('/api/job?id=' + encodeURIComponent(id));
            status(job.stage || job.message || label + '…');
            if (job.done) {
              if (job.error) throw new Error(job.error);
              result = job.result || job;
              break;
            }
            await sleep(1000);
          }
        }
        status(result.message || (body.action === 'add' ? 'Game source added.' : body.action === 'refresh' ? 'Game sources refreshed.' : 'Done.'));
        await load();
        if (body.action === 'install') onInstalled(result);
        success = true;
      } catch (error) { status(error.message); }
      finally { state.busy = false; render(); }
      return success;
    }
    async function open() {
      get('installChooser')?.close();
      if (mobile()) get('nxnativePathNote').textContent = 'Use an HTTPS catalog, or a folder mounted on your Frame. Paths here refer to the Frame, not your phone or tablet.';
      if (!get('nxnativeDlg').open) get('nxnativeDlg').showModal();
      if (state.busy) return;
      status('Reading your game sources…');
      try { await load(); status(''); } catch (error) { status(error.message); }
    }
    document.querySelectorAll('[data-open-nxnative]').forEach(button => { button.onclick = open; });
    get('nxnativeClose').onclick = () => get('nxnativeDlg').close();
    get('nxnativeRefresh').onclick = () => action({action:'refresh'}, 'Refresh game sources');
    get('nxnativeSearch').oninput = render;
    get('nxnativeGuide').onclick = event => {
      if (state.busy || !event.target.closest('[data-nx-install-apk]')) return;
      get('nxnativeDlg').close();
      onInstallApk();
    };
    get('nxnativeAdd').onsubmit = async event => {
      event.preventDefault();
      const form = get('nxnativeAdd');
      const location = form.elements.namedItem('location').value.trim();
      const name = form.elements.namedItem('name').value.trim();
      if (await action({action:'add', location, name}, 'Add game source')) form.reset();
    };
    get('nxnativeSources').onclick = event => {
      const button = event.target.closest('[data-nx-remove]');
      if (button) action({action:'remove', source:button.dataset.nxRemove}, 'Remove game source');
    };
    get('nxnativeGames').onclick = event => {
      if (event.target.closest('[data-nx-prepare]')) {
        const guide = get('nxnativePreparation'); guide.open = true; guide.scrollIntoView?.({block:'nearest'}); return;
      }
      const button = event.target.closest('[data-nx-install]');
      if (button && !button.disabled) action({action:'install', source:button.dataset.nxSource, id:button.dataset.nxInstall}, 'Install NxNative game');
    };
    return {open, load, action, state};
  }
  const exported = {mount, sourceRows, gameRows};
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  else root.FrameNxNative = exported;
})(typeof window !== 'undefined' ? window : globalThis);
