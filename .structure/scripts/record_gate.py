#!/usr/bin/env python3
"""记录人工介入门禁

用法：
    python .structure/scripts/record_gate.py --gate G2 --decision APPROVED --human alice@co.com --rationale "架构可行"
    python .structure/scripts/record_gate.py --approve G0   # 快捷方式：审批 G0
    python .structure/scripts/record_gate.py --reject G6 --rationale "不同意方案"
"""

import argparse, datetime, json, pathlib, subprocess, sys

ROOT = pathlib.Path('.').resolve()
STRUCT = ROOT / '.structure'


def update_state(gate, decision):
    sj = STRUCT / 'state.json'
    state = json.loads(sj.read_text(encoding='utf-8'))
    state['last_gate'] = gate
    state['last_gate_decision'] = decision
    sj.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')


def append_index(gate, human, decision):
    idx = STRUCT / 'human-gates' / 'INDEX.md'
    if not idx.exists():
        idx.parent.mkdir(parents=True, exist_ok=True)
        idx.write_text(
            '# 人工介入日志索引\n\n'
            '| Gate | 日期 | 人类 | 决策 | 范围 |\n'
            '|---|---|---|---|---|\n',
            encoding='utf-8')
    today = datetime.date.today()
    with open(idx, 'a', encoding='utf-8') as f:
        f.write(f'| {gate} | {today} | {human} | {decision} | - |\n')


def write_gate(gate, decision, human, rationale, conditions=None, scope=None):
    now = datetime.datetime.now().isoformat()
    today = datetime.date.today()
    fname = f'{gate}-{today}.md'
    fpath = STRUCT / 'human-gates' / fname

    cond_text = conditions if conditions else '- none -'

    content = f"""# Gate {gate}

- **Gate**: {gate}
- **Timestamp**: {now}
- **Human**: {human}
- **Decision**: {decision}
- **Scope**: {scope or '-'}

## Rationale
{rationale}

## Conditions (if any)
{cond_text}

## Resulting State Change
- state.json.last_gate: {gate}
- state.json.last_gate_decision: {decision}
"""
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content, encoding='utf-8')

    update_state(gate, decision)
    append_index(gate, human, decision)

    print(f'门禁已记录: {fpath}')
    print(f'  决策: {decision}')
    print(f'  人类: {human}')

    # 尝试 git add
    try:
        subprocess.run(['git', 'add', str(fpath),
                        str(STRUCT / 'human-gates' / 'INDEX.md'),
                        str(STRUCT / 'state.json')],
                       capture_output=True, check=False)
    except FileNotFoundError:
        pass


def main():
    p = argparse.ArgumentParser(description='记录人工介入门禁')
    p.add_argument('--gate', help='门禁 ID（如 G2）')
    p.add_argument('--decision', choices=['APPROVED', 'REJECTED', 'CONDITIONAL', 'OVERRIDDEN'])
    p.add_argument('--human', help='人类标识（邮箱或 @id）')
    p.add_argument('--rationale', default='', help='理由')
    p.add_argument('--conditions', default=None, help='条件（CONDITIONAL 时）')
    p.add_argument('--scope', default=None, help='范围')
    # 快捷方式
    p.add_argument('--approve', metavar='GATE', help='快捷审批')
    p.add_argument('--reject', metavar='GATE', help='快捷否决')
    args = p.parse_args()

    if args.approve:
        gate = args.approve
        decision = 'APPROVED'
    elif args.reject:
        gate = args.reject
        decision = 'REJECTED'
    elif args.gate and args.decision:
        gate = args.gate
        decision = args.decision
    else:
        p.error('需要 --gate + --decision，或者 --approve/--reject')
        return

    human = args.human
    if not human:
        # 尝试从 git 获取
        try:
            r = subprocess.run(['git', 'config', 'user.email'],
                               capture_output=True, text=True, check=False)
            human = r.stdout.strip() or 'unknown'
        except FileNotFoundError:
            human = 'unknown'

    write_gate(gate, decision, human, args.rationale or '（未填写理由）',
               args.conditions, args.scope)


if __name__ == '__main__':
    main()
