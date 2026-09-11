#!/usr/bin/env python3
"""从 manifest.yaml 生成子模块 .structure/ 骨架

用法：
    python .structure/scripts/scaffold_modules.py
    python .structure/scripts/scaffold_modules.py --module backend

前置条件：PHASE_3 完成（G3 已批准），或 bootstrap 模式。
"""

import json, pathlib, re, sys

ROOT = pathlib.Path('.').resolve()
STRUCT = ROOT / '.structure'


def parse_manifest():
    """简易 YAML 解析（不依赖 pyyaml）"""
    mf = STRUCT / 'manifest.yaml'
    if not mf.exists():
        print('manifest.yaml 不存在。先运行全景分析或手动创建。')
        sys.exit(1)
    text = mf.read_text(encoding='utf-8')
    modules = {}
    current = None
    current_field = None
    current_list = None
    for line in text.split('\n'):
        # 顶级模块名
        m = re.match(r'^  (\w+):\s*$', line)
        if m and 'modules:' in text[:text.index(line)]:
            current = m.group(1)
            modules[current] = {}
            current_field = None
            current_list = None
            continue
        if current is None:
            continue
        # 字段
        m = re.match(r'^    (\w+):\s*(.+)?$', line)
        if m:
            key, val = m.group(1), (m.group(2) or '').strip()
            if val == '[]':
                modules[current][key] = []
                current_field = None
                current_list = None
            elif val and not val.startswith('#'):
                modules[current][key] = val.strip('"').strip("'")
                current_field = None
                current_list = None
            else:
                current_field = key
                current_list = []
                modules[current][key] = current_list
            continue
        # 列表项
        m = re.match(r'^      - (.+)$', line)
        if m and current_list is not None:
            current_list.append(m.group(1).strip('"').strip("'"))
    return modules


def scaffold_one(name, mod_info):
    """为一个模块生成 .structure/ 骨架"""
    mod_path = mod_info.get('path', f'{name}/')
    if mod_path == '.':
        return  # root 模块不建子 .structure/

    target_dir = ROOT / mod_path.rstrip('/') / '.structure'
    status_file = target_dir / 'STATUS.md'

    if status_file.exists():
        print(f'  跳过 {name}：STATUS.md 已存在')
        return

    target_dir.mkdir(parents=True, exist_ok=True)

    resp = mod_info.get('responsibility', 'TODO')
    role = mod_info.get('agent_role', f'{name}-engineer')
    deps = mod_info.get('depends_on', [])
    if isinstance(deps, str):
        deps = [deps]
    forbidden = mod_info.get('forbidden', [])
    if isinstance(forbidden, str):
        forbidden = [forbidden]
    write_scope = mod_info.get('write_scope', [f'{mod_path}'])
    if isinstance(write_scope, str):
        write_scope = [write_scope]

    deps_str = ', '.join(deps) if deps else '无'
    forbidden_str = '\n'.join(f'- {f}' for f in forbidden) if forbidden else '- TODO'
    scope_str = '\n'.join(f'- `{s}`' for s in write_scope)

    content = f"""# {name} 状态

> 最后更新：{__import__('datetime').date.today()}
> 智能体角色：{role}

## 是什么

{resp}

## 边界

**做什么**：
- TODO: 补充具体职责

**不做什么**：
{forbidden_str}

**可写范围**：
{scope_str}

## 当前真相

- [ ] TODO: 填入可执行的验证命令

## 不要假设

- ✗ TODO: 填入已知的错误假设

## 内部结构

| 文件 | 行 | 职责 |
|---|--:|---|
| TODO | - | TODO |

## 依赖

- **上游**：{deps_str}
- **下游**：TODO

## 生命周期

| 日期 | 事件 |
|---|---|
| {__import__('datetime').date.today()} | scaffold 生成骨架 |
"""
    status_file.write_text(content, encoding='utf-8')
    print(f'  ✓ {name}: {status_file}')


def main():
    target_module = None
    if '--module' in sys.argv:
        idx = sys.argv.index('--module')
        if idx + 1 < len(sys.argv):
            target_module = sys.argv[idx + 1]

    # 检查阶段
    sj = STRUCT / 'state.json'
    if sj.exists():
        state = json.loads(sj.read_text(encoding='utf-8'))
        phase = state.get('phase', '')
        bootstrap = state.get('bootstrap', False)
        if not bootstrap and phase in ('PHASE_1_REQUIREMENTS', 'PHASE_2_ARCHITECTURE'):
            print(f'当前阶段 {phase}，不允许创建子模块 .structure/。')
            print('完成 PHASE_3 并获得 G3 批准后再运行。')
            sys.exit(1)

    modules = parse_manifest()
    print(f'manifest.yaml 中有 {len(modules)} 个模块')

    if target_module:
        if target_module not in modules:
            print(f'模块 {target_module} 不在 manifest.yaml 中')
            sys.exit(1)
        scaffold_one(target_module, modules[target_module])
    else:
        for name, info in modules.items():
            scaffold_one(name, info)

    print()
    print('下一步：编辑每个模块的 STATUS.md，补充 TODO 项。')


if __name__ == '__main__':
    main()
