#!/usr/bin/env python3
"""拼装智能体上下文（阶段感知）

用法：
    python .structure/scripts/render_context.py                    # 全局上下文
    python .structure/scripts/render_context.py --module backend   # 模块上下文
    python .structure/scripts/render_context.py --module backend --level L2  # 深层上下文

输出拼装好的系统提示词片段到 stdout。
用于将 .structure/ 的相关信息注入智能体的系统提示词。
"""

import json, pathlib, sys

ROOT = pathlib.Path('.').resolve()
STRUCT = ROOT / '.structure'


def read_safe(path):
    try:
        return path.read_text(encoding='utf-8')
    except (FileNotFoundError, PermissionError):
        return ''


def latest_files(directory, pattern, n=1):
    """返回目录下最新的 n 个文件"""
    d = pathlib.Path(directory)
    if not d.exists():
        return []
    files = sorted(d.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:n]


def render(module=None, level='L0'):
    parts = []

    # 1. AGENT.md（始终加载）
    agent = read_safe(STRUCT / 'AGENT.md')
    if agent:
        parts.append(f'<!-- AGENT.md -->\n{agent}')

    # 2. state.json
    state_text = read_safe(STRUCT / 'state.json')
    if state_text:
        state = json.loads(state_text)
        parts.append(f'<!-- state.json -->\n```json\n{state_text}\n```')
        phase = state.get('phase', 'PHASE_0_EMPTY')
    else:
        phase = 'PHASE_0_EMPTY'
        parts.append('<!-- state.json: MISSING -->')

    # 3. 最近 1 条阶段记录
    for f in latest_files(STRUCT / 'phases', '*.yaml', 1):
        parts.append(f'<!-- phase record: {f.name} -->\n```yaml\n{read_safe(f)}\n```')

    # 4. 最近 3 条门禁记录
    gate_dir = STRUCT / 'human-gates'
    if gate_dir.exists():
        gate_files = sorted(
            [f for f in gate_dir.glob('G*.md') if f.name != 'INDEX.md'],
            key=lambda f: f.stat().st_mtime, reverse=True)[:3]
        for f in gate_files:
            parts.append(f'<!-- gate: {f.name} -->\n{read_safe(f)}')

    # 5. 按 phase 加载
    if phase == 'PHASE_1_REQUIREMENTS':
        req_dir = STRUCT / 'requirements'
        if req_dir.exists():
            for f in sorted(req_dir.glob('*.md')):
                parts.append(f'<!-- requirements/{f.name} -->\n{read_safe(f)}')

    elif phase == 'PHASE_2_ARCHITECTURE':
        arch_dir = STRUCT / 'architecture'
        if arch_dir.exists():
            for f in sorted(arch_dir.glob('*.md')):
                parts.append(f'<!-- architecture/{f.name} -->\n{read_safe(f)}')

    elif phase == 'PHASE_3_MODULE_DESIGN':
        if module:
            mc = STRUCT / 'architecture' / 'modules' / f'{module}.yaml'
            if mc.exists():
                parts.append(f'<!-- module card: {module} -->\n```yaml\n{read_safe(mc)}\n```')

    elif phase in ('PHASE_4_IMPLEMENTATION', 'PHASE_5_EVOLUTION'):
        # manifest 子树
        manifest = read_safe(STRUCT / 'manifest.yaml')
        if manifest:
            parts.append(f'<!-- manifest.yaml -->\n```yaml\n{manifest}\n```')

        # tree.md
        tree = read_safe(STRUCT / 'tree.md')
        if tree:
            parts.append(f'<!-- tree.md -->\n{tree}')

        # 最近 changelog
        for f in latest_files(STRUCT / 'changelog', '*.md', 1):
            parts.append(f'<!-- changelog: {f.name} -->\n{read_safe(f)}')

        # BACKLOG
        backlog = read_safe(STRUCT / 'tasks' / 'BACKLOG.md')
        if backlog:
            parts.append(f'<!-- BACKLOG.md -->\n{backlog}')

        # 模块上下文
        if module:
            mod_struct = ROOT / module / '.structure'
            status = read_safe(mod_struct / 'STATUS.md')
            if status:
                parts.append(f'<!-- {module}/STATUS.md -->\n{status}')

            # L2: 加载 coupling
            if level in ('L2', 'L3'):
                coupling = read_safe(STRUCT / 'coupling.md')
                if coupling:
                    parts.append(f'<!-- coupling.md -->\n{coupling}')

            # L3: 加载 API
            if level == 'L3':
                api = read_safe(STRUCT / 'api.md')
                if api:
                    parts.append(f'<!-- api.md -->\n{api}')

    result = '\n\n---\n\n'.join(parts)
    return result


def main():
    module = None
    level = 'L0'
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--module' and i + 1 < len(sys.argv):
            module = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--level' and i + 1 < len(sys.argv):
            level = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    result = render(module, level)
    print(result)

    # 统计
    lines = result.count('\n')
    chars = len(result)
    sys.stderr.write(f'\n--- 上下文统计 ---\n')
    sys.stderr.write(f'行数: {lines}\n')
    sys.stderr.write(f'字符数: {chars}\n')
    sys.stderr.write(f'模块: {module or "全局"}\n')
    sys.stderr.write(f'层级: {level}\n')


if __name__ == '__main__':
    main()
