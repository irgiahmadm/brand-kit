"""Look at your work: headless Chrome/Edge screenshots for SVGs, HTML pages, brand books and mobile checks.

Usage:
  python render.py png  mark.svg -o mark.png --size 512            # SVG -> PNG (transparent)
  python render.py shot page.html -o page.png --w 1280 --h 4000 [--t 900] [--dark] [--scale 2]
  python render.py shot book.html -o color.png --only color [--dark]   # one section: the cheap way to check
  python render.py slice page.png --h 1400                          # cut a tall screenshot into readable parts
  python render.py mobile page.html -o mobile.png [--w 375]         # real narrow layout via an iframe
  python render.py overflow page.html [--w 1280]                    # list elements wider than the viewport
  python render.py ico favicon-tile.svg -o favicon.ico              # 16/32/48 ICO (needs Pillow)

Notes:
- `--t` freezes CSS animations at that millisecond (pages built by build_book.py honour ?t=). Screenshot a
  few different t values to check an animation's poses.
- Browsers enforce a minimum window width (~480-500 px on Windows), so a 375 px --w window is NOT a phone
  layout. Use `mobile`, which renders inside a 375 px iframe.
- `#anchor` URLs are unreliable in headless screenshots; take one tall shot and `slice` it instead.
- Read every PNG you produce. A render you didn't look at is a render you didn't check.
- Every PNG is trimmed of empty space at the bottom and scaled to at most 1568 px / 1.15 MP, and the script prints
  roughly what viewing it costs ("~N tokens", Claude's w*h/750 rule; other models are similar). Tall pages are not
  shrunk (they'd be unreadable): check them with --only, or slice them and say how many parts you'll look at.
"""
import argparse, glob, os, re, shutil, subprocess, sys, tempfile, urllib.parse

CANDIDATES = [
    os.environ.get("BROWSER", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
]


def browser():
    for c in CANDIDATES:
        if not c:
            continue
        p = c if os.path.isabs(c) else shutil.which(c)
        if p and os.path.exists(p):
            return p
    sys.exit("No Chrome/Edge/Chromium found. Install one or set BROWSER=/path/to/browser.")


def url_of(path, query=""):
    u = "file:///" + os.path.abspath(path).replace("\\", "/").lstrip("/")
    return u + (("?" + query) if query else "")


def run(args, timeout=120):
    return subprocess.run([browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars", *args],
                          capture_output=True, text=True, timeout=timeout)


MAX_EDGE, MAX_PX = 1568, 1_150_000


def tokens(w, h):
    return max(1, round(w * h / 750))


def fit(png):
    """Trim empty bottom, shrink to what a model actually sees, report the viewing cost. Returns tokens."""
    from PIL import Image
    im = Image.open(png)
    W, H = im.size
    bg = im.getpixel((W - 2, H - 2))
    step = max(1, W // 60)
    last = max((y for y in range(0, H, 8) if any(im.getpixel((x, y)) != bg for x in range(0, W, step))), default=H)
    if last + 24 < H:
        im = im.crop((0, 0, W, min(H, last + 24)))
        W, H = im.size
    if W >= 800 and H > 2 * W and H > MAX_EDGE:
        im.save(png)
        n = -(-H // 1400)
        print(f"  {W}x{H}: too tall to view in one image. Use --only <section>, or slice (~{n} parts, "
              f"~{n * tokens(W, 1400) if W * 1400 <= MAX_PX else n * tokens(*_scaled(W, 1400))} tokens)")
        return None
    W2, H2 = _scaled(W, H)
    if (W2, H2) != (W, H):
        im = im.resize((W2, H2), Image.LANCZOS)
    im.save(png, optimize=True)
    t = tokens(W2, H2)
    print(f"  {W2}x{H2}, ~{t} tokens to view")
    return t


def _scaled(W, H):
    k = min(1, MAX_EDGE / max(W, H), (MAX_PX / (W * H)) ** .5)
    return max(1, int(W * k)), max(1, int(H * k))


def shot(path, out, w=1280, h=900, scale=1, t=None, dark=False, budget=4000, only=None, fit_it=True):
    q = "&".join(x for x in [f"t={t}" if t is not None else "", "dark=1" if dark else "",
                             f"only={only}" if only else ""] if x)
    if not os.path.exists(path):
        sys.exit(f"cannot screenshot: {path} does not exist")
    if os.path.exists(out):
        os.unlink(out)
    run([f"--window-size={w},{h}", f"--force-device-scale-factor={scale}", f"--virtual-time-budget={budget}",
         f"--screenshot={os.path.abspath(out)}", url_of(path, q)])
    if not os.path.exists(out):
        sys.exit(f"screenshot failed for {path}")
    print("wrote", out)
    if fit_it:
        fit(out)


def svg_png(svg, out, size=512, bg="transparent"):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    tmp.write(f'<!doctype html><html><body style="margin:0;background:{bg};width:{size}px;height:{size}px;display:grid;place-items:center">'
              f'<img src="{url_of(svg)}" style="max-width:100%;max-height:100%"></body></html>')
    tmp.close()
    args = [f"--window-size={size},{size}", f"--screenshot={os.path.abspath(out)}", url_of(tmp.name)]
    if bg == "transparent":
        args.insert(0, "--default-background-color=00000000")
    run(args)
    os.unlink(tmp.name)
    print(f"wrote {out}  (~{tokens(size, size)} tokens to view)")


def slice_png(png, h=1400):
    from PIL import Image
    im = Image.open(png)
    W, H = im.size
    bg = im.getpixel((W - 2, H - 2))
    last = max((y for y in range(0, H, 20) if any(im.getpixel((x, y)) != bg for x in range(0, W, 25))), default=H)
    base = os.path.splitext(png)[0]
    n, total = 0, 0
    for y in range(0, last, h):
        part = im.crop((0, y, W, min(y + h, last + 40)))
        pw, ph = _scaled(*part.size)
        part.resize((pw, ph)).save(f"{base}-{n:02d}.png")
        total += tokens(pw, ph)
        n += 1
    print(f"{n} parts: {base}-00.png …  (~{total} tokens to view all; look only at the parts you changed)")


def mobile(path, out, w=375, h=2400):
    tmp = os.path.join(os.path.dirname(os.path.abspath(path)), "_mobile_frame.html")
    open(tmp, "w", encoding="utf-8").write(
        f'<!doctype html><html><body style="margin:0;background:#888;padding:10px">'
        f'<iframe src="{os.path.basename(path)}?t=900" style="width:{w}px;height:{h}px;border:0;background:#fff"></iframe></body></html>')
    shot(tmp, out, w=w + 40, h=h + 20, fit_it=False)
    os.unlink(tmp)
    fit(out)


def overflow(path, w=1280):
    src = open(path, encoding="utf-8").read()
    probe = """<script>window.addEventListener('load',()=>{let t='';try{const W=document.documentElement.clientWidth,o=[];
for(const e of document.querySelectorAll('body *')){const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();
if(r.right>W+1&&p.right<=W+1)o.push(e.tagName+'.'+e.className+' w='+Math.round(r.width))}
t='W='+W+' scrollW='+document.documentElement.scrollWidth+' | '+o.slice(0,30).join(' | ')}catch(err){t='ERR '+err}document.title=t;});</script></body>"""
    tmp = os.path.join(os.path.dirname(os.path.abspath(path)), "_overflow_probe.html")
    open(tmp, "w", encoding="utf-8").write(src.replace("</body>", probe))
    r = run([f"--window-size={w},900", "--virtual-time-budget=5000", "--dump-dom", url_of(tmp)])
    os.unlink(tmp)
    m = re.search(r"<title>(.*?)</title>", r.stdout, re.S)
    print(m.group(1) if m else "no result")
    print("(elements inside scroll containers such as code blocks are expected; the page itself overflows only if scrollW > W)")


def ico(svg, out, sizes=(16, 32, 48)):
    from PIL import Image
    d = tempfile.mkdtemp()
    imgs = []
    for s in sizes:
        p = os.path.join(d, f"{s}.png")
        svg_png(svg, p, s)
        imgs.append(Image.open(p).convert("RGBA"))
    imgs[-1].save(out, sizes=[(s, s) for s in sizes], append_images=imgs[:-1])
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("png"); p.add_argument("svg", nargs="+"); p.add_argument("-o"); p.add_argument("--size", type=int, default=512); p.add_argument("--bg", default="transparent")
    p = sub.add_parser("shot"); p.add_argument("page"); p.add_argument("-o", required=True); p.add_argument("--w", type=int, default=1280)
    p.add_argument("--h", type=int, default=900); p.add_argument("--scale", type=float, default=1); p.add_argument("--t"); p.add_argument("--dark", action="store_true")
    p.add_argument("--only", help="brand book only: comma-separated section/sub-section ids to show")
    p.add_argument("--full", action="store_true", help="keep the raw screenshot (for slice); no trim/resize")
    p = sub.add_parser("slice"); p.add_argument("png"); p.add_argument("--h", type=int, default=1400)
    p = sub.add_parser("mobile"); p.add_argument("page"); p.add_argument("-o", required=True); p.add_argument("--w", type=int, default=375)
    p = sub.add_parser("overflow"); p.add_argument("page"); p.add_argument("--w", type=int, default=1280)
    p = sub.add_parser("ico"); p.add_argument("svg"); p.add_argument("-o", required=True)
    a = ap.parse_args()
    if a.cmd == "png":
        for s in a.svg:
            svg_png(s, a.o if (a.o and len(a.svg) == 1) else os.path.splitext(s)[0] + ".png", a.size, a.bg)
    elif a.cmd == "shot":
        shot(a.page, a.o, a.w, a.h if not (a.only and a.h == 900) else 6000, a.scale, a.t, a.dark,
             only=a.only, fit_it=not a.full)
    elif a.cmd == "slice":
        slice_png(a.png, a.h)
    elif a.cmd == "mobile":
        mobile(a.page, a.o, a.w)
    elif a.cmd == "overflow":
        overflow(a.page, a.w)
    elif a.cmd == "ico":
        ico(a.svg, a.o)
