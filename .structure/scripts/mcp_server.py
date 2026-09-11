#!/usr/bin/env python3
"""structure-keeper MCP Server

零依赖的 MCP 服务器，将 .structure/ 操作暴露为工具。
通过 stdio 通信，JSON-RPC 2.0 协议。

注册方式（Claude Code）：
    claude mcp add structure-keeper -- python .structure/scripts/mcp_server.py

注册方式（Cursor mcp.json）：
    { "structure-keeper": { "command": "python", "args": [".structure/scripts/mcp_server.py"] } }
"""

import json, sys, os, pathlib, datetime, re, traceback

ROOT = pathlib.Path(os.environ.get('STRUCTURE_ROOT', '.')).resolve()
STRUCT = ROOT / '.structure'

# --- MCP Protocol ---

def send(msg):
    """发送 JSON-RPC 消息"""
    data = json.dumps(msg, ensure_ascii=False)
    out = f'Content-Length: {len(data.encode("utf-8"))}\r\n\r\n{data}'
    sys.stdout.write(out)
    sys.stdout.flush()


def recv():
    """接收 JSON-RPC 消息"""
    headers = {}
    while True:
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if line == '':
            break
        if ':' in line:
            k, v = line.split(':', 1)
            headers[k.strip().lower()] = v.strip()
    length = int(headers.get('content-length', 0))
    if length == 0:
        return None
    body = sys.stdin.read(length)
    return json.loads(body)


def respond(id, result):
    send({'jsonrpc': '2.0', 'id': id, 'result': result})


def respond_error(id, code, message):
    send({'jsonrpc': '2.0', 'id': id, 'error': {'code': code, 'message': message}})


# --- Tool implementations ---

def read_safe(path):
    try:
        return path.read_text(encoding='utf-8')
    except (FileNotFoundError, PermissionError):
        return None


def tool_get_phase(args):
    """返回当前阶段和可用动作"""
    sj = STRUCT / 'state.json'
    if not sj.exists():
        return {'phase': 'UNKNOWN', 'error': 'state.json not found'}
    state = json.loads(read_safe(sj))
    phase = state.get('phase', 'UNKNOWN')

    actions = {
        'PHASE_0_EMPTY': ['init-structure'],
        'PHASE_1_REQUIREMENTS': ['edit requirements/', 'record G1'],
        'PHASE_2_ARCHITECTURE': ['edit architecture/', 'record G2'],
        'PHASE_3_MODULE_DESIGN': ['write module cards', 'record G3/G4'],
        'PHASE_4_IMPLEMENTATION': ['acquire lock', 'write code', 'commit'],
        'PHASE_5_EVOLUTION': ['propose new module', 'acquire lock', 'write code'],
    }

    return {
        'phase': phase,
        'entered_at': state.get('phase_entered_at', ''),
        'last_gate': state.get('last_gate', ''),
        'last_gate_decision': state.get('last_gate_decision', ''),
        'available_actions': actions.get(phase, []),
    }


def tool_get_module_context(args):
    """返回模块的上下文（STATUS.md + manifest 条目）"""
    module = args.get('module', '')
    if not module:
        return {'error': 'module parameter required'}

    # 从 manifest 找 path
    mf = read_safe(STRUCT / 'manifest.yaml')
    if not mf:
        return {'error': 'manifest.yaml not found'}

    m = re.search(rf'{module}:\s*\n\s+path:\s*(.+)', mf)
    if not m:
        return {'error': f'module {module} not in manifest'}

    mod_path = m.group(1).strip().strip('"').strip("'").rstrip('/')

    # 读 STATUS.md
    if mod_path == '.':
        status = None
    else:
        status = read_safe(ROOT / mod_path / '.structure' / 'STATUS.md')

    # 从 manifest 提取模块信息（简易解析）
    # 找到模块段落
    lines = mf.split('\n')
    mod_info = []
    in_module = False
    for line in lines:
        if re.match(rf'  {module}:', line):
            in_module = True
            continue
        if in_module:
            if re.match(r'  \w+:', line) and not line.startswith('    '):
                break
            mod_info.append(line)

    return {
        'module': module,
        'path': mod_path,
        'status_md': status or 'not found',
        'manifest_entry': '\n'.join(mod_info),
    }


def tool_acquire_lock(args):
    """获取模块锁"""
    module = args.get('module', '')
    session = args.get('session', 'unknown')
    task = args.get('task', 'unspecified')

    if not module:
        return {'error': 'module parameter required'}

    mf = read_safe(STRUCT / 'manifest.yaml')
    if not mf:
        return {'error': 'manifest.yaml not found'}

    m = re.search(rf'{module}:\s*\n\s+path:\s*(.+)', mf)
    if not m:
        return {'error': f'module {module} not in manifest'}

    mod_path = m.group(1).strip().strip('"').strip("'").rstrip('/')
    if mod_path == '.':
        return {'error': 'root module cannot be locked'}

    status_path = ROOT / mod_path / '.structure' / 'STATUS.md'
    if not status_path.exists():
        return {'error': f'STATUS.md not found at {status_path}'}

    content = status_path.read_text(encoding='utf-8')

    # 检查现有锁
    lock_match = re.search(
        r'## LOCK\s*\n.*?\*\*holder\*\*:\s*(.+)\n.*?\*\*since\*\*:\s*(.+)\n.*?\*\*task\*\*:\s*(.+)',
        content, re.IGNORECASE)

    if lock_match:
        holder = lock_match.group(1).strip()
        since = lock_match.group(2).strip()
        if holder == session:
            pass  # 续锁
        else:
            try:
                since_dt = datetime.datetime.fromisoformat(since)
                age = datetime.datetime.now() - since_dt
                if age <= datetime.timedelta(hours=4):
                    return {
                        'locked': False,
                        'held_by': holder,
                        'since': since,
                        'task': lock_match.group(3).strip(),
                        'error': f'module locked by {holder}',
                    }
            except ValueError:
                pass

    # 写入锁
    now = datetime.datetime.now().isoformat()
    lock_section = (
        f'\n## LOCK\n\n'
        f'- **holder**: {session}\n'
        f'- **since**: {now}\n'
        f'- **task**: {task}\n'
    )

    if '## LOCK' in content:
        content = re.sub(r'\n## LOCK\n.*?(?=\n## |\Z)', lock_section, content, flags=re.DOTALL)
    else:
        content += lock_section

    status_path.write_text(content, encoding='utf-8')
    return {'locked': True, 'module': module, 'session': session, 'since': now}


def tool_release_lock(args):
    """释放模块锁"""
    module = args.get('module', '')
    if not module:
        return {'error': 'module parameter required'}

    mf = read_safe(STRUCT / 'manifest.yaml')
    if not mf:
        return {'error': 'manifest.yaml not found'}

    m = re.search(rf'{module}:\s*\n\s+path:\s*(.+)', mf)
    if not m:
        return {'error': f'module {module} not in manifest'}

    mod_path = m.group(1).strip().strip('"').strip("'").rstrip('/')
    status_path = ROOT / mod_path / '.structure' / 'STATUS.md'
    if not status_path.exists():
        return {'error': 'STATUS.md not found'}

    content = status_path.read_text(encoding='utf-8')
    if '## LOCK' not in content:
        return {'released': True, 'note': 'no lock existed'}

    content = re.sub(r'\n## LOCK\n.*?(?=\n## |\Z)', '', content, flags=re.DOTALL)
    status_path.write_text(content, encoding='utf-8')
    return {'released': True, 'module': module}


def tool_record_gate(args):
    """记录人工门禁"""
    gate = args.get('gate', '')
    decision = args.get('decision', '')
    human = args.get('human', 'unknown')
    rationale = args.get('rationale', '')

    if not gate or not decision:
        return {'error': 'gate and decision required'}

    now = datetime.datetime.now()
    fname = f'{gate}-{now.date()}.md'
    fpath = STRUCT / 'human-gates' / fname
    fpath.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Gate {gate}

- **Gate**: {gate}
- **Timestamp**: {now.isoformat()}
- **Human**: {human}
- **Decision**: {decision}

## Rationale
{rationale or '（未填写）'}
"""
    fpath.write_text(content, encoding='utf-8')

    # 更新 state.json
    sj = STRUCT / 'state.json'
    if sj.exists():
        state = json.loads(sj.read_text(encoding='utf-8'))
        state['last_gate'] = gate
        state['last_gate_decision'] = decision
        sj.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')

    # 追加 INDEX
    idx = STRUCT / 'human-gates' / 'INDEX.md'
    if idx.exists():
        with open(idx, 'a', encoding='utf-8') as f:
            f.write(f'| {gate} | {now.date()} | {human} | {decision} | - |\n')

    return {'recorded': True, 'file': str(fpath), 'gate': gate, 'decision': decision}


def tool_advance_phase(args):
    """阶段跃迁"""
    target = args.get('to', '')
    bootstrap = args.get('bootstrap', False)

    if not target:
        return {'error': 'to parameter required'}

    sj = STRUCT / 'state.json'
    if not sj.exists():
        return {'error': 'state.json not found'}

    state = json.loads(sj.read_text(encoding='utf-8'))
    current = state.get('phase', 'PHASE_0_EMPTY')

    if current == target:
        return {'advanced': False, 'reason': f'already at {target}'}

    now = datetime.datetime.now()
    state['phase'] = target
    state['phase_entered_at'] = now.isoformat()
    if bootstrap:
        state['bootstrap'] = True
    sj.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')

    # 写阶段记录
    phase_dir = STRUCT / 'phases'
    phase_dir.mkdir(parents=True, exist_ok=True)
    fname = f'{current[:7]}-to-{target[:7]}-{now.date()}.yaml'
    record = f'from: {current}\nto: {target}\ntimestamp: "{now.isoformat()}"\n'
    if bootstrap:
        record += 'bootstrap: true\n'
    (phase_dir / fname).write_text(record, encoding='utf-8')

    return {'advanced': True, 'from': current, 'to': target}


def tool_verify_structure(args):
    """校验 .structure/ 完整性"""
    errors = []
    warnings = []

    required = ['AGENT.md', 'state.json', 'manifest.yaml', 'tree.md']
    for f in required:
        if not (STRUCT / f).exists():
            errors.append(f'{f} missing')

    sj = STRUCT / 'state.json'
    if sj.exists():
        try:
            state = json.loads(sj.read_text(encoding='utf-8'))
            phase = state.get('phase', '')
            valid = ['PHASE_0_EMPTY', 'PHASE_1_REQUIREMENTS', 'PHASE_2_ARCHITECTURE',
                     'PHASE_3_MODULE_DESIGN', 'PHASE_4_IMPLEMENTATION', 'PHASE_5_EVOLUTION']
            if phase not in valid:
                errors.append(f'invalid phase: {phase}')
        except json.JSONDecodeError:
            errors.append('state.json is invalid JSON')

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
    }


def tool_list_locks(args):
    """查看所有模块锁状态"""
    mf = read_safe(STRUCT / 'manifest.yaml')
    if not mf:
        return {'error': 'manifest.yaml not found'}

    modules = re.findall(r'^  (\w+):', mf, re.MULTILINE)
    locks = {}
    for mod in modules:
        m = re.search(rf'{mod}:\s*\n\s+path:\s*(.+)', mf)
        if not m:
            continue
        mod_path = m.group(1).strip().strip('"').strip("'").rstrip('/')
        if mod_path == '.':
            continue
        status_path = ROOT / mod_path / '.structure' / 'STATUS.md'
        content = read_safe(status_path)
        if content and '## LOCK' in content:
            lock_match = re.search(
                r'\*\*holder\*\*:\s*(.+)\n.*?\*\*since\*\*:\s*(.+)\n.*?\*\*task\*\*:\s*(.+)',
                content, re.IGNORECASE)
            if lock_match:
                locks[mod] = {
                    'holder': lock_match.group(1).strip(),
                    'since': lock_match.group(2).strip(),
                    'task': lock_match.group(3).strip(),
                }
            else:
                locks[mod] = 'free'
        else:
            locks[mod] = 'free'
    return {'locks': locks}


# --- Tool registry ---

TOOLS = [
    {
        'name': 'get_phase',
        'description': '返回当前项目阶段和可用动作',
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'get_module_context',
        'description': '返回指定模块的 STATUS.md 和 manifest 条目',
        'inputSchema': {
            'type': 'object',
            'properties': {'module': {'type': 'string', 'description': '模块名（如 backend）'}},
            'required': ['module'],
        },
    },
    {
        'name': 'acquire_lock',
        'description': '获取模块锁（写代码前必须先获取）',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'module': {'type': 'string', 'description': '模块名'},
                'session': {'type': 'string', 'description': '会话 ID'},
                'task': {'type': 'string', 'description': '任务描述'},
            },
            'required': ['module', 'session', 'task'],
        },
    },
    {
        'name': 'release_lock',
        'description': '释放模块锁',
        'inputSchema': {
            'type': 'object',
            'properties': {'module': {'type': 'string', 'description': '模块名'}},
            'required': ['module'],
        },
    },
    {
        'name': 'list_locks',
        'description': '查看所有模块的锁状态',
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'record_gate',
        'description': '记录人工介入门禁',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'gate': {'type': 'string', 'description': '门禁 ID（如 G2）'},
                'decision': {'type': 'string', 'enum': ['APPROVED', 'REJECTED', 'CONDITIONAL', 'OVERRIDDEN']},
                'human': {'type': 'string', 'description': '人类标识'},
                'rationale': {'type': 'string', 'description': '理由'},
            },
            'required': ['gate', 'decision'],
        },
    },
    {
        'name': 'advance_phase',
        'description': '阶段跃迁（需要对应门禁已批准）',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'to': {'type': 'string', 'description': '目标阶段'},
                'bootstrap': {'type': 'boolean', 'description': '跳过门禁检查', 'default': False},
            },
            'required': ['to'],
        },
    },
    {
        'name': 'verify_structure',
        'description': '校验 .structure/ 完整性',
        'inputSchema': {'type': 'object', 'properties': {}},
    },
]

TOOL_FNS = {
    'get_phase': tool_get_phase,
    'get_module_context': tool_get_module_context,
    'acquire_lock': tool_acquire_lock,
    'release_lock': tool_release_lock,
    'list_locks': tool_list_locks,
    'record_gate': tool_record_gate,
    'advance_phase': tool_advance_phase,
    'verify_structure': tool_verify_structure,
}


# --- Main loop ---

def handle(msg):
    method = msg.get('method', '')
    id = msg.get('id')
    params = msg.get('params', {})

    if method == 'initialize':
        respond(id, {
            'protocolVersion': '2024-11-05',
            'capabilities': {'tools': {}},
            'serverInfo': {
                'name': 'structure-keeper',
                'version': '1.1.0',
            },
        })
    elif method == 'notifications/initialized':
        pass  # notification, no response
    elif method == 'tools/list':
        respond(id, {'tools': TOOLS})
    elif method == 'tools/call':
        name = params.get('name', '')
        arguments = params.get('arguments', {})
        fn = TOOL_FNS.get(name)
        if not fn:
            respond(id, {
                'content': [{'type': 'text', 'text': json.dumps({'error': f'unknown tool: {name}'})}],
                'isError': True,
            })
        else:
            try:
                result = fn(arguments)
                respond(id, {
                    'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False, indent=2)}],
                })
            except Exception as e:
                respond(id, {
                    'content': [{'type': 'text', 'text': json.dumps({'error': str(e), 'trace': traceback.format_exc()})}],
                    'isError': True,
                })
    elif method == 'ping':
        respond(id, {})
    else:
        if id is not None:
            respond_error(id, -32601, f'Method not found: {method}')


def main():
    while True:
        msg = recv()
        if msg is None:
            break
        handle(msg)


if __name__ == '__main__':
    main()
