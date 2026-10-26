import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const active = new WeakSet();

function skillInfo(directory) {
  const filename = path.join(directory, 'SKILL.md');
  const text = fs.readFileSync(filename, 'utf8');
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text);
  if (!match) throw new Error(`Skill frontmatter missing: ${filename}`);
  const fields = {};
  let key;
  for (const line of match[1].split(/\r?\n/)) {
    const field = /^(name|description):\s*(.*)$/.exec(line);
    if (field) {
      key = field[1];
      fields[key] = /^[>|][+-]?$/.test(field[2]) ? '' : field[2];
    } else if (/^\S/.test(line)) key = undefined;
    else if (key && line.trim()) fields[key] += ` ${line.trim()}`;
  }
  return {
    id: path.basename(directory), name: (fields.name || path.basename(directory)).replace(/^(['"])(.*)\1$/, '$2'),
    description: (fields.description || '').trim().replace(/^(['"])(.*)\1$/, '$2'),
    path: filename, content: match[2],
  };
}

function bridge(ctx, event, payload) {
  return new Promise((resolve, reject) => {
    const child = spawn(ctx.options?.python || process.env.WM_PYTHON || 'python',
      [path.join(root, 'scripts/wm.py'), 'hook', 'opencode', event], {
        shell: false, windowsHide: true,
        env: {...process.env, PYTHONUTF8: '1', WM_PLUGIN_ROOT: root},
      });
    let stdout = '', stderr = '', settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(value);
    };
    const timer = setTimeout(() => {
      child.kill();
      finish(new Error('WM Python bridge timed out'));
    }, 10000);
    child.on('error', (error) => finish(error));
    child.stdin.on('error', (error) => finish(error));
    child.stdout.on('data', chunk => {
      stdout += chunk.toString('utf8');
      if (stdout.length > 1024 * 1024) {
        child.kill(); finish(new Error('WM bridge output exceeded limit'));
      }
    });
    child.stderr.on('data', chunk => { stderr = (stderr + chunk.toString('utf8')).slice(-8192); });
    child.on('close', (code) => {
      if (code !== 0) return finish(new Error(`WM bridge exited ${code}: ${stderr}`));
      try {
        const result = JSON.parse(stdout);
        if (!result || Array.isArray(result) || typeof result !== 'object' || result.systemMessage) {
          throw new Error(result?.systemMessage || 'Invalid WM bridge output');
        }
        finish(null, result);
      } catch (error) { finish(error); }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

async function sessionPayload(ctx, event) {
  if (!event.sessionID || typeof ctx.session.get !== 'function') throw new Error('WM requires session identity');
  const session = await ctx.session.get({ sessionID: event.sessionID });
  if (!session || session.id !== event.sessionID) throw new Error('WM session lookup identity mismatch');
  const directory = session.directory || session.location?.directory;
  if (typeof directory !== 'string' || !path.isAbsolute(directory)) throw new Error('WM session directory unavailable');
  return {cwd: directory, session_id: session.id, parentID: session.parentID,
    tool_name: event.tool, tool_input: event.input};
}

export default {
  id: 'wm-ai-coding',
  async setup(ctx) {
    if (active.has(ctx)) return;
    if (!ctx.skill?.transform || !ctx.session?.hook || !ctx.tool?.hook) {
      throw new Error('WM requires the OpenCode v2 skill/session/tool plugin API');
    }
    active.add(ctx);
    const registrations = [];
    const cleanup = async () => {
      active.delete(ctx);
      for (const registration of registrations.reverse()) await registration?.dispose();
    };
    try {
      const skills = [];
      for (const entry of fs.readdirSync(path.join(root, 'skills'), {withFileTypes:true})) {
        const directory = path.join(root, 'skills', entry.name);
        if (!entry.isDirectory() || !fs.existsSync(path.join(directory, 'SKILL.md'))) continue;
        try { skills.push(skillInfo(directory)); }
        catch (error) { console.error('[wm-ai-coding] skill read failed:', error); }
      }
      registrations.push(await ctx.skill.transform(editor => {
        for (const skill of skills) {
          try { editor.add(skill); }
          catch (error) { console.error(`[wm-ai-coding] skill ${skill.id} rejected:`, error); }
        }
      }));
      if (!ctx.mcp?.transform) throw new Error('WM requires OpenCode v2 MCP transforms');
      const mcp = JSON.parse(fs.readFileSync(path.join(root, 'mcp.json'), 'utf8'));
      registrations.push(await ctx.mcp.transform(editor => {
        for (const [name, server] of Object.entries(mcp.mcpServers)) {
          editor.set(`wm_${name}`, {
            type:'local',
            command:[ctx.options?.python || process.env.WM_PYTHON || server.command,
              ...server.args.map(arg => arg.replaceAll('${PLUGIN_ROOT}', root))],
            environment:server.env || {},
          });
        }
      }));
      registrations.push(await ctx.session.hook('context', async event => {
        // The transient model context is rebuilt per step. Replace only our own
        // system block, keeping the static contract once and live brief current.
        const payload = await sessionPayload(ctx, event);
        const result = await bridge(ctx, 'context', payload);
        if (typeof result.context !== 'string') throw new Error('WM context missing');
        event.system ??= [];
        event.system = event.system.filter(part => !(part.type === 'text' && part.text.startsWith('<WM_CONTEXT>')));
        event.system.push({type:'text', text:`<WM_CONTEXT>\n${result.context}\n</WM_CONTEXT>`});
      }));
      registrations.push(await ctx.tool.hook('execute.before', async event => {
        try {
          const result = await bridge(ctx, 'PreToolUse', await sessionPayload(ctx, event));
          if (result.allowed === false) throw new Error(`WM denied: ${result.reason}`);
        } catch (cause) {
          // Native v2 execute.before failures use the Tool.Error tagged schema.
          // Keep the schema-compatible tag without importing a second SDK runtime.
          const failure = new Error(`WM tool policy failed: ${cause.message || cause}`);
          failure._tag = 'Tool.Error';
          throw failure;
        }
        // No native permission is granted here; the host continues its own flow.
      }));
      registrations.push(await ctx.tool.hook('execute.after', async event => {
        try { await bridge(ctx, 'PostToolUse', await sessionPayload(ctx, event)); }
        catch (error) { console.error('[wm-ai-coding] post-tool evidence reminder failed:', error); }
      }));
      if (process.env.WM_HOOK_TRACE) {
        try {
          fs.appendFileSync(process.env.WM_HOOK_TRACE, JSON.stringify({
            time:new Date().toISOString(), host:'opencode', event:'PluginReady',
            installed_root:root, skills_discovered:skills.length,
          }) + '\n', 'utf8');
        } catch (error) { console.error('[wm-ai-coding] activation trace unavailable:', error); }
      }
      return cleanup;
    } catch (error) { await cleanup(); throw error; }
  },
};
