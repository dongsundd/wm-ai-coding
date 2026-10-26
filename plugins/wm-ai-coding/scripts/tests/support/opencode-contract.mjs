import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const { default: plugin } = await import(pathToFileURL(process.argv[2]));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-opencode-'));
try {
  const hooks = new Map();
  const entries = new Map();
  const servers = new Map();
  const context = {
    location: { directory: path.dirname(directory) },
    options: {},
    mcp: { transform: async fn => { fn({set:(id, config) => servers.set(id, config)}); return {dispose:async()=>servers.clear()}; } },
    skill: { transform: async (fn) => { fn({
      list: () => [...entries.values()],
      get: (id) => entries.get(id),
      add: (info) => {
        assert.equal(typeof info.path, 'string');
        assert.ok(fs.existsSync(info.path));
        if (info.id === 'rust-development') throw new Error('one rejected skill');
        entries.set(info.id, info);
      },
    }); return { dispose: async () => entries.clear() }; } },
    session: {
      get: async ({sessionID}) => ({ id: sessionID, location:{directory}, ...(sessionID === 'child' ? {parentID: 'parent'} : {}) }),
      hook: async (name, fn) => { hooks.set(name, fn); return {dispose: async () => hooks.delete(name)}; },
    },
    tool: { hook: async (name, fn) => { hooks.set(name, fn); return {dispose: async () => hooks.delete(name)}; } },
  };
  const cleanup = await plugin.setup(context);
  assert.equal(entries.size, 23);
  assert.equal(servers.size, 2);
  assert.equal(servers.get('wm_codegraph').type, 'local');
  assert.ok(servers.get('wm_codegraph').command[1].endsWith('scripts/wm.py'));
  assert.ok(path.isAbsolute(servers.get('wm_codegraph').command[1]));
  assert.equal(entries.get('development-workflow').name, 'development-workflow');
  assert.match(entries.get('development-workflow').description, /Coordinate/);
  // Duplicate setup on the same context must not register another lifecycle.
  assert.equal(await plugin.setup(context), undefined);
  const event = { sessionID: 'main', system: [], messages: [{role:'user', content:[{type:'text',text:'hello'}]}] };
  await hooks.get('context')(event);
  await hooks.get('context')(event);
  assert.equal(event.system.filter(p => p.text.includes('WM_BOOTSTRAP')).length, 1);
  assert.match(event.system[0].text, /patchText/);
  const child = {sessionID:'child',system:[],messages:[]};
  await hooks.get('context')(child);
  assert.match(child.system[0].text, /WM_WORKER/);
  assert.doesNotMatch(child.system[0].text, /WM_BOOTSTRAP/);
  // Real bridge failure must reject the tool call, never silently permit it.
  context.options.python = path.join(directory, 'missing-python');
  await assert.rejects(hooks.get('execute.before')({sessionID:'main',tool:'write',input:{filePath:'a'}}),
    error => error._tag === 'Tool.Error');
  await cleanup();
  assert.equal(hooks.size, 0);
  console.log('OpenCode contract passed');
} finally {
  fs.rmSync(directory, {recursive:true,force:true});
}
