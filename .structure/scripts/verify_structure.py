#!/usr/bin/env python3
"""校验 .structure/ 完整性

用法：
    python .structure/scripts/verify_structure.py
    python .structure/scripts/verify_structure.py --strict  # CI 模式，任何警告变错误

返回码：0 = 通过，1 = 有错误
"""

import json, pathlib, re, sys

ROOT = pathlib.Path('.').resolve()
STRUCT = ROOT / '.structure'

errors = []
warnings = []


def error(msg):
    errors.append(msg)
    print(f'  ✗ ERROR: {msg}')


def warn(msg):
    warnings.append(msg)
    print(f'  ⚠ WARN:  {msg}')


def ok(msg):
    print(f'  ✓ {msg}')


def check_core_files():
    """检查核心文件是否存在"""
    print('检查核心文件...')
    required = [
        'AGENT.md', 'STRUCTURE.md', 'state.json', 'manifest.yaml',
        'INDEX.md', 'tree.md',
    ]
    for f in required:
        p = STRUCT / f
        if p.exists():
            ok(f)
        else:
            error(f'{f} 缺失')


def check_state():
    """检查 state.json"""
    print('检查 state.json...')
    sj = STRUCT / 'state.json'
    if not sj.exists():
        error('state.json 缺失')
        return None
    try:
        state = json.loads(sj.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        error(f'state.json JSON 格式错误: {e}')
        return None

    phase = state.get('phase')
    valid_phases = [
        'PHASE_0_EMPTY', 'PHASE_1_REQUIREMENTS', 'PHASE_2_ARCHITECTURE',
        'PHASE_3_MODULE_DESIGN', 'PHASE_4_IMPLEMENTATION', 'PHASE_5_EVOLUTION',
    ]
    if phase not in valid_phases:
        error(f'state.json.phase 无效: {phase}')
    else:
        ok(f'phase = {phase}')

    if 'version' not in state:
        warn('state.json 缺少 version 字段')

    return state


def check_manifest():
    """检查 manifest.yaml 基本结构"""
    print('检查 manifest.yaml...')
    mf = STRUCT / 'manifest.yaml'
    if not mf.exists():
        error('manifest.yaml 缺失')
        return
    text = mf.read_text(encoding='utf-8')
    if 'modules:' not in text:
        error('manifest.yaml 缺少 modules: 段')
        return
    # 提取模块名
    modules = re.findall(r'^  (\w+):', text, re.MULTILINE)
    if not modules:
        warn('manifest.yaml 中没有发现模块定义')
    else:
        ok(f'manifest 包含 {len(modules)} 个模块: {", ".join(modules)}')
    return modules


def check_gates(state):
    """检查门禁一致性"""
    print('检查人工门禁...')
    gate_dir = STRUCT / 'human-gates'
    if not gate_dir.exists():
        warn('human-gates/ 目录不存在')
        return

    idx = gate_dir / 'INDEX.md'
    if not idx.exists():
        warn('human-gates/INDEX.md 缺失')
    else:
        ok('human-gates/INDEX.md 存在')

    gate_files = [f for f in gate_dir.glob('G*.md') if f.name != 'INDEX.md']
    ok(f'{len(gate_files)} 个门禁记录')

    # 检查每个门禁的 Human 字段
    for gf in gate_files:
        content = gf.read_text(encoding='utf-8')
        human_match = re.search(r'\*\*Human\*\*:\s*(.+)', content)
        if not human_match:
            warn(f'{gf.name}: 缺少 Human 字段')
        elif 'TODO' in human_match.group(1) or not human_match.group(1).strip():
            warn(f'{gf.name}: Human 字段未填写')
        else:
            ok(f'{gf.name}: Human = {human_match.group(1).strip()}')

    # 检查 state 中的 last_gate 是否有对应记录
    if state:
        last_gate = state.get('last_gate', '')
        if last_gate:
            found = any(last_gate in gf.name for gf in gate_files)
            if found:
                ok(f'state.last_gate ({last_gate}) 有对应记录')
            else:
                warn(f'state.last_gate ({last_gate}) 没找到对应记录文件')


def check_phases():
    """检查阶段记录"""
    print('检查阶段记录...')
    phase_dir = STRUCT / 'phases'
    if not phase_dir.exists():
        warn('phases/ 目录不存在')
        return
    records = list(phase_dir.glob('*.yaml'))
    ok(f'{len(records)} 条阶段跃迁记录')


def check_submodules(modules):
    """检查子模块 .structure/ 完整性"""
    print('检查子模块...')
    if not modules:
        return
    for mod in modules:
        # 从 manifest 找 path
        mf = (STRUCT / 'manifest.yaml').read_text(encoding='utf-8')
        path_match = re.search(rf'{mod}:\s*\n\s+path:\s*(.+)', mf)
        if not path_match:
            continue
        mod_path = path_match.group(1).strip().strip('"').strip("'").rstrip('/')
        if mod_path == '.':
            continue

        status = ROOT / mod_path / '.structure' / 'STATUS.md'
        if status.exists():
            ok(f'{mod}: STATUS.md 存在')
            # 检查 TODO 残留
            content = status.read_text(encoding='utf-8')
            todo_count = content.count('TODO')
            if todo_count > 0:
                warn(f'{mod}: STATUS.md 中有 {todo_count} 个 TODO 未填')
        else:
            warn(f'{mod}: STATUS.md 缺失 ({status})')


def check_changelog():
    """检查 changelog"""
    print('检查 changelog...')
    cl_dir = STRUCT / 'changelog'
    if not cl_dir.exists():
        warn('changelog/ 目录不存在')
        return
    entries = list(cl_dir.glob('*.md'))
    ok(f'{len(entries)} 条变更日志')


def check_phase_code_guard(state):
    """检查阶段与代码变更的一致性（简化版）"""
    print('检查阶段护栏...')
    if not state:
        return
    phase = state.get('phase', '')
    if phase in ('PHASE_1_REQUIREMENTS', 'PHASE_2_ARCHITECTURE', 'PHASE_3_MODULE_DESIGN'):
        # 在这些阶段不应该有新增的代码文件（简化检查：看 git status）
        import subprocess
        try:
            r = subprocess.run(['git', 'status', '--porcelain'],
                               capture_output=True, text=True, check=False)
            if r.returncode == 0:
                for line in r.stdout.strip().split('\n'):
                    if not line:
                        continue
                    status = line[:2]
                    filepath = line[3:]
                    if status.startswith('A') and not filepath.startswith('.structure/'):
                        ext = pathlib.Path(filepath).suffix
                        if ext in {'.py', '.js', '.ts', '.go', '.rs', '.java'}:
                            warn(f'阶段 {phase} 中有新增代码文件: {filepath}')
        except FileNotFoundError:
            pass
    else:
        ok(f'阶段 {phase} 允许代码变更')


def main():
    strict = '--strict' in sys.argv
    print(f'=== .structure/ 完整性校验 ===')
    print(f'根目录: {ROOT}')
    print()

    if not STRUCT.exists():
        error('.structure/ 目录不存在')
        sys.exit(1)

    check_core_files()
    print()
    state = check_state()
    print()
    modules = check_manifest()
    print()
    check_gates(state)
    print()
    check_phases()
    print()
    check_submodules(modules)
    print()
    check_changelog()
    print()
    check_phase_code_guard(state)

    print()
    print(f'=== 结果 ===')
    print(f'  错误: {len(errors)}')
    print(f'  警告: {len(warnings)}')

    if errors:
        print()
        print('错误列表:')
        for e in errors:
            print(f'  - {e}')
        sys.exit(1)

    if strict and warnings:
        print()
        print('严格模式：警告视为错误')
        sys.exit(1)

    print('  ✓ 通过')


if __name__ == '__main__':
    main()
