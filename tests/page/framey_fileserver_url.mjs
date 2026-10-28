import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(process.argv[2], 'utf8');
const testSource = source.replace(/export \{ index as default \};/, 'globalThis.__Content = Content;');
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
