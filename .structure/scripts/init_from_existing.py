#!/usr/bin/env python3
"""已有项目全景分析 → 生成 .structure/ v1.1 harness

用法：
    python .structure/scripts/init_from_existing.py [项目根目录]

做什么：
    1. 扫描目录树，识别源文件
    2. 按目录分组为候选模块
    3. 分析文件间依赖（import/require）
    4. 统计每个模块的行数、文件数
    5. 识别耦合关系
    6. 生成：
       - .structure/state.json
       - .structure/manifest.yaml（草稿）
       - .structure/tree.md（草稿）
       - .structure/overview.md（草稿）
       - .structure/files.md（草稿）
       - .structure/human-gates/G0-bootstrap-*.md
       - .structure/phases/P0-to-P*-*.yaml
       - 每个模块的 .structure/STATUS.md（草稿）
    7. 输出分析报告

不做什么：
    - 不修改任何源代码
    - 不执行代码
    - 不访问网络
    - 不决定最终架构——生成的都是草稿，需要人类审批
"""

import os, sys, json, re, datetime, pathlib, collections

IGNORE_DIRS = {
    '.git', '.structure', 'node_modules', '__pycache__', '.venv', 'venv',
    'env', '.env', 'dist', 'build', '.next', '.nuxt', 'target',
    '.idea', '.vscode', '.vs', 'coverage', '.pytest_cache', '.mypy_cache',
}
IGNORE_FILES = {'.DS_Store', 'Thumbs.db', '.gitignore', '.gitattributes'}

EXT_LANG = {
    '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
    '.jsx': 'JavaScript', '.tsx': 'TypeScript',
    '.go': 'Go', '.rs': 'Rust', '.java': 'Java', '.kt': 'Kotlin',
    '.rb': 'Ruby', '.php': 'PHP', '.c': 'C', '.cpp': 'C++', '.h': 'C/C++',
    '.cs': 'C#', '.swift': 'Swift', '.lua': 'Lua', '.sh': 'Shell',
    '.sql': 'SQL', '.html': 'HTML', '.css': 'CSS', '.scss': 'SCSS',
    '.yaml': 'YAML', '.yml': 'YAML', '.json': 'JSON', '.toml': 'TOML',
    '.md': 'Markdown', '.txt': 'Text', '.xml': 'XML',
}

SOURCE_EXTS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java',
               '.kt', '.rb', '.php', '.c', '.cpp', '.h', '.cs', '.swift',
               '.lua', '.sh', '.sql'}
ASSET_EXTS = {'.html', '.css', '.scss', '.yaml', '.yml', '.json', '.toml',
              '.md', '.txt', '.xml'}


def scan_files(root):
    """扫描目录树，返回 (相对路径, 绝对路径, 扩展名) 列表"""
    root = pathlib.Path(root).resolve()
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for f in filenames:
            if f in IGNORE_FILES:
                continue
            p = pathlib.Path(dirpath) / f
            rel = p.relative_to(root)
            ext = p.suffix.lower()
            if ext in SOURCE_EXTS or ext in ASSET_EXTS:
                files.append((str(rel).replace('\\', '/'), str(p), ext))
    return files


def count_lines(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def extract_imports_python(filepath):
    """提取 Python 文件的 import 目标"""
    imports = set()
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                m = re.match(r'^from\s+([\w.]+)\s+import', line)
                if m:
                    imports.add(m.group(1).split('.')[0])
                m = re.match(r'^import\s+([\w.]+)', line)
                if m:
                    imports.add(m.group(1).split('.')[0])
    except Exception:
        pass
    return imports


def extract_imports_js(filepath):
    """提取 JS/TS 文件的 import/require 目标"""
    imports = set()
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        for m in re.finditer(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]", content):
            imports.add(m.group(1))
        for m in re.finditer(r"from\s+['\"]([^'\"]+)['\"]", content):
            imports.add(m.group(1))
    except Exception:
        pass
    return imports


def identify_modules(files, root):
    """按顶层目录分组为候选模块"""
    modules = collections.defaultdict(list)
    root_files = []
    for rel, abspath, ext in files:
        parts = rel.split('/')
        if len(parts) == 1:
            root_files.append((rel, abspath, ext))
        else:
            top = parts[0]
            modules[top].append((rel, abspath, ext))
    if root_files:
        modules['_root'] = root_files
    return dict(modules)


def analyze_module(name, files, all_module_names):
    """分析一个模块：行数、语言、依赖"""
    total_lines = 0
    lang_counts = collections.Counter()
    source_files = []
    asset_files = []
    internal_deps = set()

    for rel, abspath, ext in files:
        lines = count_lines(abspath)
        total_lines += lines
        lang = EXT_LANG.get(ext, 'Other')
        lang_counts[lang] += lines

        entry = {'path': rel, 'lines': lines, 'lang': lang}

        if ext in SOURCE_EXTS:
            source_files.append(entry)
            if ext == '.py':
                for imp in extract_imports_python(abspath):
                    if imp in all_module_names:
                        internal_deps.add(imp)
            elif ext in ('.js', '.ts', '.jsx', '.tsx'):
                for imp in extract_imports_js(abspath):
                    for mod in all_module_names:
                        if mod in imp:
                            internal_deps.add(mod)
        else:
            asset_files.append(entry)

    internal_deps.discard(name)

    return {
        'name': name,
        'total_lines': total_lines,
        'file_count': len(files),
        'source_count': len(source_files),
        'asset_count': len(asset_files),
        'languages': dict(lang_counts.most_common()),
        'source_files': sorted(source_files, key=lambda x: x['path']),
        'asset_files': sorted(asset_files, key=lambda x: x['path']),
        'depends_on': sorted(internal_deps),
    }


def generate_state_json(project_name, phase='PHASE_2_ARCHITECTURE'):
    """生成 state.json"""
    return {
        'project': project_name,
        'phase': phase,
        'phase_entered_at': datetime.datetime.now().isoformat(),
        'last_gate': 'G0-panoramic-analysis',
        'last_gate_decision': 'PENDING',
        'phase_owner': 'hybrid',
        'version': '1.1',
        'bootstrap': True,
        'bootstrap_reason': 'existing project panoramic analysis',
    }


def generate_manifest(project_name, analyses):
    """生成 manifest.yaml 草稿（纯文本，不依赖 pyyaml）"""
    lines = [
        f'version: "1.1"',
        f'project: {project_name}',
        f'description: "TODO: 一句话描述"',
        '',
        'modules:',
    ]
    for a in analyses:
        name = a['name']
        if name == '_root':
            name = 'root'
        lines.append(f'  {name}:')
        lines.append(f'    path: {a["name"]}/')
        lines.append(f'    responsibility: "TODO: 职责描述"')
        lines.append(f'    agent_role: {name}-engineer')
        lines.append(f'    write_scope:')
        lines.append(f'      - "{a["name"]}/"')
        lines.append(f'    depends_on:')
        if a['depends_on']:
            for dep in a['depends_on']:
                lines.append(f'      - {dep}')
        else:
            lines.append(f'      []')
        lines.append(f'    public_api: []  # TODO')
        lines.append(f'    forbidden: []  # TODO')
        langs = ', '.join(f'{k}({v})' for k, v in a['languages'].items())
        lines.append(f'    status: "🆕"')
        lines.append(f'    # {a["file_count"]} files, {a["total_lines"]} lines, {langs}')
        lines.append('')
    return '\n'.join(lines)


def generate_tree_md(analyses):
    """生成 tree.md 草稿"""
    lines = [
        '# 模块树（全景分析草稿）',
        '',
        f'> 自动生成于 {datetime.date.today()}，需要人工审阅。',
        '',
    ]
    for a in analyses:
        name = a['name']
        if name == '_root':
            name = '根目录'
        lines.append(f'## {name} (`{a["name"]}/`)')
        lines.append('')
        lines.append(f'- **文件数**: {a["file_count"]}（源码 {a["source_count"]}，资产 {a["asset_count"]}）')
        lines.append(f'- **总行数**: {a["total_lines"]}')
        langs = ', '.join(f'{k} {v}行' for k, v in a['languages'].items())
        lines.append(f'- **语言**: {langs}')
        if a['depends_on']:
            lines.append(f'- **依赖**: {", ".join(a["depends_on"])}')
        lines.append(f'- **状态**: 🆕 待确认')
        lines.append('')
        if a['source_files']:
            lines.append('| 文件 | 行 | 语言 |')
            lines.append('|---|--:|---|')
            for f in a['source_files']:
                lines.append(f'| `{f["path"]}` | {f["lines"]} | {f["lang"]} |')
            lines.append('')
    return '\n'.join(lines)


def generate_overview(project_name, analyses):
    """生成 overview.md 草稿"""
    total_files = sum(a['file_count'] for a in analyses)
    total_lines = sum(a['total_lines'] for a in analyses)
    all_langs = collections.Counter()
    for a in analyses:
        all_langs.update(a['languages'])

    lines = [
        f'# {project_name} 项目概况（全景分析草稿）',
        '',
        f'> 自动生成于 {datetime.date.today()}',
        '',
        '## 数字',
        '',
        f'- **模块数**: {len(analyses)}',
        f'- **源文件数**: {total_files}',
        f'- **总行数**: {total_lines}',
        '',
        '## 语言分布',
        '',
        '| 语言 | 行数 | 占比 |',
        '|---|--:|--:|',
    ]
    for lang, count in all_langs.most_common():
        pct = count / total_lines * 100 if total_lines else 0
        lines.append(f'| {lang} | {count} | {pct:.1f}% |')
    lines.append('')
    lines.append('## 模块概览')
    lines.append('')
    lines.append('| 模块 | 文件 | 行数 | 主要语言 | 依赖 |')
    lines.append('|---|--:|--:|---|---|')
    for a in analyses:
        main_lang = list(a['languages'].keys())[0] if a['languages'] else '-'
        deps = ', '.join(a['depends_on']) if a['depends_on'] else '-'
        lines.append(f'| {a["name"]} | {a["file_count"]} | {a["total_lines"]} | {main_lang} | {deps} |')
    lines.append('')
    return '\n'.join(lines)


def generate_files_md(analyses):
    """生成 files.md"""
    lines = [
        '# 文件清单（全景分析草稿）',
        '',
        f'> 自动生成于 {datetime.date.today()}',
        '',
    ]
    for a in analyses:
        lines.append(f'## {a["name"]}/')
        lines.append('')
        lines.append('| 文件 | 行 | 语言 |')
        lines.append('|---|--:|---|')
        for f in a['source_files'] + a['asset_files']:
            lines.append(f'| `{f["path"]}` | {f["lines"]} | {f["lang"]} |')
        lines.append('')
    return '\n'.join(lines)


def generate_status_md(analysis):
    """生成子模块 STATUS.md 草稿"""
    name = analysis['name']
    langs = ', '.join(analysis['languages'].keys())
    lines = [
        f'# {name} 状态（全景分析草稿）',
        '',
        f'> 自动生成于 {datetime.date.today()}，需要人工审阅和补充。',
        '',
        '## 是什么',
        '',
        f'TODO: 一两句话描述这个模块做什么。',
        f'（{analysis["file_count"]} 个文件，{analysis["total_lines"]} 行，{langs}）',
        '',
        '## 边界',
        '',
        '**做什么**：',
        '- TODO',
        '',
        '**不做什么**：',
        '- TODO',
        '',
        '## 当前真相',
        '',
        '> 填入可执行的验证命令。',
        '',
        '- [ ] TODO: `command` → expected output',
        '',
        '## 不要假设',
        '',
        '> 填入过去犯过的错误假设。',
        '',
        '- ✗ TODO: 错误假设 → 实际情况',
        '',
        '## 内部结构',
        '',
        '| 文件 | 行 | 职责 |',
        '|---|--:|---|',
    ]
    for f in analysis['source_files']:
        lines.append(f'| `{f["path"]}` | {f["lines"]} | TODO |')
    lines.append('')
    lines.append('## 依赖')
    lines.append('')
    if analysis['depends_on']:
        lines.append(f'- **上游**：{", ".join(analysis["depends_on"])}')
    else:
        lines.append('- **上游**：无')
    lines.append('- **下游**：TODO')
    lines.append('')
    lines.append('## 生命周期')
    lines.append('')
    lines.append('| 日期 | 事件 |')
    lines.append('|---|---|')
    lines.append(f'| {datetime.date.today()} | 全景分析首次识别 |')
    lines.append('')
    return '\n'.join(lines)


def generate_gate_record():
    """生成 G0 全景分析门禁草稿"""
    now = datetime.datetime.now().isoformat()
    return f"""# Gate G0 — Panoramic Analysis (Bootstrap)

- **Gate**: G0-panoramic-analysis
- **Timestamp**: {now}
- **Human**: TODO: @your-id
- **Decision**: PENDING
- **Scope**: 全项目全景分析

## Rationale

对已有项目进行首次全景分析，生成 .structure/ v1.1 harness 草稿。
所有生成的文件都需要人工审阅和确认后才能进入下一阶段。

## 待确认事项

- [ ] 模块划分是否合理（manifest.yaml）
- [ ] 模块边界是否正确（各 STATUS.md）
- [ ] 依赖关系是否完整（tree.md）
- [ ] 决定初始阶段：直接 PHASE_4（成熟项目）还是 PHASE_2（需要重新架构）

## Resulting State Change

- state.json.phase: 待人工决定
- manifest.yaml: 草稿已生成，待审批
"""


def generate_phase_record(target_phase):
    """生成阶段跃迁记录"""
    now = datetime.datetime.now().isoformat()
    return f"""from: PHASE_0_EMPTY
to: {target_phase}
timestamp: "{now}"
triggered_by: panoramic-analysis
gate: G0-panoramic-analysis
reason: "已有项目全景分析引导"
bootstrap: true
"""


def run(root_dir):
    root = pathlib.Path(root_dir).resolve()
    project_name = root.name
    struct_dir = root / '.structure'

    print(f'=== 全景分析：{project_name} ===')
    print(f'根目录：{root}')
    print()

    # 扫描
    print('扫描文件...')
    files = scan_files(root)
    print(f'  找到 {len(files)} 个文件')

    # 分组
    print('识别模块...')
    module_groups = identify_modules(files, root)
    print(f'  识别到 {len(module_groups)} 个候选模块：{", ".join(module_groups.keys())}')

    # 分析
    print('分析依赖...')
    all_module_names = set(module_groups.keys())
    analyses = []
    for name, mod_files in sorted(module_groups.items()):
        a = analyze_module(name, mod_files, all_module_names)
        analyses.append(a)
        deps = ', '.join(a['depends_on']) if a['depends_on'] else '无'
        print(f'  {name}: {a["file_count"]} 文件, {a["total_lines"]} 行, 依赖: {deps}')

    # 检查是否已有 .structure/
    if struct_dir.exists() and (struct_dir / 'state.json').exists():
        print()
        print('⚠️  .structure/ 已存在且有 state.json。')
        print('   如果要覆盖，请先删除 .structure/ 或使用 --force 参数。')
        print('   当前只生成报告，不写入文件。')
        print()
        report_only = True
    else:
        report_only = False

    # 生成
    print()
    print('生成 .structure/ 文件...')

    outputs = {
        '.structure/state.json': json.dumps(
            generate_state_json(project_name), indent=2, ensure_ascii=False),
        '.structure/manifest.yaml': generate_manifest(project_name, analyses),
        '.structure/tree.md': generate_tree_md(analyses),
        '.structure/overview.md': generate_overview(project_name, analyses),
        '.structure/files.md': generate_files_md(analyses),
        '.structure/human-gates/G0-panoramic-analysis.md': generate_gate_record(),
        '.structure/phases/P0-to-P2-bootstrap.yaml': generate_phase_record(
            'PHASE_2_ARCHITECTURE'),
        '.structure/human-gates/INDEX.md': (
            '# 人工介入日志索引\n\n'
            '| Gate | 日期 | 人类 | 决策 | 范围 |\n'
            '|---|---|---|---|---|\n'
            f'| G0-panoramic | {datetime.date.today()} | TODO | PENDING | 全景分析 |\n'
        ),
        '.structure/tasks/BACKLOG.md': (
            '# 任务队列\n\n## 待做\n\n'
            '### T-001: 审阅全景分析结果\n'
            '- **优先级**: P0\n'
            '- **描述**: 审阅 manifest.yaml、tree.md、各模块 STATUS.md，确认模块划分\n'
            '- **验收**: manifest.yaml 中所有 TODO 已填写，G0 门禁 APPROVED\n\n'
            '## 进行中\n\n（无）\n\n## 已完成\n\n（无）\n'
        ),
    }

    # 子模块 STATUS.md
    for a in analyses:
        name = a['name']
        if name == '_root':
            continue
        outputs[f'{name}/.structure/STATUS.md'] = generate_status_md(a)

    # AGENT.md 和 STRUCTURE.md 模板
    outputs['.structure/AGENT.md'] = _agent_md_template()
    outputs['.structure/STRUCTURE.md'] = _structure_md_template()
    outputs['.structure/INDEX.md'] = _index_md_template(analyses)

    if report_only:
        print()
        print('=== 分析报告（未写入文件） ===')
        print()
        for path, content in sorted(outputs.items()):
            lines = content.count('\n') + 1
            print(f'  {path} ({lines} 行)')
        print()
        print(f'共 {len(outputs)} 个文件待生成。')
        print('要写入文件，请删除现有 .structure/ 或使用 --force。')
        return analyses

    # 写入
    for path, content in outputs.items():
        full = root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding='utf-8')
        print(f'  ✓ {path}')

    print()
    print(f'=== 完成 ===')
    print(f'生成了 {len(outputs)} 个文件。')
    print()
    print('下一步：')
    print('  1. 审阅 .structure/manifest.yaml — 模块划分是否合理？')
    print('  2. 审阅每个模块的 .structure/STATUS.md — 补充边界、真相、假设')
    print('  3. 填写 .structure/human-gates/G0-panoramic-analysis.md 的 Human 字段')
    print('  4. 决定初始阶段：')
    print('     - 成熟项目 → PHASE_4（跳过架构设计）')
    print('     - 需要重构 → PHASE_2（先做架构设计）')
    print('  5. 运行 python .structure/scripts/record_gate.py --approve G0')
    print('  6. git add .structure/ && git commit')
    return analyses


def _agent_md_template():
    return """# AGENT.md — 智能体开发契约 v1.1

> 本文件是机器可读操作契约。缺失任何一节 → 拒绝启动。
> 人类手册见 STRUCTURE.md。

## 0. 心智模型

你是在 harness 下运行的**阶段感知**的**模块责任智能体**。
`.structure/` 同时是你的上下文来源、行为约束、状态存储、变更审计。

## 1. 启动序列

1. 读 `state.json` → 确认 phase
2. 按 phase 决定行为（见 §2）
3. 读 `phases/` 最近 1 条
4. 读 `human-gates/` 最近 3 条
5. 读 phase 规定的资源

| phase | 你的角色 | 禁止 |
|---|---|---|
| PHASE_0 | 拒绝启动 | 一切 |
| PHASE_1 | 需求引导者 | 写代码、建模块 |
| PHASE_2 | 架构师 | 创建子模块 .structure/ |
| PHASE_3 | 模块设计师 | 编写业务代码 |
| PHASE_4 | 模块责任工程师 | 修改 phase、跨模块写 |
| PHASE_5 | 模块责任工程师 | 直接改 manifest 新增模块 |

## 2. 模块锁

一个模块只能有一个活跃智能体。锁在 `{module}/.structure/STATUS.md` 的 LOCK 章节。
跨模块修改需原子获取所有锁。锁超过 4 小时未更新视为遗弃。

## 3. 执行完成必须更新

每次代码修改，同一个 commit 里更新：
- changelog/YYYY-MM-DD_{slug}.md
- tree.md 状态标记
- {module}/.structure/STATUS.md
- tasks/BACKLOG.md（如有变更）
- debts.md（如有变更）
- 释放 LOCK

## 4. HITL 门禁

| Gate | 名称 | 触发者 |
|---|---|---|
| G1 | 需求冻结 | 人类 |
| G2 | 架构批准 | 人类 |
| G3 | 模块树批准 | 人类 |
| G4..Gn | 单模块能力确认 | 人类（逐模块）|
| G5 | 任务下发 | 可选 HITL |
| G6 | 跨模块 ADR | 人类 |
| G7 | 合并到 main | 人类 |

门禁记录在 `human-gates/`。未记录 = 未批准。不得基于口头批准推进。

## 5. 防幻觉

三层防线：
1. 当前真相（STATUS.md 可执行断言）
2. 不要假设（STATUS.md 错误假设列表）
3. 耦合红线（coupling / manifest.yaml）

改代码前：读 STATUS.md → 读 coupling → 验证假设 → 开始。

## 6. 渐进式披露

只读需要的：tree.md 是目录，STATUS.md 是正文。不要全读。

## 7. 模块定义

见 manifest.yaml。每个模块定义：
- agent_role（智能体身份）
- write_scope（可写范围）
- forbidden（禁止事项）
- depends_on（依赖）
- public_api（对外接口）

智能体只能修改 write_scope 内的文件。

## 协议版本

v1.1 — 阶段机 + HITL + 人工日志 + 全景分析
"""


def _structure_md_template():
    return """# STRUCTURE.md — 人类开发指导手册 v1.1

> 面向团队工程师。智能体契约见 AGENT.md。

## 设计原则

1. 从空目录起步不丢人 — .structure/ 支持零模块启动
2. 人工介入是常态 — 所有介入必须落盘
3. 阶段即护栏 — 每个阶段有准入/退出条件
4. 门禁即合同 — 未记录 = 未批准
5. 模块后置生成 — 架构不清前不建子模块

## 项目阶段

```
PHASE_0 空目录 → PHASE_1 需求 → PHASE_2 架构 → PHASE_3 模块设计 → PHASE_4 实现 → PHASE_5 演化
```

每个阶段跃迁需要人类门禁（Gate）。

## 对于已有项目

已有项目用全景分析引导：
```
python .structure/scripts/init_from_existing.py
```

成熟项目可以从 PHASE_0 直接跳到 PHASE_4（需 G0 bootstrap gate）。

## 日常工作流

1. 开始：读 state.json → tree.md → BACKLOG.md
2. 改码：获取模块锁 → 写代码 → 跑测试
3. 收尾：写 changelog → 更新 STATUS.md → 释放锁 → commit

## 人工介入日志

所有人类介入（批准、否决、覆盖、修正）记录在 human-gates/。
查看：cat .structure/human-gates/INDEX.md

## 与 git 的关系

.structure/ 入版本控制。和代码同 commit。
门禁记录单独 commit，不与代码混合。

## 详细说明

见各文件的内联注释和 AGENT.md 的完整契约。
"""


def _index_md_template(analyses):
    lines = [
        '# .structure/ — 项目状态索引',
        '',
        '## 入口',
        '',
        '| 文件 | 读者 | 内容 |',
        '|---|---|---|',
        '| [STRUCTURE.md](STRUCTURE.md) | 人 | 开发指导手册 |',
        '| [AGENT.md](AGENT.md) | AI | 智能体契约 |',
        '',
        '## 状态',
        '',
        '| 文件 | 内容 |',
        '|---|---|',
        '| [state.json](state.json) | 当前阶段、门禁 |',
        '| [manifest.yaml](manifest.yaml) | 模块树、耦合 |',
        '| [tree.md](tree.md) | 模块地图 |',
        '| [overview.md](overview.md) | 项目概况 |',
        '| [files.md](files.md) | 文件清单 |',
        '',
        '## 流程',
        '',
        '| 目录 | 内容 |',
        '|---|---|',
        '| [human-gates/](human-gates/) | 人工介入日志 |',
        '| [phases/](phases/) | 阶段跃迁记录 |',
        '| [changelog/](changelog/) | 变更日志 |',
        '| [tasks/](tasks/) | 任务队列 |',
        '',
        '## 子模块',
        '',
        '| 模块 | STATUS.md |',
        '|---|---|',
    ]
    for a in analyses:
        if a['name'] == '_root':
            continue
        lines.append(f'| {a["name"]} | [{a["name"]}/.structure/STATUS.md]'
                      f'(../{a["name"]}/.structure/STATUS.md) |')
    lines.append('')
    return '\n'.join(lines)


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    force = '--force' in sys.argv
    if force:
        struct = pathlib.Path(root).resolve() / '.structure'
        if struct.exists():
            sj = struct / 'state.json'
            if sj.exists():
                sj.unlink()
    run(root)
