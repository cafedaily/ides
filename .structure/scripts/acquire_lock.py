#!/usr/bin/env python3
"""获取/释放模块锁

用法：
    python .structure/scripts/acquire_lock.py --module backend --session abc12345 --task "加流式支持"
    python .structure/scripts/acquire_lock.py --release backend
    python .structure/scripts/acquire_lock.py --status          # 查看所有锁状态
    python .structure/scripts/acquire_lock.py --cleanup         # 清理遗弃锁（>4h）
"""

import argparse, datetime, json, pathlib, re, sys

ROOT = pathlib.Path('.').resolve()
STRUCT = ROOT / '.structure'
LOCK_TIMEOUT_HOURS = 4


def find_status(module):
    """找到模块的 STATUS.md"""
    mf = STRUCT / 'manifest.yaml'
    if not mf.exists():
        return None
    text = mf.read_text(encoding='utf-8')
    m = re.search(rf'{module}:\s*\n\s+path:\s*(.+)', text)
    if not m:
        return None
    mod_path = m.group(1).strip().strip('"').strip("'").rstrip('/')
    if mod_path == '.':
        return None
    return ROOT / mod_path / '.structure' / 'STATUS.md'


def parse_lock(status_path):
    """从 STATUS.md 解析 LOCK 章节"""
    if not status_path or not status_path.exists():
        return None
    content = status_path.read_text(encoding='utf-8')
    lock_match = re.search(
        r'## LOCK\s*\n'
        r'.*?\*\*holder\*\*:\s*(.+)\n'
        r'.*?\*\*since\*\*:\s*(.+)\n'
        r'.*?\*\*task\*\*:\s*(.+)',
        content, re.IGNORECASE)
    if not lock_match:
        return None
    return {
        'holder': lock_match.group(1).strip(),
        'since': lock_match.group(2).strip(),
        'task': lock_match.group(3).strip(),
    }


def acquire(module, session, task):
    status = find_status(module)
    if not status:
        print(f'找不到模块 {module} 的 STATUS.md')
        sys.exit(1)

    lock = parse_lock(status)
    now = datetime.datetime.now()

    if lock:
        if lock['holder'] == session:
            print(f'续锁：你已持有 {module} 的锁')
        else:
            # 检查是否超时
            try:
                since = datetime.datetime.fromisoformat(lock['since'])
                age = now - since
                if age > datetime.timedelta(hours=LOCK_TIMEOUT_HOURS):
                    print(f'遗弃锁：{lock["holder"]} 已超过 {LOCK_TIMEOUT_HOURS} 小时，接管')
                else:
                    print(f'模块 {module} 被 {lock["holder"]} 锁定（{lock["since"]}）')
                    print(f'任务：{lock["task"]}')
                    print(f'等待或手动释放。')
                    sys.exit(1)
            except ValueError:
                print(f'锁的 since 格式无效，视为遗弃锁')

    # 写入锁
    content = status.read_text(encoding='utf-8')
    lock_section = (
        f'\n## LOCK\n\n'
        f'- **holder**: {session}\n'
        f'- **since**: {now.isoformat()}\n'
        f'- **task**: {task}\n'
    )

    # 如果已有 LOCK 章节，替换
    if '## LOCK' in content:
        content = re.sub(
            r'\n## LOCK\n.*?(?=\n## |\Z)',
            lock_section,
            content, flags=re.DOTALL)
    else:
        content += lock_section

    status.write_text(content, encoding='utf-8')
    print(f'✓ 已锁定 {module}（session: {session}）')


def release(module):
    status = find_status(module)
    if not status:
        print(f'找不到模块 {module} 的 STATUS.md')
        sys.exit(1)

    content = status.read_text(encoding='utf-8')
    if '## LOCK' not in content:
        print(f'{module} 没有锁')
        return

    content = re.sub(r'\n## LOCK\n.*?(?=\n## |\Z)', '', content, flags=re.DOTALL)
    status.write_text(content, encoding='utf-8')
    print(f'✓ 已释放 {module} 的锁')


def show_status():
    mf = STRUCT / 'manifest.yaml'
    if not mf.exists():
        print('manifest.yaml 不存在')
        return
    text = mf.read_text(encoding='utf-8')
    modules = re.findall(r'^  (\w+):', text, re.MULTILINE)
    print(f'模块锁状态：')
    for mod in modules:
        status = find_status(mod)
        lock = parse_lock(status)
        if lock:
            print(f'  🔒 {mod}: {lock["holder"]} (since {lock["since"]}) — {lock["task"]}')
        else:
            print(f'  🔓 {mod}: 空闲')


def cleanup():
    mf = STRUCT / 'manifest.yaml'
    if not mf.exists():
        return
    text = mf.read_text(encoding='utf-8')
    modules = re.findall(r'^  (\w+):', text, re.MULTILINE)
    now = datetime.datetime.now()
    for mod in modules:
        status = find_status(mod)
        lock = parse_lock(status)
        if lock:
            try:
                since = datetime.datetime.fromisoformat(lock['since'])
                age = now - since
                if age > datetime.timedelta(hours=LOCK_TIMEOUT_HOURS):
                    print(f'清理遗弃锁: {mod} ({lock["holder"]}, {age})')
                    release(mod)
            except ValueError:
                print(f'清理无效锁: {mod}')
                release(mod)


def main():
    p = argparse.ArgumentParser(description='模块锁管理')
    p.add_argument('--module', help='目标模块')
    p.add_argument('--session', help='会话 ID')
    p.add_argument('--task', help='任务描述')
    p.add_argument('--release', metavar='MODULE', help='释放模块锁')
    p.add_argument('--status', action='store_true', help='查看所有锁')
    p.add_argument('--cleanup', action='store_true', help='清理遗弃锁')
    args = p.parse_args()

    if args.status:
        show_status()
    elif args.cleanup:
        cleanup()
    elif args.release:
        release(args.release)
    elif args.module and args.session and args.task:
        acquire(args.module, args.session, args.task)
    else:
        p.print_help()


if __name__ == '__main__':
    main()
