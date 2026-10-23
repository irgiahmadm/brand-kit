"""Review board for exploration rounds: one row per concept, shown light and reversed, and tried in real
places at real size (browser tab at 16 px, app icon, nav bar) instead of a bare size ladder.

Usage:  python contact_sheet.py a.svg b.svg c.svg --brand "Kopi Kilat" \
            --names "Bolt cup" "KK monogram" "Steam" \
            --notes "idea in one line" ... --risks "honest risk" ... \
            [--title "Round 2"] [--lang ja --labels labels.ja.json] -o round2.html [--png]
        python contact_sheet.py --print-labels > labels.json     # English labels to translate

Deliberately has NO "recommended" badge: in exploration the user picks. Add your opinion in chat only if asked.
Black-and-white first: colour starts taste debates before the shape is settled. The reversed tile is a CSS
inversion, so draw roughs in pure black.
"""
import argparse, base64, html, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# English defaults. For any other language, translate these into a JSON file and pass --labels (dump them with
# --print-labels). The sheet speaks the product's language, not the script's.
LABELS = {"round": "Exploration", "concepts": "concepts", "light": "On light", "dark": "Reversed",
          "tab": "Browser tab · 16 px", "icon": "App icon", "nav": "Nav bar · 32 px", "risk": "Watch out",
          "reply": "Reply with letters and a direction, e.g. “B, but rounder” or “none of these, try letterforms”."}


def uri(p):
    return "data:image/svg+xml;base64," + base64.b64encode(open(p, "rb").read()).decode()


CSS = """
*{box-sizing:border-box}
body{margin:0;background:#ECEAE4;color:#17171A;font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:36px 40px 28px;background:#17171A;color:#F4F2EC;display:flex;justify-content:space-between;align-items:flex-end;gap:24px;flex-wrap:wrap}
header small{font:600 11px/1 ui-monospace,Consolas,monospace;letter-spacing:.14em;text-transform:uppercase;opacity:.6}
header h1{margin:8px 0 0;font-size:30px;line-height:1.1;letter-spacing:-.01em}
header p{margin:0;max-width:440px;opacity:.75;font-size:14px}
main{padding:28px 40px 48px;display:grid;gap:22px}
.row{display:grid;grid-template-columns:64px minmax(260px,1.25fr) minmax(240px,1fr) minmax(200px,.9fr);background:#FBFAF7;border-radius:6px;overflow:hidden}
.tag{background:#17171A;color:#F4F2EC;display:grid;place-items:center;font:700 26px ui-monospace,Consolas,monospace}
.pair{display:grid;grid-template-columns:1fr 1fr}
.pair figure{margin:0;padding:18px;display:grid;place-items:center;min-height:210px;position:relative}
.pair figure:last-child{background:#17171A}
.pair figure:last-child img{filter:invert(1)}
.pair img{max-width:100%;max-height:150px}
.pair figcaption,.ctx b{position:absolute;left:12px;top:10px;font:600 10px ui-monospace,Consolas,monospace;letter-spacing:.1em;text-transform:uppercase;opacity:.5}
.pair figure:last-child figcaption{color:#F4F2EC}
.ctx{display:grid;gap:10px;padding:16px;border-left:1px solid #E2DFD7;align-content:center}
.ctx>div{position:relative;padding-top:16px}
.ctx b{top:0;left:0}
.tab{display:flex;align-items:center;gap:8px;background:#E4E1DA;border-radius:8px 8px 0 0;padding:7px 12px;width:max-content;max-width:100%;font-size:12px}
.tab img{height:16px;width:16px;object-fit:contain}
.icons{display:flex;gap:12px;align-items:center}
.icons span{width:60px;height:60px;border-radius:14px;display:grid;place-items:center;background:#17171A}
.icons span img{width:38px;height:38px;object-fit:contain;filter:invert(1)}
.icons span.l{background:#fff;box-shadow:inset 0 0 0 1px #E2DFD7}
.icons span.l img{filter:none}
.nav{display:flex;align-items:center;gap:10px;border-bottom:1px solid #E2DFD7;padding:6px 0;font-weight:650}
.nav img{height:32px;width:auto;max-width:120px}
.nav i{margin-left:auto;font-style:normal;font-size:12px;opacity:.5}
.txt{padding:20px 22px;border-left:1px solid #E2DFD7}
.txt h2{margin:0 0 6px;font-size:19px;line-height:1.25}
.txt p{margin:0 0 12px;font-size:14px;opacity:.85}
.txt .risk{border-left:3px solid #D9822B;padding:2px 0 2px 10px;font-size:13px}
.txt .risk em{display:block;font:600 10px ui-monospace,Consolas,monospace;letter-spacing:.1em;text-transform:uppercase;font-style:normal;opacity:.6}
@media (max-width:900px){.row{grid-template-columns:48px 1fr}.ctx,.txt{grid-column:2;border-left:0;border-top:1px solid #E2DFD7}.pair{grid-column:2}.tag{grid-row:span 3}header,main{padding-left:16px;padding-right:16px}}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    if "--print-labels" in sys.argv:
        print(json.dumps(LABELS, indent=2, ensure_ascii=False))
        return
    ap.add_argument("svgs", nargs="+")
    ap.add_argument("--names", nargs="*", default=[]); ap.add_argument("--notes", nargs="*", default=[])
    ap.add_argument("--risks", nargs="*", default=[])
    ap.add_argument("--brand", default="Brand"); ap.add_argument("--title", default="")
    ap.add_argument("--lang", default="en", help="BCP 47 code for the page, e.g. en, id, ja, pt-BR")
    ap.add_argument("--labels", help="JSON file with translated labels (any subset of --print-labels)")
    ap.add_argument("-o", "--out", default="sheet.html"); ap.add_argument("--png", action="store_true")
    a = ap.parse_args()
    T = {**LABELS, **(json.load(open(a.labels, encoding="utf-8")) if a.labels else {})}
    esc = html.escape
    pick = lambda xs, i: xs[i] if i < len(xs) else ""
    rows = []
    for i, s in enumerate(a.svgs):
        u, letter = uri(s), chr(65 + i)
        name = pick(a.names, i) or os.path.splitext(os.path.basename(s))[0]
        risk = pick(a.risks, i)
        rows.append(f"""<section class="row"><div class="tag">{letter}</div>
<div class="pair"><figure><figcaption>{T['light']}</figcaption><img src="{u}" alt=""></figure>
<figure><figcaption>{T['dark']}</figcaption><img src="{u}" alt=""></figure></div>
<div class="ctx"><div><b>{T['tab']}</b><span class="tab"><img src="{u}" alt="">{esc(a.brand)}</span></div>
<div><b>{T['icon']}</b><span class="icons"><span><img src="{u}" alt=""></span><span class="l"><img src="{u}" alt=""></span></span></div>
<div><b>{T['nav']}</b><span class="nav"><img src="{u}" alt="">{esc(a.brand)}<i>· · ·</i></span></div></div>
<div class="txt"><h2>{letter} · {esc(name)}</h2><p>{esc(pick(a.notes, i))}</p>
{f'<p class="risk"><em>{T["risk"]}</em>{esc(risk)}</p>' if risk else ''}</div></section>""")
    title = a.title or T["round"]
    page = f"""<!doctype html><html lang="{esc(a.lang)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(a.brand)} · {esc(title)}</title>
<style>{CSS}</style></head><body>
<header><div><small>{esc(a.brand)} · {len(a.svgs)} {T['concepts']}</small><h1>{esc(title)}</h1></div><p>{T['reply']}</p></header>
<main>{''.join(rows)}</main></body></html>"""
    open(a.out, "w", encoding="utf-8").write(page)
    print("wrote", a.out)
    if a.png:
        import render
        render.shot(a.out, os.path.splitext(a.out)[0] + ".png", w=1280, h=200 + len(a.svgs) * 262)


if __name__ == "__main__":
    main()
