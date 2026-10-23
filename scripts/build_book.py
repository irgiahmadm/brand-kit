"""Brand Book builder — turns brand.json (+ optional extras plugin) into ONE self-contained HTML page.

Usage:  python build_book.py brand.json [-o brand-book.html]
        python build_book.py --print-labels > labels.json    # English UI labels, to translate into meta.labels

Language: the book is written in the product's language (meta.lang, any BCP 47 code). Content comes from
brand.json as written; the UI labels default to English and are replaced by meta.labels.

brand.json holds the data (logo files, colours, type, shape, motion, voice, component copy).
An optional "extras" module adds brand-specific sections; it must expose  extend(book) -> dict  with keys
  css, js            extra stylesheet / script
  sections           [{id, title, after, lead, children:[{id, title, html}]}]   new top-level sections
  into               {section_id: [{id, title, html}]}                          sub-sections appended to core sections
  hooks              {hero_art, inline_loader, empty_art}                       html snippets used by core sections
"""
import argparse, base64, html, importlib.util, json, math, os, re, sys

esc = html.escape


# ------------------------------------------------------------------ colour maths
def oklch_hex(L, C, h):
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_, m_, s_ = L + .3963377774*a + .2158037573*b, L - .1055613458*a - .0638541728*b, L - .0894841775*a - 1.291485548*b
    l, m, s = l_**3, m_**3, s_**3
    rgb = (4.0767416621*l - 3.3077115913*m + .2309699292*s, -1.2684380046*l + 2.6097574011*m - .3413193965*s,
           -.0041960863*l - .7034186147*m + 1.707614701*s)
    def enc(x):
        x = min(1, max(0, x))
        return round(255 * (12.92*x if x <= .0031308 else 1.055*x**(1/2.4) - .055))
    return "#%02X%02X%02X" % tuple(enc(v) for v in rgb)


def luminance(hexc):
    r, g, b = (int(hexc[i:i+2], 16) / 255 for i in (1, 3, 5))
    lin = lambda c: c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4
    return .2126*lin(r) + .7152*lin(g) + .0722*lin(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + .05) / (lb + .05)


# ------------------------------------------------------------------ the book
class Book:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.root = os.path.dirname(self.path)
        self.d = json.load(open(self.path, encoding="utf-8"))
        self.meta = self.d["meta"]
        self.labels = {**DEFAULT_LABELS, **self.meta.get("ui", {}), **self.meta.get("labels", {})}
        self.colors = {}
        for g in self.d["colors"]["groups"]:
            for c in g["items"]:
                c["hex"] = c.get("hex") or oklch_hex(*c["oklch"])
                self.colors[c["name"]] = c
        self.ext = {"css": "", "js": "", "sections": [], "into": {}, "hooks": {}}

    def c(self, ref):
        """Colour by name, theme key, or literal hex."""
        if ref.startswith("#"):
            return ref
        if ref in self.colors:
            return self.colors[ref]["hex"]
        th = self.d["theme"]
        if ref in th:
            return self.c(th[ref])
        # optional roles a small brand may not define yet
        fallback = {"success": "#2E7D32", "achievement": "primary", "accent": "secondary",
                    "pending": th["light"]["muted"], "destructive": "#B3261E", "destructive_fg": "#FFFFFF",
                    "secondary": "primary", "secondary_fg": "primary_fg"}
        if ref in fallback:
            return self.c(fallback[ref])
        raise KeyError(f"colour/theme role '{ref}' is not defined in brand.json")

    def L(self, key):
        """UI label: English default, overridable via meta.labels in brand.json."""
        return self.labels.get(key, key)

    def levels(self):
        """(big, mid, pill) level dicts chosen by shape, not list position."""
        L = self.d["shape"]["elevation"]["levels"]
        pills = [l for l in L if l["radius"] >= 500]
        boxes = sorted([l for l in L if l["radius"] < 500], key=lambda l: -l["radius"]) or L
        big = boxes[0]
        mid = boxes[1] if len(boxes) > 1 else boxes[0]
        pill = pills[0] if pills else {**sorted(L, key=lambda l: l["radius"])[0], "radius": 999}
        return big, mid, pill

    def level_css(self, sel, l):
        ev = self.d["shape"]["elevation"]
        if ev.get("style", "offset") == "offset":
            return f'{sel}{{border-radius:{l["radius"]}px;border:{l["border"]}px solid var(--line);box-shadow:{l["offset"]}px {l["offset"]}px 0 0 var(--line)}}'
        return (f'{sel}{{border-radius:{l["radius"]}px;border:{l["border"]}px solid color-mix(in srgb,var(--line) 16%,transparent);'
                f'box-shadow:0 {l["offset"]/2:g}px {l["offset"]*2:g}px color-mix(in srgb,#000 16%,transparent)}}')

    def t(self, key, default=""):
        return self.labels.get(key, default)

    # assets
    def asset_path(self, f):
        return os.path.join(self.root, self.d["logo"]["dir"], f)

    def svg(self, f):
        return open(self.asset_path(f), encoding="utf-8").read()

    def data_uri(self, f):
        return "data:image/svg+xml;base64," + base64.b64encode(open(self.asset_path(f), "rb").read()).decode()

    def img(self, f, h=None, cls="", alt=""):
        style = f' style="height:{h}px"' if h else ""
        return f'<img class="{cls}" src="{self.data_uri(f)}"{style} alt="{esc(alt)}">'

    # blocks
    def code(self, text, lang=""):
        if not text:
            return ""
        return (f'<details class="bb-code"><summary>{esc(self.t("code", "Code"))}</summary>'
                f'<div class="bb-codebox"><button class="bb-copy" type="button">{esc(self.t("copy", "Copy"))}</button>'
                f'<pre><code>{esc(text)}</code></pre></div></details>')

    def load_extras(self):
        rel = self.d.get("extras")
        if not rel:
            return
        p = os.path.join(self.root, rel)
        if os.path.isdir(p):   # package plugin: extras/<brand>/__init__.py (+ helper modules)
            spec = importlib.util.spec_from_file_location("bb_extras", os.path.join(p, "__init__.py"),
                                                          submodule_search_locations=[p])
        else:                  # single-file plugin: extras/<brand>.py
            spec = importlib.util.spec_from_file_location("bb_extras", p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["bb_extras"] = mod
        spec.loader.exec_module(mod)
        out = mod.extend(self)
        for k in self.ext:
            if k in out:
                self.ext[k] = out[k]


# ------------------------------------------------------------------ core sections
def sec_overview(b):
    m, L = b.meta, b.d["logo"]
    sw = "".join(f'<i style="background:{c["hex"]}" title="{esc(c["name"])}"></i>'
                 for g in b.d["colors"]["groups"] for c in g["items"])
    f = b.d["fonts"]
    fonts = " · ".join(f'<span style="font-family:\'{f[k]["family"]}\'">{esc(f[k]["family"])}</span>' for k in ("display", "body", "mono"))
    art = b.ext["hooks"].get("hero_art") or b.img(L["primary"]["light"], 120)
    return [{"id": "overview-hero", "title": m["name"], "html": f'''
      <div class="bb-hero bb-surface lv-big">
        <div class="bb-hero-art">{art}</div>
        <div class="bb-hero-txt">
          <p class="bb-eyebrow">{esc(m.get("system",""))}</p>
          <h1>{esc(m["title"])}</h1>
          <p class="bb-tagline">{esc(m.get("tagline",""))}</p>
          <p>{esc(m.get("summary",""))}</p>
          <div class="bb-hero-facts"><div class="bb-mini-sw">{sw}</div><div class="bb-mini-fonts">{fonts}</div></div>
        </div>
      </div>'''}]


def sec_logo(b):
    L = b.d["logo"]

    def tile(item, big=False):
        bg = {"light": "var(--c-light)", "dark": "var(--c-dark)", "white": "#FFFFFF", "accent": b.c("primary")}[item["bg"]]
        return (f'<figure class="bb-logo-tile{" big" if big else ""}"><div class="bb-logo-bg" style="background:{bg}">'
                f'{b.img(item["file"], cls="bb-logo-img", alt=item["label"])}</div>'
                f'<figcaption><b>{esc(item["label"])}</b><span>{esc(item["use"])}</span>'
                f'<a class="bb-dl" download="{esc(item["file"])}" href="{b.data_uri(item["file"])}">{esc(b.t("download","Download"))} SVG</a></figcaption></figure>')

    concept = (f'<div class="bb-two"><div class="bb-logo-hero bb-surface lv-big">{b.img(L["primary"]["light"], 110, cls="bb-fit")}</div>'
               f'<p class="bb-lead">{esc(L.get("idea", ""))}</p></div>')
    ratio = L.get("clearspace_ratio", .27)
    cs = (f'<div class="bb-clear"><div class="bb-clear-box" style="padding:{ratio*110:.0f}px">'
          f'<span class="only-light">{b.img(L["primary"]["light"], 110)}</span><span class="only-dark">{b.img(L["primary"]["dark"], 110)}</span></div>'
          f'<p>{esc(L.get("clearspace", ""))}</p></div>')
    mins = "".join(f'<figure class="bb-min">{b.img(m["file"], m["px"])}<figcaption>{esc(m["label"])}</figcaption></figure>' for m in L.get("minsize", []))
    donts = "".join(f'<figure class="bb-dont"><div class="bb-dont-bg {d["effect"]}">{b.img(L["primary"]["light"], 46, cls="fx-"+d["effect"])}</div>'
                    f'<figcaption><span class="bb-x">✕</span>{esc(d["label"])}</figcaption></figure>' for d in L.get("donts", []))
    return [x for x in [
        {"id": "logo-concept", "title": b.L("logo_concept"), "html": concept},
        {"id": "logo-lockups", "title": b.L("logo_lockups"), "html": f'<div class="bb-grid2">{"".join(tile(x, True) for x in L.get("lockups", []))}</div>'} if L.get("lockups") else None,
        {"id": "logo-marks", "title": b.L("logo_marks"), "html": f'<div class="bb-grid3">{"".join(tile(x) for x in L.get("marks", []))}</div>'} if L.get("marks") else None,
        {"id": "logo-space", "title": b.L("logo_space"), "html": f'<div class="bb-two">{cs}<div class="bb-mins">{mins}</div></div>'} if L.get("clearspace") else None,
        {"id": "logo-misuse", "title": b.L("logo_misuse"), "html": f'<div class="bb-grid3">{donts}</div>'} if donts else None,
    ] if x]


def sec_color(b):
    out = []
    for g in b.d["colors"]["groups"]:
        cards = ""
        for c in g["items"]:
            fg = "#FFFFFF" if contrast(c["hex"], "#FFFFFF") > contrast(c["hex"], "#111111") else "#111111"
            ok = c.get("oklch")
            okt = f"oklch({ok[0]} {ok[1]} {ok[2]})" if ok else ""
            cards += (f'<div class="bb-sw bb-surface lv-mid"><button class="bb-sw-chip" type="button" data-copy="{c["hex"]}" '
                      f'style="background:{c["hex"]};color:{fg}">{c["hex"]}</button>'
                      f'<div class="bb-sw-txt"><b>{esc(c["name"])}</b><code>{esc(c["token"])}</code><code>{okt}</code>'
                      f'<p>{esc(c["role"])}</p></div></div>')
        out.append({"id": "color-" + re.sub(r"\W+", "-", g["name"].lower()).strip("-"), "title": g["name"], "html": f'<div class="bb-grid4">{cards}</div>'})
    th = b.d["theme"]
    shell = ""
    for mode in ("light", "dark"):
        bg, fg = b.c(th[mode]["bg"]), b.c(th[mode]["fg"])
        shell += (f'<div class="bb-shell" style="background:{bg};color:{fg};--line:{fg}"><p class="bb-eyebrow" style="color:{fg};opacity:.7">'
                  f'{esc(b.L("shell_light") if mode=="light" else b.L("shell_dark"))}</p>'
                  f'<div class="bb-surface lv-mid bb-shell-card"><b>{esc(b.L("shell_card"))}</b><span>{esc(b.L("shell_card_note"))}</span></div>'
                  f'<span class="bb-btn lv-pill" style="--b:{b.c("primary")};--bf:{b.c("primary_fg")};--line:{fg}">{esc(b.d.get("components", {}).get("button", {}).get("label", "Button"))}</span></div>')
    out.append({"id": "color-shell", "title": b.L("color_shell"), "html": f'<div class="bb-grid2">{shell}</div>'})
    rows = ""
    for p in b.d["colors"].get("contrast", []):
        fg, bg = b.c(p["fg"]), b.c(p["bg"])
        r = contrast(fg, bg)
        verdict, cls = (b.L("verdict_aa"), "ok") if r >= 4.5 else ((b.L("verdict_large"), "mid") if r >= 3 else (b.L("verdict_fail"), "bad"))
        rows += (f'<tr><td><span class="bb-pair" style="background:{bg};color:{fg}">Aa</span></td><td>{esc(p["fg"])} / {esc(p["bg"])}</td>'
                 f'<td>{esc(p["use"])}</td><td class="num">{r:.1f}:1</td><td><span class="bb-verdict {cls}">{verdict}</span></td></tr>')
    if rows: out.append({"id": "color-contrast", "title": b.L("color_contrast"), "html": f'<div class="bb-surface lv-mid bb-tablewrap"><table class="bb-table"><tbody>{rows}</tbody></table></div>'})
    if b.d["colors"].get("rules"):
        out.append({"id": "color-rules", "title": b.L("rules"), "html": "<ul class='bb-rules'>" + "".join(f"<li>{esc(r)}</li>" for r in b.d["colors"]["rules"]) + "</ul>"})
    return out


def sec_type(b):
    f = b.d["fonts"]
    fam = "".join(
        f'<div class="bb-surface lv-mid bb-font"><p class="bb-eyebrow">{k}</p>'
        f'<div class="bb-aa" style="font-family:var(--f-{k})">Aa</div><b>{esc(f[k]["family"])}</b><span>{esc(f[k]["use"])}</span>'
        f'<p style="font-family:var(--f-{k})">{esc(f[k]["sample"])}</p></div>' for k in ("display", "body", "mono"))
    rows = ""
    for s in b.d.get("type_scale", []):
        st = f'font-family:var(--f-{s["font"]});font-size:{s["size"]};font-weight:{s["weight"]};'
        if s.get("upper"):
            st += "text-transform:uppercase;letter-spacing:.08em;"
        if s.get("tabular"):
            st += "font-variant-numeric:tabular-nums;"
        rows += (f'<div class="bb-scale-row"><div class="bb-scale-meta"><b>{esc(s["role"])}</b><code>{s["size"]} · {s["weight"]} · {s["font"]}</code>'
                 f'<span>{esc(s["note"])}</span></div><div class="bb-scale-sample" style="{st}">{esc(s["sample"])}</div></div>')
    return [
        {"id": "type-families", "title": b.L("type_families"), "html": f'<div class="bb-grid3">{fam}</div>'},
        {"id": "type-scale", "title": b.L("type_scale"), "html": f'<div class="bb-surface lv-mid bb-scale">{rows}</div>'} if rows else None,
        {"id": "type-rules", "title": b.L("rules"), "html": "<ul class='bb-rules'>" + "".join(f"<li>{esc(r)}</li>" for r in b.d["type_rules"]) + "</ul>"} if b.d.get("type_rules") else None,
    ]


def sec_shape(b):
    sh = b.d["shape"]
    rad = "".join(f'<div class="bb-rad"><div class="bb-rad-box" style="border-radius:{min(r["px"], 60)}px"></div>'
                  f'<b>{esc(r["name"])} · {r["px"] if r["px"] < 999 else "full"}</b><span>{esc(r["use"])}</span></div>' for r in sh.get("radius", []))
    ev = sh["elevation"]
    lv = "".join(f'<button class="bb-elev bb-surface {l["name"]}" type="button"><code>.{l["name"]}</code>'
                 f'<span>r{l["radius"] if l["radius"] < 999 else "∞"} · border {l["border"]} · offset {l["offset"]}</span><small>{esc(l["use"])}</small></button>'
                 for l in ev["levels"])
    never = "".join(f"<li>{esc(n)}</li>" for n in ev.get("never", []))
    css = "\n".join(b.level_css("." + l["name"], l).replace("{", " { ").replace(";", "; ").replace("}", " }")
                    for l in ev["levels"])
    blob = "" if not sh.get("blob") else (f'<div class="bb-two"><div class="bb-blobs"><span class="bb-blob" style="border-radius:{sh["blob"]};background:{b.c("secondary")}">R</span>'
            f'<span class="bb-blob" style="border-radius:{sh["blob"]};background:{b.c("accent")}">★</span>'
            f'<span class="bb-blob" style="border-radius:{sh["blob"]};background:{b.c("primary")};color:{b.c("primary_fg")}">C</span></div>'
            f'<div><code class="bb-inline">border-radius: {esc(sh["blob"])}</code><p>{esc(sh.get("blob_use", ""))}</p></div></div>')
    return [
        {"id": "shape-radius", "title": b.L("shape_radius"), "html": f'<div class="bb-rads">{rad}</div>'} if rad else None,
        {"id": "shape-elevation", "title": b.L("shape_elevation"), "html":
            f'<p class="bb-lead">{esc(b.L("elevation_lead"))}</p>'
            f'<div class="bb-grid3">{lv}</div>{b.code(css)}'
            + (f'<p class="bb-eyebrow" style="margin-top:18px">{esc(b.L("never"))}</p><ul class="bb-rules bad">{never}</ul>' if never else "")},
        {"id": "shape-blob", "title": b.L("shape_blob"), "html": blob} if blob else None,
    ]


# ------------------------------------------------------------------ motion
MOTION_DEFAULTS = {
    "durations": {"fast": 150, "base": 240, "slow": 420},
    "easings": {"standard": [0.2, 0, 0, 1], "enter": [0, 0, 0.2, 1], "exit": [0.4, 0, 1, 1], "overshoot": [0.34, 1.56, 0.64, 1]},
}
MOTION_EXAMPLES = [
    {"preset": "fade-up", "duration": "base", "easing": "enter"},
    {"preset": "pop", "duration": "base", "easing": "overshoot"},
    {"preset": "slide-in", "duration": "slow", "easing": "standard"},
    {"preset": "stagger", "duration": "base", "easing": "enter", "step": 60},
    {"preset": "press", "duration": "fast", "easing": "standard"},
    {"preset": "exit", "duration": "fast", "easing": "exit"},
    {"preset": "shimmer", "duration": "slow", "easing": "linear"},
]
# start state of each preset (the end state is "no transform, full opacity")
MX_FROM = {"fade-up": "opacity:0;transform:translateY(18px)", "pop": "opacity:0;transform:scale(.6)",
           "slide-in": "opacity:0;transform:translateX(110%)", "stagger": "opacity:0;transform:translateY(14px)",
           "exit": "opacity:0;transform:scale(.92) translateY(6px)"}
MX_CYCLE = 2400   # ms per demo loop: play, hold, reset


def motion_spec(b):
    """Durations (ms) and easings (cubic-bezier lists) from brand.json, falling back to sensible defaults."""
    mo = b.d.get("motion", {})
    dur = {**MOTION_DEFAULTS["durations"], **mo.get("durations", {})}
    eas = {**MOTION_DEFAULTS["easings"], **mo.get("easings", {})}
    return dur, eas


def _bez(e):
    return "linear" if e == "linear" else "cubic-bezier({})".format(", ".join(f"{v:g}" for v in e))


def _ease_svg(e):
    """Small chart of a cubic-bezier curve (y may overshoot)."""
    x1, y1, x2, y2 = e
    lo, hi = min(0, y1, y2), max(1, y1, y2)
    H = 100 * (hi - lo)
    Y = lambda y: 10 + (hi - y) * 100
    return (f'<svg class="bb-ease-svg" viewBox="0 0 120 {H + 20:.0f}" aria-hidden="true">'
            f'<path d="M10 {Y(0):.1f}H110M10 {Y(1):.1f}H110" class="bb-ease-grid"/>'
            f'<path d="M10 {Y(0):.1f}L{10 + x1 * 100:.1f} {Y(y1):.1f}M110 {Y(1):.1f}L{10 + x2 * 100:.1f} {Y(y2):.1f}" class="bb-ease-handle"/>'
            f'<path d="M10 {Y(0):.1f}C{10 + x1 * 100:.1f} {Y(y1):.1f} {10 + x2 * 100:.1f} {Y(y2):.1f} 110 {Y(1):.1f}" class="bb-ease-curve"/></svg>')


def _loop_kf(name, frm, d, ease, kind="in", extra=0):
    """Looping keyframes so a one-shot animation replays with a pause. Percentages come from the real duration."""
    pct = lambda ms: f"{min(100, ms / MX_CYCLE * 100):.2f}%"
    tf = f"animation-timing-function:{_bez(ease)}"
    if kind == "in":
        return (f"@keyframes {name}{{0%{{{frm};{tf}}}{pct(d)}{{opacity:1;transform:none}}"
                f"86%{{opacity:1;transform:none;animation-timing-function:linear}}94%,100%{{{frm}}}}}")
    # out: visible, leave, stay gone, fade back in
    return (f"@keyframes {name}{{0%,{pct(500)}{{opacity:1;transform:none;{tf}}}{pct(500 + d)}{{{frm}}}"
            f"80%{{{frm};animation-timing-function:linear}}92%,100%{{opacity:1;transform:none}}}}")


def sec_motion(b):
    mo = b.d.get("motion", {})
    dur, eas = motion_spec(b)
    out, css = [], []
    if mo.get("principles"):
        pr = "".join(f'<div class="bb-surface lv-mid bb-pr"><b>{esc(p["title"])}</b><p>{esc(p["body"])}</p></div>' for p in mo["principles"])
        out.append({"id": "motion-principles", "title": b.L("motion_principles"), "html": f'<div class="bb-grid2">{pr}</div>'})

    # easing: curve + a dot travelling with that curve
    cards = []
    for i, (name, e) in enumerate(eas.items()):
        kf = f"bbe{i}"
        css.append(f"@keyframes {kf}{{0%{{left:0;animation-timing-function:{_bez(e)}}}{dur['slow'] / 1600 * 100:.1f}%,80%{{left:calc(100% - 14px)}}90%,100%{{left:0;opacity:0}}}}"
                   f".bb-ease-{i} .bb-ease-dot{{animation:{kf} 1600ms infinite both}}")
        cards.append(f'<div class="bb-surface lv-mid bb-ease bb-ease-{i}">{_ease_svg(e)}<div class="bb-ease-track"><span class="bb-ease-dot"></span></div>'
                     f'<b>{esc(name)}</b><code class="bb-inline">{_bez(e)}</code></div>')
    ease_css = ":root{\n" + "\n".join(f"  --ease-{k}: {_bez(v)};" for k, v in eas.items()) + "\n" + \
               "\n".join(f"  --duration-{k}: {v}ms;" for k, v in dur.items()) + "\n}"
    out.append({"id": "motion-easing", "title": b.L("motion_easing"), "html": f'<div class="bb-grid4">{"".join(cards)}</div>' + b.code(ease_css)})

    # durations
    mx = max(dur.values())
    rows = []
    for i, (name, ms) in enumerate(dur.items()):
        kf = f"bbd{i}"
        css.append(f"@keyframes {kf}{{0%{{width:0;animation-timing-function:{_bez(eas.get('standard', [0.2, 0, 0, 1]))}}}"
                   f"{ms / 1600 * 100:.1f}%,80%{{width:100%}}92%,100%{{width:0}}}}.bb-dur-{i} i{{animation:{kf} 1600ms infinite both}}")
        rows.append(f'<div class="bb-dur bb-dur-{i}"><b>{esc(name)}</b><span class="bb-mono">{ms} ms</span>'
                    f'<div class="bb-dur-track" style="width:{max(14, ms / mx * 100):.0f}%"><i></i></div></div>')
    out.append({"id": "motion-duration", "title": b.L("motion_duration"), "html": f'<div class="bb-surface lv-mid bb-durs">{"".join(rows)}</div>'})

    # live examples built from the brand's own surfaces, buttons and elevation
    press = b.d["shape"].get("elevation", {}).get("press", {})
    tr = press.get("translate", 2)
    line = lambda w: f'<span class="bb-mx-line" style="width:{w}%"></span>'
    card = lambda: f'<div class="bb-surface lv-mid bb-mx-card"><span class="bb-mx-dot"></span><div>{line(80)}{line(55)}</div></div>'
    exs = mo.get("examples") or MOTION_EXAMPLES
    demos = []
    for i, ex in enumerate(exs):
        pre = ex["preset"]
        d = dur.get(ex.get("duration", "base"), ex.get("duration")) if not isinstance(ex.get("duration"), int) else ex["duration"]
        en = ex.get("easing", "standard")
        e = "linear" if en == "linear" else eas.get(en, MOTION_DEFAULTS["easings"]["standard"])
        k = f"bbx{i}"
        name = ex.get("name") or b.t(f"mx_{pre}", pre)
        use = ex.get("use") or b.t(f"mx_{pre}_use", "")
        if pre == "stagger":
            step = ex.get("step", 60)
            css.append(_loop_kf(k, MX_FROM["stagger"], d, e) + "".join(
                f".bb-mx-{i} .bb-mx-card:nth-child({n + 1}){{animation:{k} {MX_CYCLE}ms infinite both;animation-delay:{n * step}ms}}" for n in range(4)))
            stage = '<div class="bb-mx-list">' + card() * 4 + "</div>"
            snippet = (f"@keyframes fade-up {{ from {{ {MX_FROM['stagger'].replace(';', '; ')}; }} }}\n"
                       f".list > * {{\n  animation: fade-up var(--duration-{ex.get('duration', 'base')}) var(--ease-{en}) both;\n"
                       f"  animation-delay: calc(var(--i) * {step}ms);  /* set --i on each child */\n}}")
        elif pre == "press":
            css.append(f"@keyframes {k}{{0%,30%{{transform:none;animation-timing-function:{_bez(e)}}}{30 + d / MX_CYCLE * 100:.1f}%,52%{{transform:translate({tr}px,{tr}px);box-shadow:{press.get('offset', 1)}px {press.get('offset', 1)}px 0 0 var(--line);animation-timing-function:{_bez(e)}}}"
                       f"{52 + d / MX_CYCLE * 100:.1f}%,100%{{transform:none}}}}.bb-mx-{i} .bb-btn{{animation:{k} {MX_CYCLE}ms infinite both}}")
            stage = f'<button type="button" class="bb-btn lv-pill" style="--b:{b.c("primary")};--bf:{b.c("primary_fg")}">{esc(b.meta.get("name", "Button"))}</button>'
            snippet = (f".btn {{ transition: transform var(--duration-{ex.get('duration', 'fast')}) var(--ease-{en}),\n"
                       f"                   box-shadow var(--duration-{ex.get('duration', 'fast')}) var(--ease-{en}); }}\n"
                       f".btn:active {{ transform: translate({tr}px, {tr}px); }}")
        elif pre == "shimmer":
            css.append(f"@keyframes {k}{{from{{background-position:150% 0}}to{{background-position:-50% 0}}}}"
                       f".bb-mx-{i} .bb-mx-line{{background:linear-gradient(90deg,var(--sk) 30%,var(--sk2) 50%,var(--sk) 70%) 0 0/200% 100%;animation:{k} {max(1200, d * 3)}ms linear infinite}}")
            stage = f'<div class="bb-surface lv-mid bb-mx-card bb-mx-sk"><span class="bb-mx-dot"></span><div>{line(80)}{line(60)}{line(40)}</div></div>'
            snippet = (f"@keyframes shimmer {{ from {{ background-position: 150% 0; }} to {{ background-position: -50% 0; }} }}\n"
                       f".skeleton {{\n  background: linear-gradient(90deg, var(--muted) 30%, var(--card) 50%, var(--muted) 70%) 0 0 / 200% 100%;\n"
                       f"  animation: shimmer {max(1200, d * 3)}ms linear infinite;\n}}")
        else:
            kind = "out" if pre == "exit" else "in"
            css.append(_loop_kf(k, MX_FROM[pre], d, e, kind) + f".bb-mx-{i} .bb-mx-target{{animation:{k} {MX_CYCLE}ms infinite both}}")
            if pre == "pop":
                inner = f'<span class="bb-mx-badge" style="background:{b.c("primary")};color:{b.c("primary_fg")}">✓</span>'
            else:
                inner = card()
            stage = f'<div class="bb-mx-target">{inner}</div>'
            word = "to" if kind == "out" else "from"
            snippet = (f"@keyframes {pre} {{ {word} {{ {MX_FROM[pre].replace(';', '; ')}; }} }}\n"
                       f".{pre} {{ animation: {pre} var(--duration-{ex.get('duration', 'base')}) var(--ease-{en}) both; }}")
        meta = f'{d} ms · {en}'
        demos.append(f'<div class="bb-surface lv-mid bb-mx bb-mx-{i}"><div class="bb-mx-stage{" bb-mx-clip" if pre == "slide-in" else ""}">{stage}</div>'
                     f'<div class="bb-mx-txt"><b>{esc(name)}</b><span class="bb-mono bb-muted">{esc(meta)}</span>'
                     f'{f"<p class=\"bb-muted\">{esc(use)}</p>" if use else ""}</div>{b.code(snippet)}</div>')
    reduce = "@media (prefers-reduced-motion: reduce) {\n  *, *::before, *::after { animation: none !important; transition: none !important; }\n}"
    out.append({"id": "motion-examples", "title": b.L("motion_examples"),
                "html": f'<style>{"".join(css)}</style><div class="bb-grid3">{"".join(demos)}</div>'
                        f'<p class="bb-note">{esc(b.t("motion_reduced", ""))}</p>' + b.code(reduce)})

    if mo.get("tokens"):
        tok = "".join(f'<div class="bb-tok"><code class="bb-inline">{esc(t["name"])}</code><pre>{esc(t["code"])}</pre></div>' for t in mo["tokens"])
        out.append({"id": "motion-tokens", "title": b.L("motion_tokens"), "html": f'<div class="bb-surface lv-mid bb-toks">{tok}</div>'})
    if mo.get("never"):
        nev = "".join(f"<li>{esc(n)}</li>" for n in mo["never"])
        out.append({"id": "motion-never", "title": b.L("motion_never"), "html": f'<ul class="bb-rules bad">{nev}</ul>'})
    return out


def sec_voice(b):
    v = b.d["voice"]
    tr = "".join(f'<div class="bb-surface lv-mid bb-pr"><b>{esc(t["trait"])}</b><p>{esc(t["body"])}</p></div>' for t in v["traits"])
    terms = "".join(f'<tr><td>{esc(t["concept"])}</td><td><b>{esc(t["use"])}</b></td><td class="bb-avoid">{esc(t["avoid"])}</td></tr>' for t in v["terms"])
    pairs = "".join(f'<div class="bb-pair-do"><span class="bb-verdict ok">{esc(b.t("do","Do"))}</span><p>{esc(p["do"])}</p></div>'
                    f'<div class="bb-pair-do"><span class="bb-verdict bad">{esc(b.t("dont","Don\'t"))}</span><p class="bb-strike">{esc(p["dont"])}</p></div>' for p in v["pairs"])
    mc = "".join(f'<div class="bb-surface lv-mid bb-mc"><p class="bb-eyebrow">{esc(m["type"])}</p><p>{esc(m["text"])}</p></div>' for m in v["microcopy"])
    return [
        {"id": "voice-traits", "title": b.L("voice_traits"), "html": f'<div class="bb-grid3">{tr}</div>'},
        {"id": "voice-terms", "title": b.L("voice_terms"), "html":
            f'<div class="bb-surface lv-mid bb-tablewrap"><table class="bb-table"><thead><tr><th>{esc(b.L("th_concept"))}</th><th>{esc(b.L("th_use"))}</th><th>{esc(b.L("th_avoid"))}</th></tr></thead><tbody>{terms}</tbody></table></div>'},
        {"id": "voice-examples", "title": b.L("voice_examples"), "html": f'<div class="bb-pairs">{pairs}</div>'},
        {"id": "voice-microcopy", "title": b.L("voice_microcopy"), "html": f'<div class="bb-grid4">{mc}</div>'
            + (f'<p class="bb-note">{esc(v["gamified"])}</p>' if v.get("gamified") else "")},
    ]


def sec_components(b):
    """Each component renders only when its data exists in brand.json -> components."""
    C = b.d["components"]
    big, mid, pill = "lv-big", "lv-mid", "lv-pill"
    loader = b.ext["hooks"].get("inline_loader") or '<span class="bb-spin"></span>'
    demo = lambda inner, cls="": f'<div class="bb-demo {cls}">{inner}</div>'
    blob = b.d["shape"].get("blob", "50%")
    btn = lambda label, bg, fg: f'<button type="button" class="bb-btn {pill}" style="--b:{b.c(bg)};--bf:{b.c(fg)}">{esc(label)}</button>'
    out = []

    if "button" in C:
        bt = C["button"]
        states = [(b.L("st_default"), ""), (b.L("st_hover"), "is-hover"), (b.L("st_press"), "is-press"),
                  (b.L("st_loading"), "loading"), (b.L("st_disabled"), "disabled")]
        head = "".join(f"<th>{s}</th>" for s, _ in states)
        rows = ""
        for v in bt["variants"]:
            cells = ""
            for _, cls in states:
                lab = esc(v.get("label", bt["label"]))
                inner, attr = (f"{loader}{lab}…", " disabled") if cls == "loading" else ((lab, " disabled") if cls == "disabled" else (lab, ""))
                cells += (f'<td><button type="button" class="bb-btn {pill} {cls}"{attr} '
                          f'style="--b:{b.c(v["bg"])};--bf:{b.c(v["fg"])}">{inner}</button></td>')
            rows += f'<tr><th>{esc(v["name"])}{"<small>"+esc(v["note"])+"</small>" if v.get("note") else ""}</th>{cells}</tr>'
        out.append({"id": "c-button", "title": b.L("c_button"), "html": demo(
            f'<div class="bb-scroll"><table class="bb-matrix"><thead><tr><th></th>{head}</tr></thead><tbody>{rows}</tbody></table></div>') + b.code(bt.get("code"))})

    if "input" in C:
        i = C["input"]
        def field(state):
            err = state == "error"
            pre = f'<span class="bb-prefix">{esc(i["prefix"])}</span>' if i.get("prefix") else ""
            return (f'<label class="bb-field"><span class="bb-eyebrow">{esc(i["label"])}</span>'
                    f'<span class="bb-input {mid} {state}">{pre}'
                    f'<input value="{esc(i.get("value", "") if state != "empty" else "")}" placeholder="{esc(i.get("placeholder", ""))}"></span>'
                    f'<small class="{"bb-err" if err else ""}">{esc(i.get("error", "") if err else i.get("helper", ""))}</small></label>')
        out.append({"id": "c-input", "title": b.L("c_input"), "html": demo('<div class="bb-grid3 tight">' + field("empty") + field("focus") + field("error") + '</div>') + b.code(i.get("code"))})

    if "statuses" in C or "achievement" in C:
        st = "".join(f'<span class="bb-status {pill}"><i style="background:{b.c(s["color"])}"></i>{esc(s["label"])}</span>' for s in C.get("statuses", []))
        ach = (f'<div class="bb-row" style="margin-top:16px"><span class="bb-ach {mid}" style="background:{b.c("achievement")}">{esc(C["achievement"]["label"])}</span></div>'
               if "achievement" in C else "")
        out.append({"id": "c-badge", "title": b.L("c_badge"), "html": demo(f'<div class="bb-row">{st}</div>{ach}')
                    + b.code((C.get("status_code", "") + "\n\n" + C.get("achievement", {}).get("code", "")).strip())})

    if "card" in C or "wallet" in C:
        html_ = ""
        if "card" in C:
            cd = C["card"]
            html_ += (f'<div class="bb-surface {big} bb-card"><p class="bb-eyebrow">{esc(cd.get("eyebrow", ""))}</p><h4>{esc(cd["title"])}</h4><p>{esc(cd.get("body", ""))}</p>'
                      + (btn(cd["action"], "secondary", "secondary_fg") if cd.get("action") else "") + '</div>')
        if "wallet" in C:
            w = C["wallet"]
            html_ += (f'<div class="bb-surface {big} bb-card bb-wallet"><p class="bb-eyebrow">{esc(w.get("eyebrow", ""))}</p>'
                      f'<p class="bb-amount">{esc(w["amount"])}</p><p class="bb-muted">{esc(w.get("sub", ""))}</p>'
                      + (btn(w["action"], "primary", "primary_fg") if w.get("action") else "") + '</div>')
        out.append({"id": "c-card", "title": b.L("c_card"), "html": demo(f'<div class="bb-grid2 tight">{html_}</div>')
                    + b.code(C.get("wallet", {}).get("code") or C.get("card", {}).get("code"))})

    if "stats" in C:
        stats = "".join(f'<div class="bb-surface {mid} bb-stat"><p class="bb-eyebrow">{esc(s["eyebrow"])}</p><p class="bb-amount sm">{esc(s["value"])}</p>'
                        f'<p class="bb-muted">{esc(s.get("delta", ""))}</p></div>' for s in C["stats"])
        skel = "".join(f'<div class="bb-surface {mid} bb-stat bb-skel"><i style="width:50%"></i><i style="width:75%;height:22px"></i><i style="width:35%"></i></div>' for _ in C["stats"])
        out.append({"id": "c-stat", "title": b.L("c_stat"), "html": demo(f'<div class="bb-grid3 tight">{stats}</div><div class="bb-grid3 tight" style="margin-top:16px">{skel}</div>')})

    if "avatar" in C:
        av = "".join(f'<span class="bb-av-wrap"><span class="bb-avatar" style="border-radius:{blob};background:{b.c("pending") if a.get("anon") else b.c("secondary")}">'
                     f'{esc(a["initial"])}</span><small>{esc(a["name"])}</small></span>' for a in C["avatar"])
        out.append({"id": "c-avatar", "title": b.L("c_avatar"), "html": demo(f'<div class="bb-row">{av}</div>') + b.code(C.get("avatar_code"))})

    if "toast" in C:
        kinds = {k: b.c(k) for k in ("success", "destructive", "achievement") if k in b.d["theme"]}
        to = "".join(f'<div class="bb-surface {mid} bb-toast"><span class="bb-toast-dot" style="border-radius:{blob};background:{kinds.get(t["kind"], b.c("primary"))}"></span>'
                     f'<div><b>{esc(t["title"])}</b><p>{esc(t.get("body", ""))}</p></div></div>' for t in C["toast"])
        out.append({"id": "c-toast", "title": b.L("c_toast"), "html": demo(f'<div class="bb-grid3 tight">{to}</div>')})

    if "empty" in C:
        e = C["empty"]
        art = b.ext["hooks"].get("empty_art") or b.img(b.d["logo"]["marks"][0]["file"], 48)
        out.append({"id": "c-empty", "title": b.L("c_empty"), "html": demo(
            f'<div class="bb-surface {big} bb-empty"><div class="bb-empty-art">{art}</div><h4>{esc(e["title"])}</h4><p class="bb-muted">{esc(e.get("body", ""))}</p>'
            + (btn(e["action"], "primary", "primary_fg") if e.get("action") else "") + '</div>')})

    if "table" in C:
        tb = C["table"]
        stmap = {s["key"]: s for s in C.get("statuses", [])}
        trs = ""
        for r in tb["rows"]:
            s = stmap.get(r.get("status"))
            badge = f'<span class="bb-status {pill} sm"><i style="background:{b.c(s["color"])}"></i>{esc(s["label"])}</span>' if s else ""
            trs += (f'<tr><td><span class="bb-cell-av"><span class="bb-avatar sm" style="border-radius:{blob};background:{b.c("pending") if r.get("anon") else b.c("secondary")}">{esc(r.get("initial", r["name"][:1]))}</span>{esc(r["name"])}</span></td>'
                    f'<td class="bb-muted">{esc(r.get("msg", ""))}</td><td>{badge}</td><td class="num bb-mono">{esc(r.get("amount", ""))}</td></tr>')
        ths = "".join(f'<th{" class=num" if k == len(tb["columns"])-1 else ""}>{esc(c)}</th>' for k, c in enumerate(tb["columns"]))
        tabs = ('<div class="bb-tabs">' + "".join(f'<button type="button" class="bb-tab{" on" if k == 0 else ""}">{esc(t)}</button>' for k, t in enumerate(C["tabs"])) + '</div>') if C.get("tabs") else ""
        out.append({"id": "c-table", "title": b.L("c_table"), "html": demo(
            f'{tabs}<div class="bb-surface {mid} bb-tablewrap" style="margin-top:14px"><table class="bb-table"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>')})

    if "dialog" in C:
        dg = C["dialog"]
        out.append({"id": "c-dialog", "title": b.L("c_dialog"), "html": demo(
            f'<div class="bb-dialog-backdrop"><div class="bb-surface {big} bb-dialog"><h4>{esc(dg["title"])}</h4><p>{esc(dg.get("body", ""))}</p>'
            f'<div class="bb-row end">{btn(dg["cancel"], "card", "card_fg")}{btn(dg["confirm"], "primary", "primary_fg")}</div></div></div>')})
    return out


CORE = [
    ("overview", "s_overview", "", sec_overview),
    ("logo", "s_logo", "l_logo", sec_logo),
    ("color", "s_color", "l_color", sec_color),
    ("type", "s_type", "l_type", sec_type),
    ("shape", "s_shape", "l_shape", sec_shape),
    ("motion", "s_motion", "l_motion", sec_motion),
    ("voice", "s_voice", "l_voice", sec_voice),
    ("components", "s_components", "l_components", sec_components),
]

# English defaults; a brand overrides any of these in brand.json -> meta.labels
DEFAULT_LABELS = {
    "s_overview": "Overview", "s_logo": "Logo", "s_color": "Colour", "s_type": "Typography", "s_shape": "Shape & elevation",
    "s_motion": "Motion", "s_voice": "Voice & copy", "s_components": "Components",
    "l_logo": "One idea, a few forms. Use the right file for the size and background.",
    "l_color": "Colour tokens and how to use them.", "l_type": "Three families, each with a job.",
    "l_shape": "Intentional radius, firm borders, crisp shadows.", "l_motion": "Movement with a reason.",
    "l_voice": "How this brand talks.", "l_components": "Ready-to-use UI blocks, all built from the tokens above.",
    "logo_concept": "Concept", "logo_lockups": "Lockups", "logo_marks": "Marks & variants", "logo_space": "Clear space & size",
    "logo_misuse": "Misuse", "color_shell": "Shell vs surface", "color_contrast": "Contrast", "rules": "Rules",
    "shell_light": "Light shell", "shell_dark": "Dark shell", "shell_card": "Card", "shell_card_note": "always the surface colour",
    "verdict_aa": "AA", "verdict_large": "AA large", "verdict_fail": "Fail",
    "type_families": "Typefaces", "type_scale": "Scale",
    "shape_radius": "Radius", "shape_elevation": "Elevation", "shape_blob": "Organic shape",
    "elevation_lead": "Hover or press a level to feel the interaction.", "never": "Never",
    "motion_principles": "Principles", "motion_tokens": "Tokens", "motion_never": "Never animated",
    "motion_easing": "Easing", "motion_duration": "Duration", "motion_examples": "Examples",
    "motion_reduced": "Every example stops when the viewer asks for reduced motion (snippet below).",
    "mx_fade-up": "Fade up", "mx_fade-up_use": "Sections and cards entering",
    "mx_pop": "Pop in", "mx_pop_use": "Badges, confirmations, small rewards",
    "mx_slide-in": "Slide in", "mx_slide-in_use": "Toasts and side panels",
    "mx_stagger": "Stagger", "mx_stagger_use": "Lists and grids loading in",
    "mx_press": "Press", "mx_press_use": "Buttons and tappable cards",
    "mx_exit": "Exit", "mx_exit_use": "Dismissing and closing",
    "mx_shimmer": "Skeleton", "mx_shimmer_use": "Content still loading",
    "voice_traits": "Personality", "voice_terms": "Terminology", "voice_examples": "Examples", "voice_microcopy": "Microcopy",
    "th_concept": "Concept", "th_use": "Use", "th_avoid": "Avoid",
    "st_default": "Default", "st_hover": "Hover", "st_press": "Pressed", "st_loading": "Loading", "st_disabled": "Disabled",
    "c_button": "Button", "c_input": "Input", "c_badge": "Badge", "c_card": "Cards", "c_stat": "Stats & skeleton",
    "c_avatar": "Avatar", "c_toast": "Toast", "c_empty": "Empty state", "c_table": "Tabs & table", "c_dialog": "Dialog",
    "theme_light": "Light", "theme_dark": "Dark", "code": "Code", "copy": "Copy", "copied": "Copied", "download": "Download",
    "do": "Do", "dont": "Don't",
}


# ------------------------------------------------------------------ page
BASE_CSS = r"""
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:16px}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 var(--f-body);-webkit-font-smoothing:antialiased;transition:background .2s,color .2s}
h1,h2,h3,h4{font-family:var(--f-display);font-weight:600;margin:0;text-wrap:balance}
p{margin:6px 0}
code,pre{font-family:var(--f-mono)}
img{display:block;max-width:100%}
.bb-fit{width:auto;max-width:100%;height:auto;max-height:110px}
.bb-main{min-width:0}
.bb-clear-box{max-width:100%}.bb-clear-box img{max-width:100%;height:auto}
.only-dark{display:none} body.dark .only-dark{display:inline} body.dark .only-light{display:none}
.bb-eyebrow{font:600 .68rem var(--f-mono);text-transform:uppercase;letter-spacing:.08em;opacity:.75;margin:0 0 4px}
.bb-muted{color:var(--muted)} .bb-surface .bb-muted{color:var(--card-muted)}
.bb-mono,.num{font-family:var(--f-mono);font-variant-numeric:tabular-nums}
.num{text-align:right}

/* layout */
.bb-layout{display:grid;grid-template-columns:250px minmax(0,1fr);min-height:100vh}
.bb-side{position:sticky;top:0;height:100vh;overflow:auto;padding:22px 14px 22px 18px;border-right:2px solid var(--line)}
.bb-brand{display:flex;flex-direction:column;gap:6px;margin-bottom:18px;color:inherit;text-decoration:none}
.bb-brand img{height:30px;width:auto}
.bb-brand small{font:600 .62rem var(--f-mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.bb-nav{list-style:none;margin:0;padding:0}
.bb-nav>li{margin:2px 0}
.bb-nav a{color:inherit;text-decoration:none;display:block;border-radius:10px}
.bb-nav .sec{font:600 15px var(--f-display);padding:6px 10px}
.bb-nav .sec .n{font:600 11px var(--f-mono);color:var(--muted);margin-right:8px}
.bb-nav .subs{list-style:none;margin:0 0 6px;padding:0 0 0 30px;display:none}
.bb-nav li.open .subs{display:block}
.bb-nav .sub{font-size:13px;padding:3px 10px;color:var(--muted)}
.bb-nav a:hover{background:color-mix(in srgb,var(--fg) 8%,transparent)}
.bb-nav a.on.sec{background:var(--primary);color:var(--primary-fg)}
.bb-nav a.on.sec .n{color:inherit}
.bb-nav a.on.sub{color:var(--fg);font-weight:600}
.bb-theme{margin-top:18px;width:100%}
.bb-main{padding:36px 44px 140px;max-width:1100px;width:100%}
body.bb-only .bb-layout{grid-template-columns:minmax(0,1fr)} body.bb-only .bb-side{display:none} body.bb-only .bb-main{padding:8px 32px 32px}
.bb-section{padding-top:34px;margin-top:20px}
.bb-section>header{margin-bottom:8px}
.bb-section>header h2{font-size:2rem}
.bb-section>header .bb-lead{color:var(--muted)}
.bb-sub{padding-top:26px}
.bb-sub>h3{font-size:1.1rem;margin-bottom:12px;display:flex;align-items:center;gap:10px}
.bb-sub>h3::before{content:"";width:10px;height:10px;border-radius:3px;background:var(--primary);display:inline-block}
.bb-lead{max-width:720px}
.bb-note{color:var(--muted);font-size:14px;margin-top:12px;max-width:720px}

/* surfaces */
.bb-surface{background:var(--card);color:var(--card-fg);--line:var(--card-line);--muted:var(--card-muted)}
.bb-grid2,.bb-grid3,.bb-grid4{display:grid;gap:18px}
.bb-grid2{grid-template-columns:repeat(auto-fill,minmax(min(340px,100%),1fr))}
.bb-grid3{grid-template-columns:repeat(auto-fill,minmax(min(220px,100%),1fr))}
.bb-grid4{grid-template-columns:repeat(auto-fill,minmax(min(200px,100%),1fr))}
.tight{gap:16px}
.bb-two{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:24px;align-items:center}
.bb-row{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
.bb-row.end{justify-content:flex-end}
.bb-rules{margin:0;padding-left:20px;max-width:760px}
.bb-rules li{margin:6px 0}
.bb-rules.bad li::marker{content:"✕  ";color:var(--destructive)}

/* hero */
.bb-hero{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:28px;align-items:center;padding:30px}
.bb-hero-art{display:grid;place-items:center;min-height:200px;background:var(--c-light);border-radius:18px;border:2px dashed color-mix(in srgb,var(--card-fg) 20%,transparent)}
.bb-hero h1{font-size:2.6rem;line-height:1.05}
.bb-tagline{font:600 1.15rem var(--f-display);color:var(--primary-strong)}
.bb-hero-facts{display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin-top:14px}
.bb-mini-sw{display:flex}
.bb-mini-sw i{width:24px;height:24px;border-radius:50%;border:2px solid var(--card-fg);margin-right:-6px}
.bb-mini-fonts{font-size:14px;color:var(--card-muted)}

/* logo */
.bb-logo-hero{display:grid;place-items:center;padding:36px}
.bb-logo-tile{margin:0}
.bb-logo-bg{position:relative;height:150px;border-radius:16px;border:2px solid var(--line)}
.bb-logo-tile.big .bb-logo-bg{height:190px}
.bb-logo-img{position:absolute;inset:22px;width:calc(100% - 44px);height:calc(100% - 44px);object-fit:contain}
.bb-logo-tile figcaption{display:flex;flex-direction:column;padding:8px 2px;font-size:13px}
.bb-logo-tile b{font:600 15px var(--f-display)}
.bb-logo-tile span{color:var(--muted)}
.bb-dl{color:var(--fg);font:600 12px var(--f-mono);margin-top:4px;text-underline-offset:3px}
.bb-clear{display:flex;flex-direction:column;align-items:flex-start;gap:10px}
.bb-clear-box{border:2px dashed var(--primary);background:repeating-linear-gradient(45deg,transparent 0 8px,color-mix(in srgb,var(--primary) 12%,transparent) 8px 10px);border-radius:6px}
.bb-clear-box img{background:var(--bg)}
.bb-mins{display:flex;gap:26px;align-items:flex-end;flex-wrap:wrap}
.bb-min{margin:0;display:flex;flex-direction:column;align-items:flex-start;gap:8px;font-size:12px;color:var(--muted)}
.bb-min img{width:auto}
.bb-dont{margin:0}
.bb-dont-bg{height:120px;border-radius:14px;display:grid;place-items:center;background:var(--c-light);border:2px solid var(--line);overflow:hidden}
.bb-dont-bg img{width:auto}
.bb-dont figcaption{font-size:13px;padding:8px 2px;display:flex;gap:8px;align-items:center}
.bb-x{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;background:var(--destructive);color:#fff;font-size:11px;flex:none}
.fx-stretch{transform:scaleX(1.3) scaleY(.75)}
.fx-rotate{transform:rotate(-16deg)}
.fx-recolor{filter:hue-rotate(150deg) saturate(1.6)}
.fx-shadow{filter:drop-shadow(0 8px 10px rgba(0,0,0,.55)) drop-shadow(0 0 14px rgba(255,140,40,.9))}
.fx-outline{filter:drop-shadow(2px 0 0 #E5262B) drop-shadow(-2px 0 0 #E5262B) drop-shadow(0 2px 0 #E5262B) drop-shadow(0 -2px 0 #E5262B)}
.bb-dont-bg.busy{background:repeating-linear-gradient(60deg,#2a7 0 14px,#f6b 14px 28px,#47f 28px 42px)}

/* colour */
.bb-sw{overflow:hidden;display:flex;flex-direction:column}
.bb-sw-chip{all:unset;cursor:copy;height:84px;display:flex;align-items:flex-end;padding:10px 12px;font:600 13px var(--f-mono);border-bottom:2px solid var(--line)}
.bb-sw-txt{padding:10px 12px 12px;display:flex;flex-direction:column;gap:2px;font-size:13px}
.bb-sw-txt b{font:600 15px var(--f-display)}
.bb-sw-txt code{font-size:11.5px;color:var(--card-muted)}
.bb-sw-txt p{margin-top:6px}
.bb-shell{border-radius:18px;padding:22px;display:flex;flex-direction:column;gap:14px;align-items:flex-start;border:2px solid var(--line)}
.bb-shell-card{padding:14px 16px;display:flex;flex-direction:column}
.bb-pair{display:inline-grid;place-items:center;width:44px;height:30px;border-radius:8px;font:600 15px var(--f-display);border:1.5px solid rgba(0,0,0,.15)}
.bb-verdict{font:600 11px var(--f-mono);text-transform:uppercase;letter-spacing:.06em;padding:3px 8px;border-radius:999px;border:1.5px solid currentColor;white-space:nowrap}
.bb-verdict.ok{color:var(--success)} .bb-verdict.mid{color:#A06A00} .bb-verdict.bad{color:var(--destructive)}

/* tables */
.bb-tablewrap{overflow-x:auto;padding:4px 6px}
.bb-table{width:100%;border-collapse:collapse;font-size:14px}
.bb-table th{font:600 .68rem var(--f-mono);text-transform:uppercase;letter-spacing:.08em;text-align:left;color:var(--card-muted);padding:10px}
.bb-table td{padding:10px;border-top:1.5px solid color-mix(in srgb,var(--card-fg) 12%,transparent);vertical-align:middle}
.bb-avoid{color:var(--card-muted);text-decoration:line-through;text-decoration-color:var(--destructive)}

/* type */
.bb-font{padding:16px;display:flex;flex-direction:column;gap:2px}
.bb-font .bb-aa{font-size:64px;line-height:1.1;font-weight:600}
.bb-font b{font:600 16px var(--f-display)}
.bb-font span{font-size:13px;color:var(--card-muted)}
.bb-font p{margin-top:10px;font-size:15px}
.bb-scale{padding:6px 18px}
.bb-scale-row{display:grid;grid-template-columns:230px minmax(0,1fr);gap:18px;align-items:center;padding:14px 0;border-top:1.5px solid color-mix(in srgb,var(--card-fg) 12%,transparent)}
.bb-scale-row:first-child{border-top:0}
.bb-scale-meta{display:flex;flex-direction:column;font-size:12.5px}
.bb-scale-meta b{font:600 15px var(--f-display)}
.bb-scale-meta code{font-size:11.5px;color:var(--card-muted)}
.bb-scale-meta span{color:var(--card-muted)}
.bb-scale-sample{overflow-wrap:anywhere;line-height:1.15}

/* shape */
.bb-rads{display:flex;flex-wrap:wrap;gap:22px}
.bb-rad{display:flex;flex-direction:column;gap:4px;font-size:13px;width:140px}
.bb-rad-box{width:120px;height:84px;background:var(--card);border:2.5px solid var(--line)}
.bb-rad b{font:600 14px var(--f-display)} .bb-rad span{color:var(--muted)}
.bb-elev{appearance:none;font:inherit;text-align:left;cursor:pointer;padding:18px;display:flex;flex-direction:column;gap:4px;transition:transform .15s ease,box-shadow .15s ease}
.bb-elev:hover,.bb-elev:active{transform:translate(var(--press-t),var(--press-t));box-shadow:var(--press-o) var(--press-o) 0 0 var(--line)}
.bb-elev code{font:600 15px var(--f-mono)} .bb-elev span,.bb-elev small{font-size:13px;color:var(--card-muted)}
.bb-blobs{display:flex;gap:16px}
.bb-blob{width:64px;height:64px;display:grid;place-items:center;color:#fff;font:600 24px var(--f-display);border:2.5px solid var(--line)}
.bb-inline{font-size:12.5px;background:color-mix(in srgb,var(--fg) 8%,transparent);padding:2px 7px;border-radius:6px}

/* motion */
.bb-pr{padding:16px} .bb-pr b{font:600 16px var(--f-display)} .bb-pr p{color:var(--card-muted);font-size:14px}
.bb-toks{padding:6px 18px}
.bb-tok{padding:12px 0;border-top:1.5px solid color-mix(in srgb,var(--card-fg) 12%,transparent)}
.bb-tok:first-child{border-top:0}
.bb-tok pre{margin:8px 0 0;font-size:12.5px;white-space:pre-wrap;color:var(--card-fg)}
.bb-tok .bb-inline{background:color-mix(in srgb,var(--card-fg) 8%,transparent)}

/* voice */
.bb-pairs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 18px;max-width:900px}
.bb-pair-do{display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-top:1.5px solid color-mix(in srgb,var(--fg) 12%,transparent)}
.bb-pair-do p{margin:0}
.bb-strike{text-decoration:line-through;text-decoration-color:var(--destructive);color:var(--muted)}
.bb-mc{padding:14px}

/* code */
.bb-code{margin-top:12px}
.bb-code summary{cursor:pointer;font:600 12px var(--f-mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);width:max-content}
.bb-codebox{position:relative;margin-top:8px;background:#1B120C;color:#F4E8D8;border-radius:14px;padding:16px;overflow:auto}
.bb-codebox pre{margin:0;font-size:12.5px;line-height:1.6}
.bb-copy{position:absolute;top:10px;right:10px;font:600 11px var(--f-mono);background:#3a2a1e;color:#F4E8D8;border:0;border-radius:8px;padding:5px 9px;cursor:pointer}

/* components */
.bb-demo{background:var(--bg);border:2px dashed color-mix(in srgb,var(--fg) 22%,transparent);border-radius:18px;padding:22px}
.bb-scroll{overflow-x:auto}
.bb-matrix{border-collapse:separate;border-spacing:14px 12px;margin:-12px -14px}
.bb-matrix th{font:600 .68rem var(--f-mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);text-align:left;white-space:nowrap}
.bb-matrix tbody th{font:600 14px var(--f-display);text-transform:none;letter-spacing:0;color:var(--fg)}
.bb-matrix th small{display:block;font:500 11px var(--f-body);color:var(--muted)}
.bb-btn{font:600 15px var(--f-display);padding:9px 18px;display:inline-flex;align-items:center;gap:8px;cursor:pointer;white-space:nowrap;
  background:var(--b,var(--primary));color:var(--bf,var(--primary-fg));transition:transform .15s ease,box-shadow .15s ease}
.bb-btn:hover,.bb-btn.is-hover,.bb-btn:active,.bb-btn.is-press{transform:translate(var(--press-t),var(--press-t));box-shadow:var(--press-o) var(--press-o) 0 0 var(--line)}
.bb-btn.is-press{box-shadow:0 0 0 0 var(--line);filter:brightness(.95)}
.bb-btn[disabled]{cursor:not-allowed;transform:none!important}
.bb-btn.disabled{opacity:.45;box-shadow:none!important}
.bb-btn.loading{cursor:progress}
.bb-spin{width:14px;height:14px;border-radius:50%;border:2.5px solid currentColor;border-right-color:transparent;animation:bbspin .7s linear infinite}
@keyframes bbspin{to{transform:rotate(360deg)}}
.bb-field{display:flex;flex-direction:column;gap:6px}
.bb-field .bb-eyebrow{color:var(--fg)}
.bb-field small{font-size:12px;color:var(--muted)}
.bb-field small.bb-err{color:var(--destructive);font-weight:600}
.bb-input{display:flex;align-items:center;background:var(--card);color:var(--card-fg);--line:var(--card-line);overflow:hidden}
.bb-input.focus{outline:3px solid var(--primary);outline-offset:3px}
.bb-input.error{--line:var(--destructive)}
.bb-prefix{font:600 15px var(--f-mono);padding:0 4px 0 14px;color:var(--card-muted)}
.bb-input input{all:unset;flex:1;min-width:0;padding:11px 14px 11px 6px;font:600 16px var(--f-mono);font-variant-numeric:tabular-nums}
.bb-input input::placeholder{color:var(--card-muted);font-weight:400}
.bb-status{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;font:600 11.5px var(--f-mono);text-transform:uppercase;letter-spacing:.06em;background:var(--card);color:var(--card-fg)}
.bb-status i{width:9px;height:9px;border-radius:50%}
.bb-status.sm{padding:3px 10px;font-size:10.5px;box-shadow:none;border-width:1.5px}
.bb-ach{display:inline-flex;padding:6px 14px;color:#fff;font:600 15px var(--f-display);transform:rotate(2deg)}
.bb-card{padding:22px;display:flex;flex-direction:column;align-items:flex-start;gap:4px}
.bb-card h4{font-size:1.1rem}
.bb-card .bb-btn{margin-top:12px}
.bb-amount{font:700 2.2rem var(--f-mono);font-variant-numeric:tabular-nums;margin:4px 0;letter-spacing:-.02em}
.bb-amount.sm{font-size:1.5rem}
.bb-stat{padding:16px}
.bb-skel i{display:block;height:12px;border-radius:6px;background:color-mix(in srgb,var(--card-fg) 12%,transparent);margin:8px 0;animation:bbpulse 1.4s ease-in-out infinite}
@keyframes bbpulse{50%{opacity:.45}}
.bb-av-wrap{display:flex;flex-direction:column;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
.bb-avatar{width:44px;height:44px;display:grid;place-items:center;color:#fff;font:600 17px var(--f-display);flex:none}
.bb-avatar.sm{width:30px;height:30px;font-size:13px}
.bb-cell-av{display:flex;align-items:center;gap:10px;font-weight:500}
/* motion */
.bb-ease{padding:14px;display:flex;flex-direction:column;gap:8px}
.bb-ease-svg{width:100%;height:110px}
.bb-ease-grid{stroke:var(--card-muted);stroke-dasharray:3 4;fill:none;opacity:.5}
.bb-ease-handle{stroke:var(--card-muted);fill:none;opacity:.7}
.bb-ease-curve{stroke:var(--primary);stroke-width:3;fill:none;stroke-linecap:round}
.bb-ease-track{position:relative;height:14px;border-radius:7px;background:color-mix(in srgb,var(--card-fg) 8%,transparent)}
.bb-ease-dot{position:absolute;top:0;left:0;width:14px;height:14px;border-radius:7px;background:var(--primary)}
.bb-ease code{font-size:11px;word-break:break-all}
.bb-durs{padding:16px 18px;display:grid;gap:12px}
.bb-dur{display:grid;grid-template-columns:90px 70px 1fr;align-items:center;gap:12px}
.bb-dur-track{height:10px;border-radius:5px;background:color-mix(in srgb,var(--card-fg) 8%,transparent);overflow:hidden}
.bb-dur-track i{display:block;height:100%;width:0;background:var(--primary);border-radius:5px}
.bb-mx{display:flex;flex-direction:column;overflow:hidden}
.bb-mx-stage{height:190px;display:grid;place-items:center;padding:18px;background:var(--bg);color:var(--fg);--line:var(--fg)}
.bb-mx-clip{overflow:hidden}
.bb-mx-txt{padding:12px 16px 4px;display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline}
.bb-mx-txt p{width:100%;margin:0;font-size:13.5px}
.bb-mx .bb-code{margin:6px 16px 14px}
.bb-mx-card{display:flex;gap:10px;align-items:center;padding:12px 14px;width:220px;max-width:100%}
.bb-mx-card>div{flex:1;display:grid;gap:6px}
.bb-mx-dot{width:26px;height:26px;border-radius:50%;background:var(--primary);flex:none}
.bb-mx-line{display:block;height:8px;border-radius:4px;background:color-mix(in srgb,var(--card-fg) 18%,transparent)}
.bb-mx-sk{--sk:color-mix(in srgb,var(--card-fg) 12%,transparent);--sk2:color-mix(in srgb,var(--card-fg) 28%,transparent)}
.bb-mx-sk .bb-mx-dot{background:color-mix(in srgb,var(--card-fg) 14%,transparent)}
.bb-mx-list{display:grid;gap:6px}.bb-mx-list .bb-mx-card{padding:6px 10px;width:200px}.bb-mx-list .bb-mx-dot{width:16px;height:16px}
.bb-mx-badge{display:grid;place-items:center;width:64px;height:64px;border-radius:50%;font:700 28px var(--f-display);border:2.5px solid var(--line)}
@media (prefers-reduced-motion: reduce){.bb-mx *,.bb-ease *,.bb-dur *{animation:none!important}.bb-dur-track i{width:100%}}
.bb-toast{display:flex;gap:12px;padding:14px;align-items:flex-start}
.bb-toast b{font:600 15px var(--f-display)} .bb-toast p{margin:2px 0 0;font-size:13.5px;color:var(--card-muted)}
.bb-toast-dot{width:26px;height:26px;flex:none;border:2px solid var(--card-line)}
.bb-empty{display:flex;flex-direction:column;align-items:center;text-align:center;padding:28px;max-width:420px;margin:0 auto}
.bb-empty-art{min-height:90px;display:grid;place-items:center;margin-bottom:6px}
.bb-tabs{display:inline-flex;gap:4px;padding:4px;border:2px solid var(--line);border-radius:999px;background:var(--card)}
.bb-tab{all:unset;cursor:pointer;font:600 14px var(--f-display);padding:6px 16px;border-radius:999px;color:var(--card-fg)}
.bb-tab.on{background:var(--primary);color:var(--primary-fg)}
.bb-dialog-backdrop{background:color-mix(in srgb,#000 45%,transparent);border-radius:14px;padding:34px 18px;display:grid;place-items:center}
.bb-dialog{padding:24px;max-width:420px;width:100%}
.bb-dialog h4{font-size:1.25rem} .bb-dialog p{color:var(--card-muted)}
.bb-dialog .bb-row{margin-top:18px}
.bb-toast-live{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:var(--card);color:var(--card-fg);border:2px solid var(--card-line);border-radius:999px;padding:6px 14px;font:600 12px var(--f-mono);opacity:0;transition:opacity .2s;pointer-events:none;z-index:9}
.bb-toast-live.show{opacity:1}

/* responsive */
@media (max-width:900px){
  .bb-layout{grid-template-columns:minmax(0,1fr)}
  .bb-side{position:sticky;top:0;z-index:5;height:auto;display:flex;align-items:center;gap:10px;padding:8px 12px;border-right:0;border-bottom:2px solid var(--line);background:var(--bg)}
  .bb-brand{margin:0;flex:none}.bb-brand small{display:none}.bb-brand img{height:22px}
  .bb-nav{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;flex:1}
  .bb-nav .subs{display:none!important}
  .bb-nav .sec{white-space:nowrap;font-size:13px;padding:5px 10px}.bb-nav .sec .n{display:none}
  .bb-theme{margin:0;width:auto;flex:none;font-size:12px;padding:5px 10px}
  .bb-main{padding:18px 16px 100px}
  html{scroll-padding-top:64px}
  .bb-hero,.bb-two{grid-template-columns:1fr}
  .bb-hero h1{font-size:2rem}
  .bb-scale-row{grid-template-columns:1fr;gap:6px}
  .bb-pairs{grid-template-columns:1fr}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}html{scroll-behavior:auto}}
"""

BASE_JS = r"""
(function(){
  const live=document.createElement('div');live.className='bb-toast-live';document.body.appendChild(live);
  const say=t=>{live.textContent=t;live.classList.add('show');clearTimeout(live._t);live._t=setTimeout(()=>live.classList.remove('show'),1300);};
  const copy=t=>{(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>say(UI.copied+': '+t.slice(0,40))).catch(()=>say(t));};
  document.querySelectorAll('.bb-copy').forEach(b=>b.onclick=()=>copy(b.parentElement.querySelector('code').textContent));
  document.querySelectorAll('[data-copy]').forEach(b=>b.onclick=()=>copy(b.dataset.copy));
  // theme
  const tb=document.getElementById('bb-theme');
  const setT=d=>{document.body.classList.toggle('dark',d);tb.textContent=d?UI.light:UI.dark;try{localStorage.setItem('bb-dark',d?'1':'0')}catch(e){}};
  let saved=null;try{saved=localStorage.getItem('bb-dark')}catch(e){}
  const qs=new URLSearchParams(location.search);
  // ?only=id[,id] shows just those sections/sub-sections (cheap, targeted screenshots)
  if(qs.has('only')){const ids=qs.get('only').split(',');document.body.classList.add('bb-only');
    document.querySelectorAll('.bb-section').forEach(sec=>{
      const subs=[...sec.querySelectorAll('.bb-sub')],hit=ids.includes(sec.id),subHit=subs.filter(x=>ids.includes(x.id));
      if(!hit&&!subHit.length)sec.style.display='none';
      else if(!hit)subs.forEach(x=>{if(!subHit.includes(x))x.style.display='none'});});}
  setT(qs.has('dark')?qs.get('dark')==='1':saved==='1');
  tb.onclick=()=>setT(!document.body.classList.contains('dark'));
  // scrollspy
  const links=[...document.querySelectorAll('.bb-nav a')];
  const byId=Object.fromEntries(links.map(a=>[a.getAttribute('href').slice(1),a]));
  const targets=[...document.querySelectorAll('.bb-section,.bb-sub')];
  function spy(){
    let cur=null;const y=window.innerHeight*0.28;
    for(const t of targets){if(t.getBoundingClientRect().top<=y)cur=t;}
    if(!cur)cur=targets[0];
    const sec=cur.closest('.bb-section');
    links.forEach(a=>a.classList.remove('on'));
    document.querySelectorAll('.bb-nav>li').forEach(li=>li.classList.remove('open'));
    const sa=byId[sec.id];if(sa){sa.classList.add('on');sa.parentElement.classList.add('open');
      if(window.innerWidth<=900)sa.scrollIntoView({block:'nearest',inline:'center'});}
    if(cur!==sec&&byId[cur.id])byId[cur.id].classList.add('on');
  }
  let raf;window.addEventListener('scroll',()=>{cancelAnimationFrame(raf);raf=requestAnimationFrame(spy)},{passive:true});spy();
  // debug: ?t=ms freezes animations (screenshots)
  if(qs.has('t'))setTimeout(()=>document.getAnimations().forEach(a=>{a.pause();a.currentTime=+qs.get('t')}),50);
})();
"""


def build(path, out):
    b = Book(path)
    b.load_extras()
    th, f = b.d["theme"], b.d["fonts"]
    ev = b.d["shape"]["elevation"]
    elev_css = "\n".join(b.level_css("." + l["name"], l) for l in ev["levels"])
    for alias, l in zip(("lv-big", "lv-mid", "lv-pill"), b.levels()):
        elev_css += "\n" + b.level_css("." + alias, l)
    soft = ev.get("style", "offset") != "offset"
    pr = ev.get("press", {"translate": 0 if soft else 3, "offset": 0 if soft else 1})
    card_fg = b.c("card_fg")
    tokens = f""":root{{
  --f-display:'{f["display"]["family"]}',{f["display"]["fallback"]};--f-body:'{f["body"]["family"]}',{f["body"]["fallback"]};--f-mono:'{f["mono"]["family"]}',{f["mono"]["fallback"]};
  --bg:{b.c(th["light"]["bg"])};--fg:{b.c(th["light"]["fg"])};--muted:{b.c(th["light"]["muted"])};--line:var(--fg);
  --c-light:{b.c(th["light"]["bg"])};--c-dark:{b.c(th["dark"]["bg"])};
  --card:{b.c("card")};--card-fg:{card_fg};--card-line:{card_fg};--card-muted:color-mix(in srgb,{card_fg} 62%,{b.c("card")});
  --primary:{b.c("primary")};--primary-fg:{b.c("primary_fg")};--primary-strong:color-mix(in srgb,{b.c("primary")} 70%,{card_fg});
  --secondary:{b.c("secondary")};--destructive:{b.c("destructive")};--success:{b.c("success")};--achievement:{b.c("achievement")};
  --press-t:{pr["translate"]}px;--press-o:{pr["offset"]}px;
}}
body.dark{{--bg:{b.c(th["dark"]["bg"])};--fg:{b.c(th["dark"]["fg"])};--muted:{b.c(th["dark"]["muted"])}}}
{elev_css}"""

    # assemble sections (core + extras placed after their anchor)
    secs = []
    needs = {"logo": "logo", "color": "colors", "type": "fonts", "shape": "shape",
             "voice": "voice", "components": "components"}
    for sid, title_key, lead_key, fn in CORE:
        if sid in needs and needs[sid] not in b.d:
            continue
        subs = [x for x in fn(b) if x] + b.ext["into"].get(sid, [])
        if not subs:
            continue
        secs.append({"id": sid, "title": b.L(title_key), "lead": esc(b.L(lead_key)) if lead_key else "", "children": subs})
    for x in b.ext["sections"]:
        idx = next((k for k, s in enumerate(secs) if s["id"] == x.get("after")), len(secs) - 1)
        secs.insert(idx + 1, x)

    nav, body = [], []
    for n, s in enumerate(secs):
        subs = s["children"]
        hide_subs = s["id"] == "overview"
        sub_nav = "" if hide_subs else "".join(f'<li><a class="sub" href="#{c["id"]}">{esc(c["title"])}</a></li>' for c in subs)
        nav.append(f'<li><a class="sec" href="#{s["id"]}"><span class="n">{n:02d}</span>{esc(s["title"])}</a>'
                   + (f'<ul class="subs">{sub_nav}</ul>' if sub_nav else "") + "</li>")
        head = "" if s["id"] == "overview" else (f'<header><p class="bb-eyebrow">{n:02d}</p><h2>{esc(s["title"])}</h2>'
                                                  + (f'<p class="bb-lead">{s["lead"]}</p>' if s.get("lead") else "") + "</header>")
        inner = "".join(
            (f'<div class="bb-sub" id="{c["id"]}"><h3>{esc(c["title"])}</h3>{c["html"]}</div>' if not hide_subs else
             f'<div class="bb-sub" id="{c["id"]}">{c["html"]}</div>') for c in subs)
        body.append(f'<section class="bb-section" id="{s["id"]}">{head}{inner}</section>')

    m = b.meta
    ui = json.dumps({"light": b.t("theme_light", "Light"), "dark": b.t("theme_dark", "Dark"), "copied": b.t("copied", "Copied")})
    brand_logo = (f'<span class="only-light">{b.img(b.d["logo"]["primary"]["light"])}</span>'
                  f'<span class="only-dark">{b.img(b.d["logo"]["primary"]["dark"])}</span>')
    page = f"""<!doctype html>
<html lang="{m.get("lang","en")}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(m["title"])}</title>
<link rel="icon" href="{b.data_uri(b.d["logo"]["marks"][0]["file"])}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{f["css"]}" rel="stylesheet">
<style>{tokens}{BASE_CSS}{b.ext["css"]}</style></head>
<body>
<div class="bb-layout">
  <aside class="bb-side"><a class="bb-brand" href="#overview">{brand_logo}<small>{esc(" · ".join(x for x in (m.get("system",""), m.get("updated","")) if x))}</small></a>
    <ul class="bb-nav">{"".join(nav)}</ul>
    <button id="bb-theme" class="bb-btn lv-pill bb-theme" type="button"></button></aside>
  <main class="bb-main">{"".join(body)}</main>
</div>
<script>const UI={ui};</script>
<script>{BASE_JS}</script>
<script>{b.ext["js"]}</script>
</body></html>"""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, "w", encoding="utf-8").write(page)
    print(f"wrote {out} ({len(page)//1024} KB, {len(secs)} sections, {sum(len(s['children']) for s in secs)} sub-sections)")
    print("  check one with: render.py shot <book> -o x.png --only <id>   ids: " + " ".join(s["id"] for s in secs))
    print("  don't read the HTML itself: it embeds every asset (~" + str(len(page) // 4000) + "k tokens)")


if __name__ == "__main__":
    if "--print-labels" in sys.argv:
        print(json.dumps(DEFAULT_LABELS, indent=2, ensure_ascii=False))
        sys.exit()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.brand)), "brand-book.html")
    build(a.brand, out)
