#!/usr/bin/env python3
"""Render the supervisor-scenario markdown reports into one standalone HTML page.

Usage: python render_html.py   ->  writes index.html next to the reports.
No third-party dependencies and no CDN assets, so the output opens offline.
"""
from __future__ import annotations

import html
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "index.html"
REPORTS = [
    ("breakout", "supervisor-breakout-report.md", "破圈实验报告"),
    ("engineering", "supervisor-engineering-report.md", "工程评估报告"),
]
# Code blocks longer than this collapse into a <details> toggle.
COLLAPSE_AFTER = 14

_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def inline(text: str) -> str:
    """Escape a line, then apply inline code / bold / link markup."""
    out = html.escape(text, quote=False)
    spans: list[str] = []

    def stash(match: re.Match[str]) -> str:
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    out = _CODE.sub(stash, out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _LINK.sub(r'<a href="\2">\1</a>', out)
    for index, span in enumerate(spans):
        out = out.replace(f"\x00{index}\x00", f"<code>{span}</code>")
    return out


def slugify(text: str, seen: dict[str, int]) -> str:
    base = re.sub(r"[^\w一-鿿-]+", "-", text).strip("-").lower() or "section"
    seen[base] = seen.get(base, 0) + 1
    return base if seen[base] == 1 else f"{base}-{seen[base]}"


def convert(md: str, prefix: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Return (html_body, toc) where toc entries are (level, title, anchor)."""
    body: list[str] = []
    toc: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}
    lines = md.splitlines()
    index = 0
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    while index < len(lines):
        line = lines[index]

        fence = re.match(r"^```(\w*)\s*$", line)
        if fence:
            lang = fence.group(1)
            index += 1
            buf: list[str] = []
            while index < len(lines) and not lines[index].startswith("```"):
                buf.append(lines[index])
                index += 1
            index += 1  # skip closing fence
            close_list()
            code = html.escape("\n".join(buf), quote=False)
            block = f'<pre class="code" data-lang="{lang or "text"}"><code>{code}</code></pre>'
            if len(buf) > COLLAPSE_AFTER:
                body.append(
                    "<details class='fold'><summary>"
                    f"{lang or 'text'} · {len(buf)} 行</summary>{block}</details>"
                )
            else:
                body.append(block)
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            close_list()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            anchor = f"{prefix}-{slugify(title, seen)}"
            toc.append((level, title, anchor))
            body.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>')
            index += 1
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", line)
        if bullet:
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{inline(bullet.group(1))}</li>")
            index += 1
            continue

        if not line.strip():
            close_list()
            index += 1
            continue

        close_list()
        para = [line.strip()]
        index += 1
        while index < len(lines) and lines[index].strip() and not re.match(
            r"^(#{1,6}\s|[-*]\s|```)", lines[index]
        ):
            para.append(lines[index].strip())
            index += 1
        body.append(f"<p>{inline(' '.join(para))}</p>")

    close_list()
    return "\n".join(body), toc


CSS = """
:root {
  --bg: #0f1115; --panel: #161a21; --line: #262c37; --text: #dfe4ec;
  --muted: #94a0b3; --accent: #6ea8fe; --code-bg: #11151c;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f6f7f9; --panel: #fff; --line: #e2e6ec; --text: #1c2430;
    --muted: #5d6b7e; --accent: #1257c4; --code-bg: #f2f4f8;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.7 "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
}
.layout { display: flex; min-height: 100vh; }
aside {
  width: 310px; flex: 0 0 310px; background: var(--panel);
  border-right: 1px solid var(--line); position: sticky; top: 0;
  height: 100vh; overflow-y: auto; padding: 20px 0 40px;
}
aside h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .08em;
  color: var(--muted); margin: 18px 20px 8px; }
.tabs { display: flex; gap: 8px; padding: 0 20px 14px; border-bottom: 1px solid var(--line); }
.tabs button {
  flex: 1; padding: 8px 10px; cursor: pointer; border-radius: 7px;
  border: 1px solid var(--line); background: transparent; color: var(--text); font: inherit;
}
.tabs button[aria-selected="true"] { background: var(--accent); border-color: var(--accent); color: #fff; }
nav a {
  display: block; padding: 4px 20px; color: var(--muted);
  text-decoration: none; font-size: 13px; border-left: 2px solid transparent;
}
nav a:hover { color: var(--text); background: rgba(110,168,254,.10); }
nav a.lvl-1, nav a.lvl-2 { color: var(--text); font-weight: 600; margin-top: 6px; }
nav a.lvl-3 { padding-left: 32px; }
nav a.lvl-4 { padding-left: 44px; font-size: 12.5px; }
main { flex: 1; min-width: 0; padding: 34px 46px 90px; max-width: 1080px; }
h1 { font-size: 26px; border-bottom: 1px solid var(--line); padding-bottom: 12px; }
h2 { font-size: 21px; margin-top: 38px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
h3 { font-size: 17px; margin-top: 28px; color: var(--accent); }
h4 { font-size: 14.5px; margin: 20px 0 6px; color: var(--muted);
  text-transform: uppercase; letter-spacing: .05em; }
code {
  background: var(--code-bg); border: 1px solid var(--line); border-radius: 4px;
  padding: 1px 5px; font-family: Consolas, "Cascadia Mono", monospace; font-size: 13px;
  overflow-wrap: anywhere;
}
pre.code {
  background: var(--code-bg); border: 1px solid var(--line); border-radius: 8px;
  padding: 14px 16px; overflow-x: auto; font-size: 12.5px; line-height: 1.55;
}
pre.code code { background: none; border: 0; padding: 0; }
details.fold { margin: 10px 0; }
details.fold > summary {
  cursor: pointer; color: var(--accent); font-size: 13px; padding: 6px 10px;
  background: var(--code-bg); border: 1px solid var(--line); border-radius: 7px;
}
ul { padding-left: 22px; } li { margin: 3px 0; }
.report[hidden] { display: none; }
.meta { color: var(--muted); font-size: 13px; margin: 0 0 6px; }
.meta a { color: var(--accent); }
@media (max-width: 860px) {
  .layout { flex-direction: column; }
  aside { position: static; width: auto; flex: none; height: auto; border-right: 0;
    border-bottom: 1px solid var(--line); }
  main { padding: 22px 18px 60px; }
}
"""

JS = """
const buttons = [...document.querySelectorAll('.tabs button')];
function show(id) {
  buttons.forEach(b => b.setAttribute('aria-selected', String(b.dataset.target === id)));
  document.querySelectorAll('.report').forEach(s => { s.hidden = s.id !== 'report-' + id; });
  document.querySelectorAll('nav').forEach(n => { n.hidden = n.dataset.owner !== id; });
  history.replaceState(null, '', '#' + id);
}
buttons.forEach(b => b.addEventListener('click', () => show(b.dataset.target)));
document.querySelectorAll('nav a').forEach(a => a.addEventListener('click', e => {
  e.preventDefault();
  const el = document.querySelector(a.getAttribute('href'));
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}));
show((location.hash || '').replace('#', '') || buttons[0].dataset.target);
"""


def main() -> None:
    tabs, navs, sections = [], [], []
    for key, filename, label in REPORTS:
        source = HERE / filename
        if not source.exists():
            continue
        body, toc = convert(source.read_text(encoding="utf-8"), key)
        tabs.append(f'<button data-target="{key}" aria-selected="false">{label}</button>')
        links = "".join(
            f'<a class="lvl-{lvl}" href="#{anchor}">{html.escape(title)}</a>'
            for lvl, title, anchor in toc
            if lvl <= 4
        )
        navs.append(f'<nav data-owner="{key}" hidden><h2>{label}</h2>{links}</nav>')
        sections.append(
            f'<section class="report" id="report-{key}" hidden>'
            f'<p class="meta">来源：<a href="{filename}">{filename}</a></p>{body}</section>'
        )

    raw = sorted((HERE / "raw").glob("*.json")) if (HERE / "raw").is_dir() else []
    raw_links = " · ".join(f'<a href="raw/{p.name}">{p.name}</a>' for p in raw)
    raw_html = f'<h2>原始数据</h2><div class="meta" style="padding:0 20px">{raw_links}</div>' if raw_links else ""

    OUT.write_text(
        "<!doctype html>\n<html lang=\"zh-CN\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>副 Agent 场景实验报告</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n"
        f'<div class="layout"><aside><div class="tabs">{"".join(tabs)}</div>'
        f'{"".join(navs)}{raw_html}</aside>'
        f'<main>{"".join(sections)}</main></div>\n'
        f"<script>{JS}</script>\n</body>\n</html>\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()


