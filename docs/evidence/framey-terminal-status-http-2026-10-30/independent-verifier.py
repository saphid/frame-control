from pathlib import Path
import ast,base64,hashlib,importlib.util,json,subprocess
root=Path('/tmp/framey-terminal-browser-candidate-mppkd9qczt');out=Path('/tmp/framey-terminal-status-http-local2-mppkd9qczt');head='ca945552e1b69afb6e0cfd6b1dd94bf47a2c8238';sha=lambda d:hashlib.sha256(d).hexdigest()
i=json.loads((out/'inputs.json').read_text());r=json.loads((out/'result.json').read_text());assert r['inputs']==i and i['sourceRevision']==head and i['architecture']=='x86_64'
for k in ('networkDevice','hostBusExposed','realFrameContacted','productionAdaptationEnabled'):assert i[k] is False,k
assert i['productionHttpRequested'] is True and i['loaderSha256']=='e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181'
for name,digest in i['sourceSha256'].items():assert sha(subprocess.check_output(['git','show',head+':'+name],cwd=root))==digest,name
module=ast.parse(subprocess.check_output(['git','show',head+':scripts/framey-test-terminal-browser.py'],cwd=root));bootstrap=next(ast.literal_eval(n.value)for n in module.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='BOOTSTRAP'for t in n.targets));assert sha(bootstrap.encode())==i['bootstrapSha256']
spec=importlib.util.spec_from_file_location('terminal_status_codec',root/'tests/decky-runtime/guest_result.py');codec=importlib.util.module_from_spec(spec);spec.loader.exec_module(codec);packet=(out/'guest-result.packet').read_bytes();assert codec.decode(packet)==r['guest'] and r['guestResultPacket']==dict(bytes=len(packet),sha256=sha(packet))
assert r['success'] is True and r['ownedQemuReaped'] is True;g=r['guest'];assert g['success'] is True and g['probeExitStatus']==0 and g['ownedUserManagerStopped'] is True and g['realFrameContacted'] is False
terminal=g['terminal'];abi=terminal['candidate']['loaderPythonAbi'];assert abi['architecture']=='x86_64' and abi['versionInfo'][:3]==[3,14,8]
life=terminal['terminalLifecycle']
for key in ('privateInputOutput','resizeVerified','explicitRemoveReaped','reloadReaped','unrelatedProcessPreserved','configPersistedAcrossPluginReload'):assert life[key] is True,key
assert life['reloadAfter'] is None
native=next(c['result']for c in life['calls']if c['method']=='private_pty_output');assert bytes.fromhex(native['markerHex'])==b'framey-owned-terminal\n'
for line in ('\r\n31 97\r\n','\r\nframey-owned-output\r\n','\r\nframey-owned-stderr\r\n'):assert line in native['output']
p=terminal['terminalBrowser']
for key in ('success','actualDeckyUserService','syntheticCef','syntheticManagedReceipt','syntheticInput','productionParentUnchanged','productionPanelUnchanged','productionHttpHandler','productionMethodScript','productionEventScript','productionLocalSshWrapper','productionEventListenerCleanup','browserShellReaped','ownedTargetClosed','ownedBrowserReaped','httpServerStopped','sshObserverRemoved','ownedDeckyServiceStopped','originalUnitRestored','ownedBundleRemoved','productionStatusCommandUnchanged'):assert p[key] is True,key
for key in ('realSteamCef','realFrameContacted','managedInstallVerified','productionAdaptationEnabled','physicalControllerVerified','browserSandboxDisabled'):assert p[key] is False,key
assert p['iframe']==dict(sandbox='allow-scripts allow-popups',src='/framey/panel/65')
assert [s['stage']for s in p['stages']]==['terminal','output','removed'] and all(not s['errors']for s in p['stages']);assert any(row.strip()=='framey-browser-output'for row in p['stages'][1]['terminalRows'])
assert '\r\nframey-browser-output\r\n' in ''.join(e['args'][0]for e in p['deliveredEvents'])
assert p['privateMarkerSha256']==sha(b'framey-browser-terminal\n');assert p['requests'] and all(x['httpStatus']==200 for x in p['requests'])
assert p['statusHttpRequests'] and all(x['httpStatus']==200 and x['running']is True and x['pluginCount']==1 and x['elapsedSeconds']<15 for x in p['statusHttpRequests'])
assert not p.get('statusFailureDiagnostic')
for name,digest in p['uiSourceFingerprints'].items():assert i['sourceSha256'][name]==digest
shell=p['browserShell'];chain=shell['ancestryToDeckyService'];assert shell['uid']==1100 and chain[0]==shell['pid'] and chain[-1]==p['deckyMainPid'] and len(chain)==len(set(chain))
assert p['sandboxedRendererPids']
for render in p['sandboxedRendererPids']:assert render['seccomp']==2 and render['noNewPrivs']==1
stop=p['ownedDeckyStop'];assert stop['activeState']=='inactive' and stop['result']=='success' and stop['mainPidAfter']==0 and stop['execMainCode']==stop['execMainStatus']=='0' and 0<=stop['elapsedSeconds']<90
assert set(p['screenshots'])=={'terminal','output','removed'};captures={}
for name,encoded in p['screenshots'].items():
 raw=base64.b64decode(encoded,validate=True);assert raw==(out/(name+'.png')).read_bytes() and raw.startswith(b'\x89PNG\r\n\x1a\n');captures[name]=sha(raw)
proof=dict(head=head,architecture='x86_64',sourceFingerprintsVerified=len(i['sourceSha256']),bootstrapVerified=True,resultPacketSha256=sha(packet),resultPacketVerified=True,actualNativeLifecycleVerified=True,productionHttpAndEventRoundTripVerified=True,statusRequests=p['statusHttpRequests'],ownedDeckyStop=stop,allOwnedCleanupVerified=True,captureSha256=captures,capturesVisuallyInspected=False,syntheticCef=True,syntheticManagedReceipt=True,syntheticInput=True,managedInstallVerified=False,productionAdaptationEnabled=False,realSteamCef=False,realFrameContacted=False,physicalControllerVerified=False,nativeArmVerified=False)
(out/'verified.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
