"""Build the full logo kit from one master mark + a small JSON config.

Usage:  python make_kit.py kit.json

The master mark is an SVG whose <path> elements carry data-role="main" | "accent" | ... (geometry.write_svg does
this). Recolouring works per role, so the accent (e.g. a coin) can keep its colour while the rest flips.

kit.json example (all colours are hex):
{
  "name": "acme",                       // file prefix
  "mark": "mark.svg",                   // master, roles tagged
  "small_mark": "mark-small.svg",       // optional simplified cut for < 24 px (favicon); defaults to mark
  "out": "files",
  "wordmark": {"text": "Acme", "font": "fonts/Brand.ttf", "axes": {"wght": 600}, "tracking": 0,
               "cap_ratio": 0.60, "gap_ratio": 0.30, "stacked_cap_ratio": 0.46, "stacked_gap_ratio": 0.26},
  "colourways": {
    "":          {"main": "#302017", "accent": "#FD8537", "text": "#302017"},
    "-reversed": {"main": "#F9F0E3", "accent": "#FD8537", "text": "#F9F0E3"},
    "-black":    {"*": "#000000"},
    "-white":    {"*": "#FFFFFF"}
  },
  "app_icon": {"bg": "#180C05", "roles": {"main": "#F9F0E3", "accent": "#FD8537"}, "scale": 0.72, "radius": 0.225},
  "favicon":  {"bg": "#180C05", "roles": {"main": "#F9F0E3", "accent": "#FD8537"}, "scale": 0.78, "radius": 0.22,
               "adaptive": {"light": "#302017", "dark": "#F9F0E3", "role": "main"}},
  "theme_color": "#180C05",
  "mobile": {"splash_bg": "#F9F0E3", "splash_bg_dark": "#180C05"}   // optional; "mobile": false skips it
}

Writes <name>-mark*.svg, -mark-small*.svg, -horizontal*.svg, -stacked*.svg, -wordmark.svg, -app-icon.svg and
web/ (favicon.svg adaptive light/dark, favicon.ico, icon PNGs, maskable, site.webmanifest, head-snippet.html).
Also writes mobile/ when app_icon is set (all optional keys under "mobile"):
  ios/AppIcon.appiconset      1024 icon + dark + tinted variants, Contents.json (Xcode 16+)
  ios/BrandMark.imageset      vector logo for in-app use, with a dark-mode variant
  android/res/...             adaptive icon (vector foreground + monochrome for themed icons), legacy mipmaps,
                              splash icon (Android 12 SplashScreen), vector logo (+ drawable-night), colours
  android/play-store-512.png
  store/                      1024 PNGs for Expo / Flutter tooling + expo-app.json and flutter_*.yaml snippets
Keys: splash_bg, splash_bg_dark, ios_dark_roles, android_fill (share of the 108 dp canvas, default .5).
PNG/ICO need a Chromium browser (render.py) and Pillow; SVGs and XML are always written.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from geometry import to_path, to_d, transform, union, bounds  # noqa: E402


def read_roles(svg_path):
    s = open(svg_path, encoding="utf-8").read()
    layers = []
    for m in re.finditer(r"<path\b([^>]*)>", s):
        attrs = m.group(1)
        d = re.search(r'\sd="([^"]+)"', attrs)
        role = re.search(r'data-role="([^"]+)"', attrs)
        if d:
            layers.append((to_path(d.group(1)), role.group(1) if role else "main"))
    if not layers:
        sys.exit(f"no <path> found in {svg_path}")
    return layers


def colour(way, role):
    return way.get(role) or way.get("*") or way.get("main") or "#000000"


def svg_doc(items, b, pad, height, title):
    x0, y0, x1, y1 = b
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    body = "\n".join(f'<path fill="{fill}" d="{d}"/>' for d, fill in items)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-pad:.2f} {y0-pad:.2f} {w:.2f} {h:.2f}" '
            f'width="{w/h*height:.0f}" height="{height}">\n<title>{title}</title>\n{body}\n</svg>\n')


def tile_svg(layers, roles, bg, scale, radius, size=1024, title="Logo"):
    b = bounds(*[p for p, _ in layers])
    s = scale * size / max(b[2] - b[0], b[3] - b[1])
    tx, ty = size / 2 - s * (b[0] + b[2]) / 2, size / 2 - s * (b[1] + b[3]) / 2
    r = f' rx="{radius*size:.0f}"' if radius else ""
    paths = "".join(f'<path fill="{colour(roles, role)}" d="{to_d(transform(p, s, 0, 0, s, tx, ty))}"/>' for p, role in layers)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}"><title>{title}</title>'
            f'<rect width="{size}" height="{size}"{r} fill="{bg}"/>{paths}</svg>\n')


def main(cfg_path):
    root = os.path.dirname(os.path.abspath(cfg_path))
    C = json.load(open(cfg_path, encoding="utf-8"))
    P = lambda p: os.path.join(root, p)
    out = P(C.get("out", "files")); web = os.path.join(out, "web")
    os.makedirs(web, exist_ok=True)
    name, title = C["name"], C.get("title", C["name"])
    mark = read_roles(P(C["mark"]))
    small = read_roles(P(C["small_mark"])) if C.get("small_mark") else mark
    MB, SB = bounds(*[p for p, _ in mark]), bounds(*[p for p, _ in small])
    mh = MB[3] - MB[1]
    save = lambda f, s: open(os.path.join(out, f), "w", encoding="utf-8").write(s)
    ways = C["colourways"]

    for suf, way in ways.items():
        save(f"{name}-mark{suf}.svg", svg_doc([(to_d(p), colour(way, r)) for p, r in mark], MB, mh * .08, 256, title))
        save(f"{name}-mark-small{suf}.svg", svg_doc([(to_d(p), colour(way, r)) for p, r in small], SB, (SB[3]-SB[1]) * .07, 256, title))

    wm = C.get("wordmark")
    if wm:
        from outline_text import outline
        axes = wm.get("axes", {})
        cap = wm.get("cap_ratio", .6) * mh
        w = outline(wm["text"], P(wm["font"]), cap, axes, wm.get("tracking", 0))
        wb = w.bounds
        w_h = transform(w, 1, 0, 0, 1, MB[2] + wm.get("gap_ratio", .3) * mh - wb[0], (MB[1] + MB[3]) / 2 + cap / 2)
        cap2 = wm.get("stacked_cap_ratio", .46) * mh
        w2 = outline(wm["text"], P(wm["font"]), cap2, axes, wm.get("tracking", 0)); w2b = w2.bounds
        w_s = transform(w2, 1, 0, 0, 1, (MB[0] + MB[2]) / 2 - (w2b[0] + w2b[2]) / 2, MB[3] + wm.get("stacked_gap_ratio", .26) * mh + cap2)
        for suf, way in ways.items():
            tc = way.get("text") or colour(way, "main")
            items = [(to_d(p), colour(way, r)) for p, r in mark]
            save(f"{name}-horizontal{suf}.svg", svg_doc(items + [(to_d(w_h), tc)], bounds(*[p for p, _ in mark], w_h), mh * .1, 160, title))
            save(f"{name}-stacked{suf}.svg", svg_doc(items + [(to_d(w_s), tc)], bounds(*[p for p, _ in mark], w_s), mh * .1, 256, title))
        save(f"{name}-wordmark.svg", svg_doc([(to_d(w), colour(ways.get("", {}), "text") if ways.get("", {}).get("text") else "#000")], w.bounds, cap * .1, 96, title))

    ai = C.get("app_icon")
    if ai:
        save(f"{name}-app-icon.svg", tile_svg(mark, ai["roles"], ai["bg"], ai.get("scale", .72), ai.get("radius", .225), title=title))
        open(os.path.join(web, "icon-full.svg"), "w").write(tile_svg(mark, ai["roles"], ai["bg"], ai.get("scale", .72), 0, title=title))
        open(os.path.join(web, "maskable.svg"), "w").write(tile_svg(mark, ai["roles"], ai["bg"], min(.6, ai.get("scale", .72)), 0, title=title))
    fv = C.get("favicon")
    if fv:
        open(os.path.join(web, "favicon-tile.svg"), "w").write(tile_svg(small, fv["roles"], fv["bg"], fv.get("scale", .78), fv.get("radius", .22), title=title))
        ad = fv.get("adaptive")
        if ad:
            items = [(to_d(p), "var(--c)" if r == ad.get("role", "main") else colour(ways.get("", {}), r)) for p, r in small]
            s = svg_doc(items, SB, (SB[3]-SB[1]) * .05, 256, title)
            s = s.replace(f"<title>{title}</title>", f"<title>{title}</title><style>:root{{--c:{ad['light']}}}@media (prefers-color-scheme:dark){{:root{{--c:{ad['dark']}}}}}</style>")
            s = s.replace('fill="var(--c)"', 'style="fill:var(--c)"')
            open(os.path.join(web, "favicon.svg"), "w").write(s)
    theme = C.get("theme_color", (ai or {}).get("bg", "#000000"))
    json.dump({"name": title, "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                                        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
                                        {"src": "/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
               "theme_color": theme, "background_color": theme, "display": "standalone"},
              open(os.path.join(web, "site.webmanifest"), "w"), indent=2)
    open(os.path.join(web, "head-snippet.html"), "w").write(
        '<link rel="icon" href="/favicon.ico" sizes="48x48">\n<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
        f'<link rel="apple-touch-icon" href="/apple-touch-icon.png">\n<link rel="manifest" href="/site.webmanifest">\n<meta name="theme-color" content="{theme}">\n')

    try:   # rasters (optional)
        import render
        if ai:
            for f, n, s in (("icon-full.svg", "icon-512.png", 512), ("icon-full.svg", "icon-192.png", 192),
                            ("icon-full.svg", "apple-touch-icon.png", 180), ("maskable.svg", "maskable-512.png", 512)):
                render.svg_png(os.path.join(web, f), os.path.join(web, n), s)
        if fv:
            render.ico(os.path.join(web, "favicon-tile.svg"), os.path.join(web, "favicon.ico"))
    except SystemExit as e:
        print("skipped rasters:", e)
    except Exception as e:  # Pillow missing etc.
        print("skipped rasters:", type(e).__name__, e)
    print("kit written to", out, "-", len(os.listdir(out)), "files +", len(os.listdir(web)), "web files")
    if ai and C.get("mobile") is not False:
        mobile_kit(out, name, mark, small, ai, C, title, theme, ways)


# ------------------------------------------------------------------ mobile
def _fit(layers, viewport, fill, circle=None):
    """Scale + offset that centre the layers in a square viewport; `circle` caps the diagonal (safe zones)."""
    b = bounds(*[p for p, _ in layers])
    w, h = b[2] - b[0], b[3] - b[1]
    s = fill * viewport / max(w, h)
    if circle:
        s = min(s, circle / (w * w + h * h) ** .5)
    return s, viewport / 2 - s * (b[0] + b[2]) / 2, viewport / 2 - s * (b[1] + b[3]) / 2


def vector_drawable(layers, roles, viewport, fill, circle=None, single=None, dp=None, box=None):
    """Android VectorDrawable. Square canvas by default; `box` keeps the mark's own aspect (in-app logo)."""
    if box:
        b = bounds(*[p for p, _ in layers]); pad = (b[3] - b[1]) * .04
        vw, vh, s, tx, ty = b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad, 1, pad - b[0], pad - b[1]
        w_dp, h_dp = round(box * vw / vh), box
    else:
        s, tx, ty = _fit(layers, viewport, fill, circle)
        vw = vh = viewport; w_dp = h_dp = dp or viewport
    paths = "".join(f'\n  <path android:fillColor="{single or colour(roles, r)}"\n    android:pathData="{to_d(transform(p, s, 0, 0, s, tx, ty))}"/>'
                    for p, r in layers)
    return ('<?xml version="1.0" encoding="utf-8"?>\n<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            f'  android:width="{w_dp}dp" android:height="{h_dp}dp"\n  android:viewportWidth="{vw:.2f}" android:viewportHeight="{vh:.2f}">'
            f'{paths}\n</vector>\n')


def svg_tile(layers, roles, bg, fill, radius=0, circle=None, size=1024, title="Logo", single=None):
    """Square SVG for rasterising; bg None = transparent."""
    s, tx, ty = _fit(layers, size, fill, circle)
    rect = f'<rect width="{size}" height="{size}"{f" rx={chr(34)}{radius * size:.0f}{chr(34)}" if radius else ""} fill="{bg}"/>' if bg else ""
    paths = "".join(f'<path fill="{single or colour(roles, r)}" d="{to_d(transform(p, s, 0, 0, s, tx, ty))}"/>' for p, r in layers)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
            f'<title>{title}</title>{rect}{paths}</svg>\n')


def _grey(hexc):
    h = hexc.lstrip("#")[:6]
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return .2126 * r + .7152 * g + .0722 * b


def mobile_kit(out, name, mark, small, ai, cfg, title, theme, ways):
    M = cfg.get("mobile") or {}
    root = os.path.join(out, "mobile")
    ios, andr, store = (os.path.join(root, d) for d in ("ios", "android", "store"))
    res = os.path.join(andr, "res")
    files = {}
    put = lambda path, text: files.__setitem__(path, text)
    roles, bg = ai["roles"], ai["bg"]
    fill = ai.get("scale", .72)
    splash_bg = M.get("splash_bg", theme)
    splash_dark = M.get("splash_bg_dark", splash_bg)
    a_fill = M.get("android_fill", .5)
    used = sorted({r for _, r in mark})

    # --- iOS app icon: square, no transparency, no rounding (iOS masks it); dark = transparent bg; tinted = greys on black
    dark_roles = M.get("ios_dark_roles", roles)
    lum = {r: _grey(colour(roles, r)) for r in used}
    top = max(lum.values()) or 1
    tint_roles = {r: "#{0:02X}{0:02X}{0:02X}".format(int(round(255 * lum[r] / top))) for r in used}
    put(f"{ios}/AppIcon.appiconset/AppIcon-1024.svg", svg_tile(mark, roles, bg, fill, title=title))
    put(f"{ios}/AppIcon.appiconset/AppIcon-1024-dark.svg", svg_tile(mark, dark_roles, None, fill, title=title))
    put(f"{ios}/AppIcon.appiconset/AppIcon-1024-tinted.svg", svg_tile(mark, tint_roles, "#000000", fill, title=title))
    img = lambda f, app=None: {**({"appearances": [{"appearance": "luminosity", "value": app}]} if app else {}),
                               "filename": f, "idiom": "universal", "platform": "ios", "size": "1024x1024"}
    put(f"{ios}/AppIcon.appiconset/Contents.json", json.dumps({"images": [img("AppIcon-1024.png"), img("AppIcon-1024-dark.png", "dark"),
                                                                         img("AppIcon-1024-tinted.png", "tinted")],
                                                              "info": {"author": "xcode", "version": 1}}, indent=2))
    # --- iOS in-app logo (vector, dark variant from the reversed colourway)
    light_way, dark_way = ways.get("", {}), ways.get("-reversed")
    put(f"{ios}/BrandMark.imageset/brand-mark.svg", open(os.path.join(out, f"{name}-mark.svg"), encoding="utf-8").read())
    imgs = [{"filename": "brand-mark.svg", "idiom": "universal"}]
    if dark_way is not None:
        put(f"{ios}/BrandMark.imageset/brand-mark-dark.svg", open(os.path.join(out, f"{name}-mark-reversed.svg"), encoding="utf-8").read())
        imgs.append({"appearances": [{"appearance": "luminosity", "value": "dark"}], "filename": "brand-mark-dark.svg", "idiom": "universal"})
    put(f"{ios}/BrandMark.imageset/Contents.json", json.dumps({"images": imgs, "info": {"author": "xcode", "version": 1},
                                                              "properties": {"preserves-vector-representation": True}}, indent=2))

    # --- Android adaptive icon: 108 dp canvas, content inside the 66 dp safe circle
    put(f"{res}/drawable/ic_launcher_foreground.xml", vector_drawable(mark, roles, 108, a_fill, circle=58))
    put(f"{res}/drawable/ic_launcher_monochrome.xml", vector_drawable(mark, roles, 108, a_fill, circle=58, single="#FFFFFF"))
    adaptive = ('<?xml version="1.0" encoding="utf-8"?>\n<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                '  <background android:drawable="@color/ic_launcher_background"/>\n'
                '  <foreground android:drawable="@drawable/ic_launcher_foreground"/>\n'
                '  <monochrome android:drawable="@drawable/ic_launcher_monochrome"/>\n</adaptive-icon>\n')
    put(f"{res}/mipmap-anydpi-v26/ic_launcher.xml", adaptive)
    put(f"{res}/mipmap-anydpi-v26/ic_launcher_round.xml", adaptive)
    # Android 12+ splash: 288 dp icon, content inside a 192 dp circle
    put(f"{res}/drawable/splash_icon.xml", vector_drawable(mark, light_way or roles, 288, .6, circle=184))
    put(f"{res}/drawable/brand_mark.xml", vector_drawable(mark, light_way or roles, 0, 0, box=48))
    if dark_way is not None:
        put(f"{res}/drawable-night/brand_mark.xml", vector_drawable(mark, dark_way, 0, 0, box=48))
    put(f"{res}/values/brand_colors.xml", '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        f'  <color name="ic_launcher_background">{bg}</color>\n  <color name="splash_background">{splash_bg}</color>\n</resources>\n')
    put(f"{res}/values-night/brand_colors.xml", '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        f'  <color name="splash_background">{splash_dark}</color>\n</resources>\n')

    # --- 1024 sources for Expo / Flutter tooling (and anything else that wants PNGs)
    put(f"{store}/icon-1024.svg", svg_tile(mark, roles, bg, fill, title=title))
    put(f"{store}/adaptive-foreground-1024.svg", svg_tile(mark, roles, None, a_fill, circle=1024 * 58 / 108, title=title))
    put(f"{store}/adaptive-monochrome-1024.svg", svg_tile(mark, roles, None, a_fill, circle=1024 * 58 / 108, title=title, single="#FFFFFF"))
    put(f"{store}/splash-icon-1024.svg", svg_tile(mark, light_way or roles, None, .8, title=title))
    put(f"{store}/expo-app.json", json.dumps({"expo": {
        "icon": "./assets/brand/icon-1024.png",
        "ios": {"icon": {"light": "./assets/brand/icon-1024.png", "dark": "./assets/brand/ios-dark-1024.png",
                         "tinted": "./assets/brand/ios-tinted-1024.png"}},
        "android": {"adaptiveIcon": {"foregroundImage": "./assets/brand/adaptive-foreground-1024.png",
                                     "monochromeImage": "./assets/brand/adaptive-monochrome-1024.png", "backgroundColor": bg}},
        "plugins": [["expo-splash-screen", {"image": "./assets/brand/splash-icon-1024.png", "imageWidth": 200,
                                            "backgroundColor": splash_bg, "dark": {"backgroundColor": splash_dark}}]]}}, indent=2))
    put(f"{store}/flutter_launcher_icons.yaml",
        "# dart run flutter_launcher_icons  (copy the PNGs from this folder to assets/brand/)\nflutter_launcher_icons:\n"
        '  android: "ic_launcher"\n  ios: true\n  remove_alpha_ios: true\n  image_path: "assets/brand/icon-1024.png"\n'
        f'  adaptive_icon_background: "{bg}"\n  adaptive_icon_foreground: "assets/brand/adaptive-foreground-1024.png"\n'
        '  adaptive_icon_monochrome: "assets/brand/adaptive-monochrome-1024.png"\n')
    put(f"{store}/flutter_native_splash.yaml",
        "# dart run flutter_native_splash:create\nflutter_native_splash:\n"
        f'  color: "{splash_bg}"\n  color_dark: "{splash_dark}"\n  image: assets/brand/splash-icon-1024.png\n'
        f'  android_12:\n    image: assets/brand/splash-icon-1024.png\n    color: "{splash_bg}"\n    color_dark: "{splash_dark}"\n')

    for path, text in files.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(text)

    # --- rasters (optional: need Chromium + Pillow)
    try:
        import render
        from PIL import Image
        quiet = lambda svg, png, size: _silent(render.svg_png, svg, png, size)
        aset = os.path.join(ios, "AppIcon.appiconset")
        for v in ("", "-dark", "-tinted"):
            quiet(os.path.join(aset, f"AppIcon-1024{v}.svg"), os.path.join(aset, f"AppIcon-1024{v}.png"), 1024)
            os.unlink(os.path.join(aset, f"AppIcon-1024{v}.svg"))
        for f in ("icon-1024", "adaptive-foreground-1024", "adaptive-monochrome-1024", "splash-icon-1024"):
            quiet(os.path.join(store, f + ".svg"), os.path.join(store, f + ".png"), 1024)
            os.unlink(os.path.join(store, f + ".svg"))
        Image.open(os.path.join(aset, "AppIcon-1024.png")).convert("RGB").save(os.path.join(aset, "AppIcon-1024.png"))
        for v, dst in (("-dark", "ios-dark-1024.png"), ("-tinted", "ios-tinted-1024.png")):
            Image.open(os.path.join(aset, f"AppIcon-1024{v}.png")).save(os.path.join(store, dst))
        big = Image.open(os.path.join(store, "icon-1024.png")).convert("RGB")
        big.resize((512, 512), Image.LANCZOS).save(os.path.join(andr, "play-store-512.png"))
        tmp = os.path.join(root, "_legacy.svg")
        for dens, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
            d = os.path.join(res, f"mipmap-{dens}"); os.makedirs(d, exist_ok=True)
            for fname, rad in (("ic_launcher.png", .18), ("ic_launcher_round.png", .5)):
                open(tmp, "w", encoding="utf-8").write(svg_tile(mark, roles, bg, fill * .8, radius=rad, title=title))
                quiet(tmp, os.path.join(d, fname), px)
        os.unlink(tmp)
    except SystemExit as e:
        print("skipped mobile rasters:", e)
    except Exception as e:
        print("skipped mobile rasters:", type(e).__name__, e)
    n = sum(len(fs) for _, _, fs in os.walk(root))
    print(f"mobile kit: {n} files in {root} (ios/, android/res/, store/)")


def _silent(fn, *a):
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        fn(*a)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
