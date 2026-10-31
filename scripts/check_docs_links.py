#!/usr/bin/env python3
"""Check local Markdown links, image paths and in-page anchors (no network calls)."""
import html
import pathlib
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
LINK = re.compile(r'(?<!!)\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+["\'][^"\']+["\'])?\)|!\[[^\]]*\]\((<[^>]+>|[^\s)]+)\)')
HTML = re.compile(r'\b(?:src|srcset|href)\s*=\s*["\']([^"\']+)["\']')
HEADING = re.compile(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$')

def slug(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'!?(?:\[([^\]]+)\]\([^)]*\))', r'\1', text)
    text = re.sub(r'[`*_~]', '', text).strip().lower()
    text = ''.join(c for c in text if c in '-_ ' or c.isalnum() or unicodedata.category(c).startswith('M'))
    return re.sub(r'\s+', '-', text)

def anchors(path):
    seen, names, fenced = {}, set(), False
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.lstrip().startswith(('\x60\x60\x60', '~~~')):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = HEADING.match(line)
        if m:
            name = slug(m.group(1))
            n = seen.get(name, 0)
            names.add(name + ('-' + str(n) if n else ''))
            seen[name] = n + 1
        for a in re.findall(r'<a\s+[^>]*id=["\']([^"\']+)["\']', line, re.I):
            names.add(a)
    return names

def main():
    failures, checked = [], 0
    docs = [ROOT / 'README.md', ROOT / 'README.tr.md']
    docs += sorted((ROOT / 'docs').rglob('*.md'))
    for page in docs:
        if not page.is_file():
            continue
        fenced = False
        for number, line in enumerate(page.read_text(encoding='utf-8').splitlines(), 1):
            if line.lstrip().startswith(('\x60\x60\x60', '~~~')):
                fenced = not fenced
                continue
            if fenced:
                continue
            urls = [m.group(1) or m.group(2) for m in LINK.finditer(line)]
            urls += HTML.findall(line)
            for url in urls:
                url = html.unescape(url.strip('<>'))
                if not url or url.startswith(('http:', 'https:', 'mailto:', 'data:', '//')):
                    continue
                parts = urlsplit(url)
                if parts.scheme or parts.netloc:
                    continue
                relative = unquote(parts.path)
                target = (ROOT / relative.lstrip('/')) if relative.startswith('/') else (page.parent / relative)
                target = target.resolve()
                checked += 1
                if not target.is_relative_to(ROOT.resolve()):
                    failures.append(f'{page.relative_to(ROOT)}:{number}: outside repository: {url}')
                elif not target.exists():
                    failures.append(f'{page.relative_to(ROOT)}:{number}: missing target: {url}')
                elif parts.fragment and target.is_file() and target.suffix.lower() == '.md':
                    fragment = unquote(parts.fragment)
                    if fragment not in anchors(target):
                        failures.append(f'{page.relative_to(ROOT)}:{number}: missing anchor: {url}')
    if failures:
        print('\n'.join(failures), file=sys.stderr)
        print(f'FAILED: {len(failures)} broken links among {checked} checked', file=sys.stderr)
        return 1
    print(f'PASS: {checked} local links/images/anchors checked across {len(docs)} Markdown pages')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
