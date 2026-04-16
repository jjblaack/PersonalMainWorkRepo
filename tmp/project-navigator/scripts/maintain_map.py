#!/usr/bin/env python3
import argparse
import fnmatch
import os
import re
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_IGNORE = [
    '**/.git/**',
    '**/.svn/**',
    '**/.hg/**',
    '**/.DS_Store',
    '**/node_modules/**',
    '**/__pycache__/**',
    '**/.venv/**',
    '**/venv/**',
    '**/dist/**',
    '**/build/**',
    '**/out/**',
    '**/.trae/**',
    '**/drafts/**',
    '**/archived/**',
]

CATEGORY_ORDER = [
    'Philosophy',
    'Architecture',
    'Conventions',
    'Playbooks',
    'Reference',
    'Misc',
]

def _strip_quotes(val):
    s = val.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1].strip()
    return s

def parse_frontmatter(lines):
    if not lines:
        return ({}, 0)
    if lines[0].strip() != '---':
        return ({}, 0)
    data = {}
    i = 1
    while i < len(lines):
        raw = lines[i].rstrip('\n')
        if raw.strip() == '---':
            i += 1
            break
        m = re.match(r'^\s*([A-Za-z0-9_-]+)\s*:\s*(.*)$', raw)
        if not m:
            i += 1
            continue
        key = m.group(1).strip()
        rest = m.group(2).strip()
        if key == 'tags':
            if rest.startswith('[') and rest.endswith(']'):
                inner = rest[1:-1].strip()
                if inner:
                    parts = [p.strip() for p in inner.split(',')]
                    data['tags'] = [_strip_quotes(p) for p in parts if p]
                else:
                    data['tags'] = []
                i += 1
                continue
            if rest:
                data['tags'] = [_strip_quotes(rest)]
                i += 1
                continue
            tags = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].rstrip('\n')
                if nxt.strip() == '---':
                    break
                if re.match(r'^\s*[A-Za-z0-9_-]+\s*:\s*', nxt):
                    break
                mm = re.match(r'^\s*-\s*(.+?)\s*$', nxt)
                if mm:
                    tags.append(_strip_quotes(mm.group(1)))
                    j += 1
                    continue
                if nxt.strip() == '':
                    j += 1
                    continue
                break
            data['tags'] = tags
            i = j
            continue
        if key == 'description':
            if rest:
                data['description'] = _strip_quotes(rest)
            i += 1
            continue
        if rest:
            data[key] = _strip_quotes(rest)
        i += 1
    return (data, i)

def extract_title_summary_tags(path, summary_max_len, max_head_lines):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = []
            for _ in range(max(1, max_head_lines)):
                line = f.readline()
                if not line:
                    break
                lines.append(line)
    except Exception:
        return (Path(path).stem, '', [])
    fm, content_start = parse_frontmatter(lines)
    description = fm.get('description')
    tags = fm.get('tags') or []
    title = None
    for line in lines[content_start:]:
        s = line.strip()
        if not s:
            continue
        if s.startswith('#'):
            title = s.lstrip('#').strip()
        else:
            title = s
        break
    if not title:
        title = Path(path).stem
    summary = description.strip() if isinstance(description, str) else ''
    if summary and summary_max_len > 0 and len(summary) > summary_max_len:
        summary = summary[: max(0, summary_max_len - 1)].rstrip() + '…'
    return (title, summary, tags)

def is_cjk_text(s):
    if not s:
        return False
    return re.search(r'[\u4e00-\u9fff]', s) is not None

def infer_language(title, summary, tags):
    for t in tags or []:
        if t.lower() in ('zh', 'cn', 'chinese', '中文'):
            return '中文'
        if t.lower() in ('en', 'eng', 'english', '英文'):
            return 'English'
    if is_cjk_text(title) or is_cjk_text(summary):
        return '中文'
    return 'English'

def infer_category(rel_path, title, summary, tags):
    path_lower = rel_path.lower()
    tag_lower = {t.lower() for t in (tags or [])}
    if (
        'philosophy' in path_lower
        or any(t in tag_lower for t in ['philosophy', 'philosophies', '理念', '哲学', 'principles', 'principle', '设计原则'])
        or any(k in (title.lower() + ' ' + summary.lower()) for k in ['philosophy', 'principle'])
        or any(k in (title + summary) for k in ['哲学', '理念', '原则'])
    ):
        return 'Philosophy'
    if (
        'architecture' in path_lower
        or any(t in tag_lower for t in ['architecture', 'arch', '架构', '模块', 'boundary', 'boundaries'])
        or any(k in (title + summary) for k in ['架构', '模块', '边界', '数据流'])
    ):
        return 'Architecture'
    if (
        any(seg in path_lower for seg in ['contrib', 'contributing', 'convention', 'conventions', 'guideline', 'guidelines', 'style', '规范'])
        or any(t in tag_lower for t in ['conventions', 'guidelines', 'style', '规范'])
        or any(k in (title + summary) for k in ['规范', '约定', '风格', '贡献'])
    ):
        return 'Conventions'
    if (
        any(seg in path_lower for seg in ['playbook', 'runbook', 'howto', 'how-to', 'ops', '操作'])
        or any(t in tag_lower for t in ['playbook', 'runbook', 'howto', '操作'])
        or any(k in (title + summary) for k in ['手册', '指南', '排障', '运行'])
    ):
        return 'Playbooks'
    if (
        any(seg in path_lower for seg in ['reference', 'refs', 'api', 'spec', 'specs'])
        or any(t in tag_lower for t in ['reference', 'api', 'spec'])
        or any(k in (title.lower() + ' ' + summary.lower()) for k in ['reference', 'api', 'spec'])
    ):
        return 'Reference'
    return 'Misc'

def is_ignored(rel_path, ignore_patterns):
    normalized = rel_path.replace('\\', '/')
    for pat in ignore_patterns:
        if fnmatch.fnmatch(normalized, pat):
            return True
    return False

def collect_markdown_files(docs_dir, cwd, ignore_patterns):
    result = []
    for root, _, files in os.walk(docs_dir):
        for name in files:
            if name.lower().endswith('.md'):
                full_path = os.path.join(root, name)
                rel = os.path.relpath(full_path, cwd).replace(os.sep, '/')
                if is_ignored(rel, ignore_patterns):
                    continue
                result.append(full_path)
    return result

def build_entries(files, cwd, summary_max_len, max_head_lines, ignore_patterns):
    entries = []
    for p in files:
        rel_path = os.path.relpath(p, cwd).replace(os.sep, '/')
        if is_ignored(rel_path, ignore_patterns):
            continue
        title, summary, tags = extract_title_summary_tags(p, summary_max_len, max_head_lines)
        entries.append({
            'title': title,
            'rel': rel_path[2:] if rel_path.startswith('./') else rel_path,
            'summary': summary,
            'tags': tags,
        })
    title_counts = {}
    for e in entries:
        key = e['title'].strip().lower()
        title_counts[key] = title_counts.get(key, 0) + 1
    for e in entries:
        key = e['title'].strip().lower()
        if title_counts.get(key, 0) > 1:
            e['title'] = f"{e['title']} ({Path(e['rel']).name})"
    for e in entries:
        e['category'] = infer_category(e['rel'], e['title'], e['summary'], e['tags'])
        e['language'] = infer_language(e['title'], e['summary'], e['tags'])
        e['sort_key'] = (e['category'], e['language'], e['rel'].lower(), e['title'].lower())
    entries.sort(key=lambda x: x['sort_key'])
    return entries

def build_update_command(
    script_rel_path,
    docs_dir_arg,
    map_file_arg,
    summary_max_len,
    include_tags,
    lang_sections,
    max_head_lines,
    max_per_category,
    extra_ignores,
):
    parts = ['python3', script_rel_path]
    if docs_dir_arg != './docs':
        parts.extend(['--docs-dir', docs_dir_arg])
    if map_file_arg != './MAP.md':
        parts.extend(['--map-file', map_file_arg])
    if summary_max_len != 80:
        parts.extend(['--summary-max-len', str(summary_max_len)])
    if max_head_lines != 200:
        parts.extend(['--max-head-lines', str(max_head_lines)])
    if max_per_category and max_per_category > 0:
        parts.extend(['--max-per-category', str(max_per_category)])
    if lang_sections:
        parts.append('--lang-sections')
    if not include_tags:
        parts.append('--no-tags')
    for pat in (extra_ignores or [])[:6]:
        parts.extend(['--ignore', pat])
    return ' '.join(parts)

def render_map(
    entries,
    docs_dir_arg,
    map_file_arg,
    script_rel_path,
    ignore_patterns,
    summary_max_len,
    include_tags,
    lang_sections,
    max_per_category,
    max_head_lines,
    extra_ignores,
):
    lines = []
    lines.append('# MAP')
    lines.append('')
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
    lines.append(f'- Generated at: {ts}')
    lines.append(f'- Docs dir: {docs_dir_arg}')
    lines.append(
        '- Update command: '
        + build_update_command(
            script_rel_path,
            docs_dir_arg,
            map_file_arg,
            summary_max_len,
            include_tags,
            lang_sections,
            max_head_lines,
            max_per_category,
            extra_ignores,
        )
    )
    lines.append(f'- Summary: prefer frontmatter description; max {summary_max_len} chars')
    if ignore_patterns:
        shown = ', '.join(ignore_patterns[:12])
        suffix = ' …' if len(ignore_patterns) > 12 else ''
        lines.append(f'- Ignore: {shown}{suffix}')
    lines.append('')
    if not entries:
        lines.append('No documents indexed.')
        lines.append('')
        return '\n'.join(lines)
    grouped = {c: [] for c in CATEGORY_ORDER}
    for e in entries:
        grouped.setdefault(e['category'], []).append(e)
    for category in CATEGORY_ORDER:
        items = grouped.get(category) or []
        if not items:
            continue
        if max_per_category and max_per_category > 0:
            items = items[:max_per_category]
        lines.append(f'## {category}')
        lines.append('')
        if lang_sections:
            for lang in ['中文', 'English']:
                subset = [x for x in items if x['language'] == lang]
                if not subset:
                    continue
                lines.append(f'### {lang}')
                lines.append('')
                for e in subset:
                    lines.append(render_entry(e, include_tags))
                lines.append('')
        else:
            for e in items:
                lines.append(render_entry(e, include_tags))
            lines.append('')
    return '\n'.join(lines)

def render_entry(entry, include_tags):
    title = entry['title']
    rel = entry['rel']
    summary = entry['summary']
    tags = entry.get('tags') or []
    tail = ''
    if include_tags and tags:
        tail = ' (tags: ' + ', '.join(tags) + ')'
    if summary:
        return f'- [{title}]({rel}) - {summary}{tail}'
    return f'- [{title}]({rel}){tail}'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docs-dir', default='./docs')
    parser.add_argument('--map-file', default='./MAP.md')
    parser.add_argument('--ignore', action='append', default=[])
    parser.add_argument('--summary-max-len', type=int, default=80)
    parser.add_argument('--max-head-lines', type=int, default=200)
    parser.add_argument('--max-per-category', type=int, default=0)
    parser.add_argument('--no-tags', dest='include_tags', action='store_false')
    parser.set_defaults(include_tags=True)
    parser.add_argument('--lang-sections', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    cwd = os.getcwd()
    docs_dir = os.path.abspath(args.docs_dir)
    ignore_patterns = DEFAULT_IGNORE + (args.ignore or [])
    files = collect_markdown_files(docs_dir, cwd, ignore_patterns) if os.path.isdir(docs_dir) else []
    entries = build_entries(files, cwd, args.summary_max_len, args.max_head_lines, ignore_patterns)
    script_rel_path = './.trae/skills/project-navigator/scripts/maintain_map.py'
    content = render_map(
        entries,
        args.docs_dir,
        args.map_file,
        script_rel_path,
        ignore_patterns,
        args.summary_max_len,
        args.include_tags,
        args.lang_sections,
        args.max_per_category,
        args.max_head_lines,
        args.ignore or [],
    )
    map_path = os.path.abspath(args.map_file)
    os.makedirs(os.path.dirname(map_path), exist_ok=True)
    if args.dry_run:
        print(content)
        return
    with open(map_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    main()
