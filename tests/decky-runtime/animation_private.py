"""Disposable movie overrides driven through the published Decky legacy RPC."""
import base64
import hashlib
import json
import os
from pathlib import Path

VIDEOS = ('deck_startup.webm', 'steam_os_suspend.webm',
          'steam_os_suspend_from_throbber.webm')
KINDS = ('boot', 'suspend', 'throbber')


def snapshot(path):
    info = path.lstat()
    return dict(base64=base64.b64encode(path.read_bytes()).decode(),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                identity=[info.st_dev, info.st_ino])


def prepare(home, base, folder):
    movies = home/'.steam/root/config/uioverrides/movies'
    movies.mkdir(parents=True)
    originals = {}
    for video in VIDEOS:
        path = movies/video
        path.write_bytes(('Private original '+video+'\n').encode())
        originals[video] = snapshot(path)
    selections = []
    for name in ['a', 'b']:
        path = home/('private-animation-'+name+'.webm')
        path.write_bytes(('Private selected '+name+'\n').encode())
        selections.append(dict(id=name, path=str(path), name='Private '+name, target='boot'))
    settings = base/'settings'/folder/'config.json'
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps(dict(boot='', suspend='', throbber='', randomize='',
        current_set='', downloads=[], custom_animations=selections, custom_sets=[],
        shuffle_exclusions=[], force_ipv4=False)))
    return dict(movies=movies, originals=originals, selections=selections)


def exercise(fixture, legacy, rpc, name, until_ready):
    def ready():
        response = rpc('loader/call_legacy_plugin_method', name, 'getState', {})
        return response.get('success') and response.get('result', {}).get('settings', {}).get('boot') == ''
    until_ready(ready, 'private Animation Changer settings')
    initial = legacy('getState')
    assert initial['settings']['boot'] == initial['settings']['suspend'] == initial['settings']['throbber'] == ''
    movies, originals = fixture['movies'], fixture['originals']
    assert {v:snapshot(movies/v) for v in VIDEOS} == originals
    assert not (movies/'.frame-control-animation-backups').exists()
    transitions = []
    for video, kind in zip(VIDEOS, KINDS):
        target = movies/video
        backup = movies/'.frame-control-animation-backups'/video/'original'
        for selected in ['a', 'a', 'b']:
            legacy('saveSettings', settings={kind:selected})
            source = next(v['path'] for v in fixture['selections'] if v['id'] == selected)
            assert target.is_symlink() and os.readlink(target) == source
            assert snapshot(backup) == originals[video]
            state = legacy('getState')
            assert state['settings'][kind] == selected
            transitions.append(dict(video=video, selection=selected, link=os.readlink(target),
                                    originalBackup=snapshot(backup)))
        legacy('saveSettings', settings={kind:''})
        assert not target.is_symlink() and snapshot(target) == originals[video]
        assert not os.path.lexists(backup)
    final = legacy('getState')
    assert all(final['settings'][kind] == '' for kind in KINDS)
    restored = {v:snapshot(movies/v) for v in VIDEOS}
    assert restored == originals
    return dict(defaultStartupPreservedAllThreeOverrides=True, originals=originals,
        transitions=transitions, restored=restored, repeatAndSwitchPreservedOriginal=True,
        resetRestoredOriginalBytesAndInodes=True, allSelectedSourceBytesRetained={
            v['id']:snapshot(Path(v['path'])) for v in fixture['selections']},
        privateFixtureOnly=True, actualSteamPlaybackVerified=False, externalRepositoryVerified=False,
        realFrameContacted=False, browserVerified=False, physicalControllerVerified=False)
