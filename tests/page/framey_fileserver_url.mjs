import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(process.argv[2], 'utf8');
const testSource = source.replace(/export \{ index as default \};/,
  'globalThis.__Content = Content; globalThis.__SettingsPage = SettingsPage;');
assert.notEqual(testSource, source, 'official module export must be present');

const DFL = new Proxy({
  definePlugin: factory => factory(),
  staticClasses: {Title: 'title'},
}, {get(target, name) { return target[name] ?? name; }});
const createElement = (type, props, ...children) => ({type, props: props ?? {}, children});

for (const allow_uploads of [false, true]) {
  const SP_REACT = {
    createElement,
    createContext: value => ({value}),
    useState: initial => [{...initial, server_running: true,
      ip_address: '192.0.2.5', port: 8421, allow_uploads}, () => {}],
    useEffect() {},
  };
  const window = {SP_REACT,
    __DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit: {
      connect: () => ({_version: 2, callable: () => async () => ({}), openFilePicker: async () => ({})}),
    },
  };
  const context = vm.createContext({window, SP_REACT, DFL, setInterval() {}, clearInterval() {}});
  vm.runInContext(testSource, context);
  const tree = context.__Content();
  const fields = [];
  function visit(value) {
    if (!value || typeof value !== 'object') return;
    if (value.type === DFL.Field) fields.push(value);
    for (const child of value.children ?? []) visit(child);
  }
  visit(tree);
  const addresses = fields.filter(field => field.props.label === 'Server Address');
  assert.equal(addresses.length, 1);
  assert.equal(addresses[0].children.join(''), 'https://192.0.2.5:8421');
  assert.equal(fields.filter(field => field.children.join('').includes('steamdeck')).length, 0);
}

// The official directory button needs Decky's native path picker. The exact
// managed bundle provides an explicit path field inside this plugin instead.
let formState;
let stateIndex = 0;
let pickerCalls = 0;
let submitted;
const SP_REACT = {
  createElement,
  createContext: value => ({value}),
  useState: initial => {
    const index = stateIndex++;
    if (index === 0) return [formState ?? initial, value => {formState = value;}];
    return [initial, () => {}];
  },
  useRef: () => ({current:null}),
  useEffect() {},
};
const window = {SP_REACT,
  __DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit: {
    connect: () => ({_version: 2, callable: () => async () => ({}),
      openFilePicker: async () => {pickerCalls++; return {path:'/unexpected'};}}),
  },
};
const context = vm.createContext({window, SP_REACT, DFL, setInterval() {}, clearInterval() {}});
vm.runInContext(testSource, context);
const props = {port:8421, timeout:5, directory:'/home/steamos/Downloads',
  history:[], allow_uploads:false, disable_thumbnails:true,
  handleSubmit: async (...values) => {submitted=values;}, closeModal() {}};
function visit(value, found=[]) {
  if (!value || typeof value !== 'object') return found;
  found.push(value);
  for (const child of value.children ?? []) visit(child, found);
  return found;
}
stateIndex = 0;
let page = context.__SettingsPage(props);
let field = visit(page).find(value => value.type === DFL.TextField &&
  value.props.label === 'Directory to share (absolute path)');
assert.ok(field, 'managed panel must offer explicit directory entry');
assert.equal(field.props.value, '/home/steamos/Downloads');
field.props.onChange({currentTarget:{value:'/home/steamos/Test Folder'}});
stateIndex = 0;
page = context.__SettingsPage(props);
field = visit(page).find(value => value.type === DFL.TextField &&
  value.props.label === 'Directory to share (absolute path)');
assert.equal(field.props.value, '/home/steamos/Test Folder');
await page.props.onCancel();
assert.equal(submitted[2], '/home/steamos/Test Folder');
assert.equal(pickerCalls, 0);
