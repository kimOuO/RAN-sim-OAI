"""最小 Markdown → HTML(只支援本倉庫文件用到的語法),給 Chrome --print-to-pdf 排版。"""
import html, re, sys, pathlib

def inline(t):
    t = html.escape(t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img alt="\1" src="\2">', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)
    return t

def convert(md):
    out, i, lines = [], 0, md.split('\n')
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('```'):
            i += 1; buf = []
            while i < len(lines) and not lines[i].startswith('```'):
                buf.append(html.escape(lines[i])); i += 1
            i += 1
            out.append('<pre><code>' + '\n'.join(buf) + '</code></pre>'); continue
        if re.match(r'^\s*\|', ln) and i + 1 < len(lines) and re.match(r'^\s*\|[\s:|-]+\|?\s*$', lines[i+1]):
            def cells(r): return [c.strip() for c in r.strip().strip('|').split('|')]
            head = cells(ln); i += 2; rows = []
            while i < len(lines) and re.match(r'^\s*\|', lines[i]):
                rows.append(cells(lines[i])); i += 1
            out.append('<table><thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in head) + '</tr></thead><tbody>'
                       + ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in rows)
                       + '</tbody></table>'); continue
        m = re.match(r'^(#{1,6})\s+(.*)$', ln)
        if m:
            lv = len(m.group(1)); out.append(f'<h{lv}>{inline(m.group(2))}</h{lv}>'); i += 1; continue
        if re.match(r'^\s*[-*]\s+', ln) or re.match(r'^\s*\d+\.\s+', ln):
            ordered = bool(re.match(r'^\s*\d+\.\s+', ln)); tag = 'ol' if ordered else 'ul'
            items = []
            while i < len(lines) and (re.match(r'^\s*[-*]\s+', lines[i]) or re.match(r'^\s*\d+\.\s+', lines[i])):
                items.append(inline(re.sub(r'^\s*(?:[-*]|\d+\.)\s+', '', lines[i]))); i += 1
            out.append(f'<{tag}>' + ''.join(f'<li>{x}</li>' for x in items) + f'</{tag}>'); continue
        if ln.startswith('>'):
            buf = []
            while i < len(lines) and lines[i].startswith('>'):
                buf.append(inline(lines[i].lstrip('> ').rstrip())); i += 1
            out.append('<blockquote>' + '<br>'.join(buf) + '</blockquote>'); continue
        if re.match(r'^\s*---+\s*$', ln):
            out.append('<hr>'); i += 1; continue
        if ln.strip() == '':
            i += 1; continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#{1,6}\s|```|>|\s*[-*]\s|\s*\d+\.\s|\s*\|)', lines[i]) \
                and not re.match(r'^\s*---+\s*$', lines[i]):
            buf.append(inline(lines[i])); i += 1
        if buf: out.append('<p>' + '<br>'.join(buf) + '</p>')
    return '\n'.join(out)

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm; }
body { font-family: "Noto Sans CJK TC","Noto Sans CJK SC",sans-serif; font-size: 10.5pt; line-height: 1.65; color: #1a1a1a; }
h1 { font-size: 20pt; border-bottom: 2px solid #333; padding-bottom: 6px; margin: 0 0 14px; }
h2 { font-size: 14.5pt; margin: 22px 0 8px; padding-left: 8px; border-left: 4px solid #666; page-break-after: avoid; }
h3 { font-size: 12.5pt; margin: 16px 0 6px; page-break-after: avoid; }
h4 { font-size: 11pt; margin: 12px 0 4px; page-break-after: avoid; }
p { margin: 6px 0; }
code { font-family: "DejaVu Sans Mono",monospace; font-size: 9pt; background: #f2f2f2; padding: 1px 4px; border-radius: 3px; }
pre { background: #f7f7f7; border: 1px solid #ddd; border-radius: 4px; padding: 9px 11px; overflow-wrap: break-word;
      white-space: pre-wrap; page-break-inside: avoid; margin: 8px 0; }
pre code { background: none; padding: 0; font-size: 8.6pt; line-height: 1.45; }
table { border-collapse: collapse; width: 100%; margin: 9px 0; font-size: 9.3pt; page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 4px 7px; text-align: left; vertical-align: top; }
th { background: #eee; font-weight: 600; }
tr:nth-child(even) td { background: #fafafa; }
blockquote { border-left: 3px solid #f0a000; background: #fffbf0; margin: 9px 0; padding: 7px 11px; page-break-inside: avoid; }
ul, ol { margin: 6px 0 6px 20px; padding: 0; }
li { margin: 3px 0; }
hr { border: none; border-top: 1px solid #ddd; margin: 18px 0; }
img { max-width: 100%; border: 1px solid #ddd; border-radius: 3px; margin: 8px 0; page-break-inside: avoid; }
a { color: #05529e; text-decoration: none; }
"""

src = pathlib.Path(sys.argv[1]); dst = pathlib.Path(sys.argv[2])
body = convert(src.read_text(encoding='utf-8'))
base = src.resolve().parent.as_uri() + '/'   # 圖片路徑相對於原始 .md 所在目錄
dst.write_text(f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
               f'<base href="{base}"><title>{html.escape(src.stem)}</title>'
               f'<style>{CSS}</style></head><body>{body}</body></html>', encoding='utf-8')
print(dst)

# 用法(環境沒有 pandoc,用 puppeteer 附帶的 Chrome 列印):
#   python3 tools/md2pdf.py docs/frontend_guide.md /tmp/x.html
#   ~/.cache/puppeteer/chrome/linux-*/chrome-linux64/chrome --headless --disable-gpu --no-sandbox \
#       --no-pdf-header-footer --print-to-pdf=docs/輸出.pdf file:///tmp/x.html
# 圖片以 <base href> 指回原始 .md 所在目錄,相對路徑的截圖會一起進 PDF。
