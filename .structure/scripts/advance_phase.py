#!/usr/bin/env python3
"""阶段跃迁（带门禁校验）

用法：
    python .structure/scripts/advance_phase.py --to PHASE_3_MODULE_DESIGN
    python .structure/scripts/advance_phase.py --to PHASE_4_IMPLEMENTATION --bootstrap
"""

import argparse, datetime, json, pathlib, subprocess, sys

ROOT = pathlib.Path('.').resolve()
STRUCT = ROOT / '.structure'

PHASES = [
    'PHASE_0_EMPTY',
    'PHASE_1_REQUIREMENTS',
    'PHASE_2_ARCHITECTURE',
    'PHASE_3_MODULE_DESIGN',
    'PHASE_4_IMPLEMENTATION',
    'PHASE_5_EVOLUTION',
]

REQUIRED_GATES = {
    'PHASE_1_REQUIREMENTS': [],
    'PHASE_2_ARCHITECTURE': ['G1'],
    'PHASE_3_MODULE_DESIGN': ['G2'],
    'PHASE_4_IMPLEMENTATION': ['G3'],
    'PHASE_5_EVOLUTION': [],
}


def read_state():
    sj = STRUCT / 'state.json'
    if not sj.exists():
        return {'phase': 'PHASE_0_EMPTY'}
    return json.loads(sj.read_text(encoding='utf-8'))


def check_gates(target, bootstrap=False):
    """检查目标阶段的前置门禁"""
    if bootstrap:
        return True, []

    required = REQUIRED_GATES.get(target, [])
    missing = []
    gate_dir = STRUCT / 'human-gates'
    for g in required:
        found = list(gate_dir.glob(f'{g}-*.md')) if gate_dir.exists() else []
        # 检查是否有 APPROVED 的
        approved = False
        for f in found:
            content = f.read_text(encoding='utf-8')
            if 'APPROVED' in content:
                approved = True
                break
        if not approved:
            missing.append(g)
    return len(missing) == 0, missing


def advance(target, bootstrap=False, reason=''):
    state = read_state()
    current = state.get('phase', 'PHASE_0_EMPTY')

    if current == target:
        print(f'已经在 {target}，无需跃迁。')
        return

    # 检查顺序
    if not bootstrap:
        ci = PHASES.index(current) if current in PHASES else -1
        ti = PHASES.index(target) if target in PHASES else -1
        if ti < 0:
            print(f'未知阶段: {target}')
            sys.exit(1)
        if ti <= ci:
            print(f'阶段只能前进（当前 {current}，目标 {target}）。')
            print(f'回退需要写 ADR + 门禁记录。')
            sys.exit(1)

    # 检查门禁
    ok, missing = check_gates(target, bootstrap)
    if not ok:
        print(f'门禁未通过，缺少: {", ".join(missing)}')
        print(f'请先运行: python .structure/scripts/record_gate.py --approve {missing[0]}')
        sys.exit(1)

    # 写阶段记录
    now = datetime.datetime.now().isoformat()
    today = datetime.date.today()

    ci_short = current.split('_')[0] + current.split('_')[1] if '_' in current else 'P0'
    ti_short = target.split('_')[0] + target.split('_')[1] if '_' in target else 'P?'
    fname = f'{ci_short}-to-{ti_short}-{today}.yaml'
    phase_file = STRUCT / 'phases' / fname
    phase_file.parent.mkdir(parents=True, exist_ok=True)

    record = (
        f'from: {current}\n'
        f'to: {target}\n'
        f'timestamp: "{now}"\n'
        f'triggered_by: {"bootstrap" if bootstrap else "human"}\n'
        f'gate: {state.get("last_gate", "none")}\n'
        f'reason: "{reason or "阶段跃迁"}"\n'
    )
    if bootstrap:
        skipped = PHASES[PHASES.index(current)+1:PHASES.index(target)]
        if skipped:
            record += 'skipped_phases:\n'
            for s in skipped:
                record += f'  - {s}\n'
        record += 'bootstrap: true\n'

    phase_file.write_text(record, encoding='utf-8')

    # 更新 state.json
    state['phase'] = target
    state['phase_entered_at'] = now
    if bootstrap:
        state['bootstrap'] = True
    (STRUCT / 'state.json').write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f'阶段跃迁: {current} → {target}')
    print(f'记录: {phase_file}')

    # 尝试 git add
    try:
        subprocess.run(['git', 'add', str(phase_file), str(STRUCT / 'state.json')],
                       capture_output=True, check=False)
    except FileNotFoundError:
        pass


def main():
    p = argparse.ArgumentParser(description='阶段跃迁')
    p.add_argument('--to', required=True, help='目标阶段')
    p.add_argument('--bootstrap', action='store_true', help='跳过门禁检查（已有项目引导）')
    p.add_argument('--reason', default='', help='跃迁理由')
    args = p.parse_args()
    advance(args.to, args.bootstrap, args.reason)


if __name__ == '__main__':
    main()
