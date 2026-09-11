#!/usr/bin/env python3
"""Git pre-commit hook：校验 .structure/ 完整性

安装方式：
    python .structure/scripts/pre_commit_hook.py --install

也可以手动复制到 .git/hooks/pre-commit：
    cp .structure/scripts/pre_commit_hook.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
"""

import json, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
STRUCT = ROOT / '.structure'


def get_staged_files():
    """获取暂存区的文件列表"""
    r = subprocess.run(['git', 'diff', '--cached', '--name-only'],
                       capture_output=True, text=True, check=False, cwd=ROOT)
    if r.returncode != 0:
        return []
    return [f.strip() for f in r.stdout.strip().split('\n') if f.strip()]


def check_structure_update(staged):
    """如果有代码变更，检查是否同时更新了 .structure/"""
    code_files = [f for f in staged if not f.startswith('.structure/')
                  and not f.startswith('.git')
                  and not f.endswith('.md')  # README 等不算
                  and any(f.endswith(ext) for ext in
                          ['.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs',
                           '.java', '.css', '.html'])]

    structure_files = [f for f in staged if f.startswith('.structure/')]

    if code_files and not structure_files:
        print('⚠ 代码变更但没有更新 .structure/')
        print(f'  代码: {", ".join(code_files[:5])}{"..." if len(code_files) > 5 else ""}')
        print(f'  提示: 更新 changelog、tree.md、STATUS.md')
        print(f'  跳过: git commit --no-verify（不推荐）')
        return False
    return True


def check_state_valid():
    """检查 state.json 合法性"""
    sj = STRUCT / 'state.json'
    if not sj.exists():
        print('⚠ .structure/state.json 缺失')
        return False
    try:
        state = json.loads(sj.read_text(encoding='utf-8'))
        phase = state.get('phase', '')
        valid = ['PHASE_0_EMPTY', 'PHASE_1_REQUIREMENTS', 'PHASE_2_ARCHITECTURE',
                 'PHASE_3_MODULE_DESIGN', 'PHASE_4_IMPLEMENTATION', 'PHASE_5_EVOLUTION']
        if phase not in valid:
            print(f'✗ state.json.phase 无效: {phase}')
            return False
    except json.JSONDecodeError as e:
        print(f'✗ state.json JSON 格式错误: {e}')
        return False
    return True


def check_phase_guard(staged):
    """检查阶段护栏：非实现阶段不应有新增代码"""
    sj = STRUCT / 'state.json'
    if not sj.exists():
        return True
    state = json.loads(sj.read_text(encoding='utf-8'))
    phase = state.get('phase', '')

    if phase in ('PHASE_1_REQUIREMENTS', 'PHASE_2_ARCHITECTURE', 'PHASE_3_MODULE_DESIGN'):
        new_code = [f for f in staged if not f.startswith('.structure/')
                    and any(f.endswith(ext) for ext in ['.py', '.js', '.ts', '.go', '.rs', '.java'])]
        if new_code:
            print(f'⚠ 阶段 {phase} 中有代码文件变更:')
            for f in new_code:
                print(f'  {f}')
            print(f'  在这个阶段应该只修改 .structure/ 下的文件')
            return False
    return True


def check_lock_consistency(staged):
    """检查是否修改了未持锁的模块"""
    mf = STRUCT / 'manifest.yaml'
    if not mf.exists():
        return True

    text = mf.read_text(encoding='utf-8')
    modules = {}
    for m in re.finditer(r'  (\w+):\s*\n\s+path:\s*(.+)', text):
        name = m.group(1)
        path = m.group(2).strip().strip('"').strip("'").rstrip('/')
        if path != '.':
            modules[name] = path

    for mod_name, mod_path in modules.items():
        # 检查是否有该模块的文件在暂存区
        mod_staged = [f for f in staged if f.startswith(mod_path + '/')
                      and not f.startswith(mod_path + '/.structure/')]
        if not mod_staged:
            continue

        # 检查锁
        status = ROOT / mod_path / '.structure' / 'STATUS.md'
        if not status.exists():
            continue
        content = status.read_text(encoding='utf-8')
        if '## LOCK' not in content:
            print(f'⚠ 修改了模块 {mod_name} 但未持有锁')
            print(f'  获取锁: python .structure/scripts/acquire_lock.py --module {mod_name} --session $SESSION --task "..."')
            # 不阻塞，只警告
    return True


def install_hook():
    """安装 pre-commit hook"""
    hooks_dir = ROOT / '.git' / 'hooks'
    if not hooks_dir.exists():
        print('.git/hooks/ 不存在，请先 git init')
        sys.exit(1)

    hook_file = hooks_dir / 'pre-commit'
    script = (
        '#!/usr/bin/env python\n'
        'import subprocess, sys\n'
        'r = subprocess.run([sys.executable, ".structure/scripts/pre_commit_hook.py"],\n'
        '                   cwd=subprocess.run(["git", "rev-parse", "--show-toplevel"],\n'
        '                                      capture_output=True, text=True).stdout.strip())\n'
        'sys.exit(r.returncode)\n'
    )
    hook_file.write_text(script, encoding='utf-8')
    # Windows 不需要 chmod，但不会报错
    try:
        os.chmod(hook_file, 0o755)
    except OSError:
        pass
    print(f'✓ pre-commit hook 已安装到 {hook_file}')


def main():
    if '--install' in sys.argv:
        install_hook()
        return

    staged = get_staged_files()
    if not staged:
        sys.exit(0)

    ok = True
    ok = check_state_valid() and ok
    ok = check_structure_update(staged) and ok
    ok = check_phase_guard(staged) and ok
    check_lock_consistency(staged)  # 只警告

    if not ok:
        print()
        print('提交被阻止。修复上述问题后重试。')
        print('紧急跳过: git commit --no-verify')
        sys.exit(1)

    print('✓ .structure/ 校验通过')


if __name__ == '__main__':
    main()
