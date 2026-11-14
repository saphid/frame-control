"""Notebook's unmodified backend, private app IDs and independent file readback."""
import hashlib
import json


def probe(call, restart, settings):
    app_a, app_b = 424242, 434343
    strokes = {
        (0, 0): [{"paths": [{"x": 4, "y": 8}, {"x": 16, "y": 24}],
                  "strokeWidth": 3, "strokeColor": "#ffffff", "drawMode": True}],
        (app_a, 2): [{"paths": [{"x": 10, "y": 20}, {"x": 30, "y": 40}],
                      "strokeWidth": 4, "strokeColor": "#ff0000", "drawMode": True}],
        (app_b, 2): [{"paths": [{"x": 50, "y": 60}, {"x": 70, "y": 80}],
                      "strokeWidth": 5, "strokeColor": "#00ff00", "drawMode": True}],
    }
    payloads = {key: json.dumps(value, separators=(',', ':')) for key, value in strokes.items()}
    for app in (0, app_a, app_b):
        assert call('listPages', appid=app) == []
        assert call('loadLastSelectedPage', appid=app) == 0
        assert call('loadPage', appid=app, page=2) == dict(page=2, timestamp=0, empty=True, data='')
    for (app, page), data in payloads.items():
        saved = call('savePage', appid=app, page=page, data=data)
        assert type(saved['timestamp']) is int and saved['timestamp'] > 0
        path = settings / str(app) / (str(page) + '.json')
        assert path.read_text() == data
        loaded = call('loadPage', appid=app, page=page)
        assert loaded == dict(page=page, timestamp=int(path.stat().st_mtime * 1000), empty=False, data=data)
    assert call('savePage', appid=app_a, page=7, data='')['timestamp'] > 0
    assert call('loadPage', appid=app_a, page=7)['empty'] is True
    selections = {0: 0, app_a: 7, app_b: 2}
    for app, page in selections.items():
        assert call('saveLastSelectedPage', appid=app, page=page) is True
        assert (settings / str(app) / 'page').read_text() == str(page)
    before = {str(path.relative_to(settings)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in settings.rglob('*') if path.is_file()}
    restart()
    for app, page in selections.items():
        assert call('loadLastSelectedPage', appid=app) == page
    for (app, page), data in payloads.items():
        assert call('loadPage', appid=app, page=page)['data'] == data
    pages = sorted(call('listPages', appid=app_a), key=lambda item: item['page'])
    assert [p['page'] for p in pages] == [2, 7]
    assert [p['empty'] for p in pages] == [False, True]
    assert all(type(p['timestamp']) is int and p['timestamp'] > 0 for p in pages)
    assert call('deletePage', appid=app_a, page=2) is True
    assert call('deletePage', appid=app_a, page=2) is False
    assert call('loadPage', appid=app_a, page=2)['empty'] is True
    assert not (settings / str(app_a) / '2.json').exists()
    for app in (0, app_b):
        page = 0 if app == 0 else 2
        assert call('loadPage', appid=app, page=page)['data'] == payloads[(app, page)]
    assert [p['page'] for p in call('listPages', appid=app_a)] == [7]
    after = {str(path.relative_to(settings)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in settings.rglob('*') if path.is_file()}
    assert after == {name: digest for name, digest in before.items() if name != str(app_a) + '/2.json'}
    return dict(defaultAndTwoAppNamespaces=True, samePageNumberIsolated=True,
                strokeBytesIndependentlyReadBack=True, emptyPageMetadata=True,
                perAppSelectionPersistedAcrossRestart=True, pageBytesPersistedAcrossRestart=True,
                selectedDeletePreservedOtherPages=True, retainedFilesSha256=after,
                publishedBackendUnmodified=True, syntheticAppIds=[0, app_a, app_b],
                browserVerified=False, realSteamGameSelectionVerified=False,
                realFrameContacted=False, physicalControllerVerified=False)
