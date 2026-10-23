"""Export brand.json design tokens into stack-specific formats.

Usage:  python export_tokens.py brand.json [-o tokens/] [--only dtcg css tailwind4 shadcn tailwind3 flutter swift compose rn]

Writes:
  tokens.json      W3C Design Tokens (DTCG) — universal source for Style Dictionary, Figma Tokens, mobile, etc.
  tokens.css       plain CSS custom properties (+ .dark shell) — works in any web stack
  tailwind4.css    Tailwind v4: @theme inline mapping + @utility for elevation levels and blob
  shadcn.css       shadcn/ui variable names (:root / .dark) mapped from the brand theme
  tailwind3.js     Tailwind v3 theme.extend (colours/radius/fonts/shadows reading the CSS variables)
  brand_theme.dart Flutter: BrandColors, BrandRadius, BrandFonts, light/dark ThemeData (Material 3 ColorScheme)
  BrandTheme.swift SwiftUI (iOS): Color.brand* that switch with dark mode, radius and font names
  BrandTheme.kt    Jetpack Compose: palette, light/dark ColorScheme, BrandTheme { } wrapper, radius in dp
  theme.ts         React Native / Expo: palette, light/dark roles, radius, fonts, elevation as RN shadow props
Fonts in the native files are family names only: bundle the font files the way the project already does.

Rule of the brand-book system: surfaces (card) never change between shells; only the shell does.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_book import oklch_hex, MOTION_DEFAULTS  # noqa: E402


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class Tokens:
    def __init__(self, path):
        self.d = json.load(open(path, encoding="utf-8"))
        self.colors = {c["name"]: c for g in self.d["colors"]["groups"] for c in g["items"]}
        self.theme = self.d["theme"]

    def css_color(self, ref):
        """oklch() when the brand defines it (keeps wide gamut), else hex."""
        if ref.startswith("#"):
            return ref
        if ref in self.colors:
            c = self.colors[ref]
            if c.get("oklch"):
                L, C, h = c["oklch"]
                return f"oklch({L} {C} {h})"
            return c["hex"]
        return self.css_color(self.theme[ref])

    def hex(self, ref):
        if ref.startswith("#"):
            return ref
        if ref in self.colors:
            c = self.colors[ref]
            return c.get("hex") or oklch_hex(*c["oklch"])
        return self.hex(self.theme[ref])

    # semantic roles shared by every exporter
    def roles(self, mode):
        t, sh = self.theme, self.theme[mode]
        r = {
            "background": sh["bg"], "foreground": sh["fg"], "muted-foreground": sh["muted"],
            "card": t["card"], "card-foreground": t["card_fg"],
            "primary": t["primary"], "primary-foreground": t["primary_fg"],
            "secondary": t["secondary"], "secondary-foreground": t["secondary_fg"],
            "destructive": t["destructive"], "destructive-foreground": t["destructive_fg"],
        }
        for k in ("accent", "success", "pending", "achievement"):
            if k in t:
                r[k] = t[k]
        return r

    @property
    def motion(self):
        mo = self.d.get("motion", {})
        return ({**MOTION_DEFAULTS["durations"], **mo.get("durations", {})},
                {**MOTION_DEFAULTS["easings"], **mo.get("easings", {})})

    @property
    def levels(self):
        return self.d["shape"]["elevation"]["levels"]

    def shadow(self, l, var="var(--line)"):
        style = self.d["shape"]["elevation"].get("style", "offset")
        if style == "offset":
            return f'{l["offset"]}px {l["offset"]}px 0 0 {var}'
        return f'0 {l["offset"]}px {l["offset"]*3}px rgb(0 0 0 / .15)'

    # ---------------------------------------------------------------- exporters
    def dtcg(self):
        out = {"color": {}, "role": {"light": {}, "dark": {}}, "font": {}, "radius": {}, "elevation": {}, "duration": {}, "easing": {}}
        dur, eas = self.motion
        for k, v in dur.items():
            out["duration"][k] = {"$type": "duration", "$value": {"value": v, "unit": "ms"}}
        for k, v in eas.items():
            out["easing"][k] = {"$type": "cubicBezier", "$value": v}
        for name, c in self.colors.items():
            out["color"][slug(name)] = {"$type": "color", "$value": c.get("hex") or oklch_hex(*c["oklch"]),
                                        "$description": c.get("role", ""),
                                        "$extensions": {"oklch": c.get("oklch"), "token": c.get("token")}}
        for mode in ("light", "dark"):
            for role, ref in self.roles(mode).items():
                val = "{color." + slug(ref) + "}" if ref in self.colors else self.hex(ref)
                out["role"][mode][role] = {"$type": "color", "$value": val}
        for k, f in self.d["fonts"].items():
            if isinstance(f, dict):
                out["font"][k] = {"$type": "fontFamily", "$value": [f["family"]] + [x.strip() for x in f["fallback"].split(",")],
                                  "$description": f.get("use", "")}
        for r in self.d["shape"]["radius"]:
            out["radius"][r["name"]] = {"$type": "dimension", "$value": f'{r["px"]}px', "$description": r.get("use", "")}
        for l in self.levels:
            out["elevation"][l["name"]] = {"$type": "shadow", "$value": {"offsetX": f'{l["offset"]}px', "offsetY": f'{l["offset"]}px',
                                           "blur": "0px", "spread": "0px", "color": "{role.light.foreground}"},
                                           "$extensions": {"radius": f'{l["radius"]}px', "border": f'{l["border"]}px'}}
        return json.dumps(out, indent=2, ensure_ascii=False)

    # ---------------------------------------------------------------- native
    def _native(self):
        """Shared data for the native exporters: palette, light/dark roles (hex), radius, fonts."""
        ident = lambda s: "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", s) if w) or "Color"
        camel = lambda s: (lambda t: t[0].lower() + t[1:])(ident(s))
        pal = {ident(n): self.hex(n) for n in self.colors}
        roles = {m: {camel(r): self.hex(v) for r, v in self.roles(m).items()} for m in ("light", "dark")}
        radius = {("r" + ident(r["name"])) if r["name"][0].isdigit() else camel(r["name"]): r["px"]
                  for r in self.d["shape"]["radius"]}
        fonts = {k: f["family"] for k, f in self.d["fonts"].items() if isinstance(f, dict)}
        return pal, roles, radius, fonts, camel

    @staticmethod
    def _scheme_args(r, argb):
        g = lambda k, d: argb(r.get(k, r[d]))
        return [("primary", g("primary", "primary")), ("onPrimary", g("primaryForeground", "foreground")),
                ("secondary", g("secondary", "primary")), ("onSecondary", g("secondaryForeground", "primaryForeground")),
                ("error", g("destructive", "primary")), ("onError", g("destructiveForeground", "primaryForeground")),
                ("surface", g("card", "background")), ("onSurface", g("cardForeground", "foreground"))]

    def flutter(self):
        pal, roles, radius, fonts, camel = self._native()
        argb = lambda h: "Color(0xFF" + h.lstrip("#")[:6].upper() + ")"

        def theme(m):
            args = ", ".join(f"{k}: {v}" for k, v in self._scheme_args(roles[m], argb))
            return (f"  static ThemeData get {m} => ThemeData(\n    useMaterial3: true,\n"
                    f"    colorScheme: ColorScheme(brightness: Brightness.{m}, {args}),\n"
                    f"    scaffoldBackgroundColor: {argb(roles[m]['background'])},\n"
                    f"    fontFamily: BrandFonts.{'body' if 'body' in fonts else next(iter(fonts), 'body')},\n  );")
        L = ["// Generated from brand.json by export_tokens.py. Fonts: bundle them in pubspec.yaml under these family names.",
             "import 'package:flutter/material.dart';", "", "class BrandColors {", "  BrandColors._();"]
        L += [f"  static const {camel(k)} = {argb(v)};" for k, v in pal.items()]
        L += ["}", "", "class BrandRadius {", "  BrandRadius._();"]
        L += [f"  static const double {k} = {v};" for k, v in radius.items()]
        L += ["}", "", "class BrandFonts {", "  BrandFonts._();"]
        L += [f"  static const {k} = '{v}';" for k, v in fonts.items()]
        L += ["}", "", "class BrandTheme {", "  BrandTheme._();", theme("light"), theme("dark"), "}"]
        return "\n".join(L) + "\n"

    def swift(self):
        pal, roles, radius, fonts, camel = self._native()
        rgb = lambda h: ", ".join(f"{int(h.lstrip('#')[i:i + 2], 16) / 255:.4f}" for i in (0, 2, 4))
        L = ["// Generated from brand.json by export_tokens.py (iOS / SwiftUI). Fonts: add the files to the target,",
             "// list them under UIAppFonts in Info.plist, and use the family names below.",
             "import SwiftUI", "import UIKit", "",
             "private func dynamic(_ light: (Double, Double, Double), _ dark: (Double, Double, Double)) -> Color {",
             "    Color(UIColor { $0.userInterfaceStyle == .dark",
             "        ? UIColor(red: dark.0, green: dark.1, blue: dark.2, alpha: 1)",
             "        : UIColor(red: light.0, green: light.1, blue: light.2, alpha: 1) })", "}", "",
             "public extension Color {", "    // palette"]
        lab = lambda h: ", ".join(f"{n}: {x}" for n, x in zip(("red", "green", "blue"), rgb(h).split(", ")))
        L += [f"    static let palette{k} = Color(red: {lab(v)[5:]})" for k, v in pal.items()]
        L.append("    // roles: switch with light/dark mode")
        for r in roles["light"]:
            L.append(f"    static let brand{r[0].upper() + r[1:]} = dynamic(({rgb(roles['light'][r])}), ({rgb(roles['dark'][r])}))")
        L += ["}", "", "public enum BrandRadius {"]
        L += [f"    public static let {k}: CGFloat = {v}" for k, v in radius.items()]
        L += ["}", "", "public enum BrandFont {"]
        L += [f'    public static let {k} = "{v}"' for k, v in fonts.items()]
        L += ["}"]
        return "\n".join(L) + "\n"

    def compose(self):
        pal, roles, radius, fonts, camel = self._native()
        argb = lambda h: "Color(0xFF" + h.lstrip("#")[:6].upper() + ")"

        def scheme(m):
            r = roles[m]
            args = self._scheme_args(r, argb) + [("background", argb(r["background"])), ("onBackground", argb(r["foreground"]))]
            body = ",\n".join(f"    {k} = {v}" for k, v in args)
            return f"val Brand{m.title()}Colors = {m}ColorScheme(\n{body},\n)"
        L = ["// Generated from brand.json by export_tokens.py (Jetpack Compose, Material 3).",
             "// Fonts: add them to res/font and build a FontFamily; the family names are in BrandFonts.",
             "package brand", "", "import androidx.compose.foundation.isSystemInDarkTheme",
             "import androidx.compose.material3.MaterialTheme", "import androidx.compose.material3.darkColorScheme",
             "import androidx.compose.material3.lightColorScheme", "import androidx.compose.runtime.Composable",
             "import androidx.compose.ui.graphics.Color", "import androidx.compose.ui.unit.dp", "", "object BrandPalette {"]
        L += [f"    val {k} = {argb(v)}" for k, v in pal.items()]
        L += ["}", "", "object BrandRadius {"]
        L += [f"    val {k} = {v}.dp" for k, v in radius.items()]
        L += ["}", "", "object BrandFonts {"]
        L += [f'    const val {k} = "{v}"' for k, v in fonts.items()]
        L += ["}", "", scheme("light"), "", scheme("dark"), "",
              "@Composable", "fun BrandTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {",
              "    MaterialTheme(colorScheme = if (darkTheme) BrandDarkColors else BrandLightColors, content = content)", "}"]
        return "\n".join(L) + "\n"

    def rn(self):
        pal, roles, radius, fonts, camel = self._native()
        offset = self.d["shape"]["elevation"].get("style", "offset") == "offset"
        lv = {camel(l["name"]): {"borderRadius": l["radius"], "borderWidth": l["border"],
                                 "shadowOffset": {"width": l["offset"] if offset else 0, "height": l["offset"]},
                                 "shadowOpacity": 1 if offset else .15, "shadowRadius": 0 if offset else l["offset"] * 2,
                                 "elevation": l["offset"]} for l in self.levels}
        j = lambda o: json.dumps(o, indent=2, ensure_ascii=False)
        return ("// Generated from brand.json by export_tokens.py (React Native / Expo).\n"
                "// Fonts: load them (e.g. expo-font useFonts) under these family names.\n"
                "// Elevation: iOS draws shadow*, Android only `elevation` (no hard offset shadows); set shadowColor per mode.\n"
                f"export const palette = {j({camel(k): v for k, v in pal.items()})} as const;\n\n"
                f"export const colors = {j(roles)} as const;\n\n"
                f"export const radius = {j(radius)} as const;\n\n"
                f"export const fonts = {j(fonts)} as const;\n\n"
                f"export const elevation = {j(lv)} as const;\n\n"
                "export type ColorMode = keyof typeof colors;\n")

    def css(self):
        f = self.d["fonts"]
        lines = [":root {"]
        for k in ("display", "body", "mono"):
            lines.append(f'  --font-{k}: "{f[k]["family"]}", {f[k]["fallback"]};')
        for role, ref in self.roles("light").items():
            lines.append(f"  --{role}: {self.css_color(ref)};")
        lines.append("  --line: var(--foreground);  /* bevel border/shadow; inside cards it becomes --card-foreground */")
        dur, eas = self.motion
        lines += [f"  --duration-{k}: {v}ms;" for k, v in dur.items()]
        lines += [f"  --ease-{k}: cubic-bezier({', '.join(f'{x:g}' for x in v)});" for k, v in eas.items()]
        for r in self.d["shape"]["radius"]:
            lines.append(f'  --radius-{r["name"]}: {r["px"]}px;')
        lines.append("}")
        lines.append(".dark {")
        for role, ref in self.roles("dark").items():
            if ref != self.roles("light")[role]:
                lines.append(f"  --{role}: {self.css_color(ref)};")
        lines.append("}")
        lines.append(".card, [data-surface] { --line: var(--card-foreground); }")
        for l in self.levels:
            lines.append(f'.{l["name"]} {{ border-radius: {l["radius"]}px; border: {l["border"]}px solid var(--line); box-shadow: {self.shadow(l)}; }}')
        p = self.d["shape"]["elevation"].get("press")
        if p:
            sel = ", ".join(f'.{l["name"]}:is(button, a):hover, .{l["name"]}:is(button, a):active' for l in self.levels)
            lines.append(f'.{", .".join(l["name"] for l in self.levels)} {{ transition: transform {p["ms"]}ms var(--ease-standard), box-shadow {p["ms"]}ms var(--ease-standard); }}')
            lines.append(f'{sel} {{ transform: translate({p["translate"]}px, {p["translate"]}px); box-shadow: {p["offset"]}px {p["offset"]}px 0 0 var(--line); }}')
        if self.d["shape"].get("blob"):
            lines.append(f'.blob {{ border-radius: {self.d["shape"]["blob"]}; }}')
        return "\n".join(lines) + "\n"

    def tailwind4(self):
        roles = list(self.roles("light"))
        lines = ['/* Tailwind v4 — import after tokens.css (or shadcn.css):  @import "./tokens.css";  @import "./tailwind4.css"; */',
                 "@theme inline {"]
        f = self.d["fonts"]
        for k in ("display", "body", "mono"):   # literal values: a var() pointing at itself would be a cycle in @theme
            lines.append(f'  --font-{k}: "{f[k]["family"]}", {f[k]["fallback"]};')
        for role in roles:
            lines.append(f"  --color-{role}: var(--{role});")
        lines.append("  --color-line: var(--line);")
        # literal values: --ease-x: var(--ease-x) inside @theme would be a cycle
        lines += [f"  --ease-{k}: cubic-bezier({', '.join(f'{x:g}' for x in v)});" for k, v in self.motion[1].items()]
        for r in self.d["shape"]["radius"]:
            lines.append(f'  --radius-{r["name"]}: {r["px"]}px;')
        lines.append("}")
        lines.append('@custom-variant dark (&:where(.dark, .dark *));')
        p = self.d["shape"]["elevation"].get("press")
        for l in self.levels:
            lines.append(f'@utility {l["name"]} {{ border-radius: {l["radius"]}px; border: {l["border"]}px solid var(--line); box-shadow: {self.shadow(l)};'
                         + (f' transition: transform {p["ms"]}ms var(--ease-standard), box-shadow {p["ms"]}ms var(--ease-standard);'
                            f' &:is(button, a):hover, &:is(button, a):active {{ transform: translate({p["translate"]}px, {p["translate"]}px); box-shadow: {p["offset"]}px {p["offset"]}px 0 0 var(--line); }}' if p else "")
                         + " }")
        if self.d["shape"].get("blob"):
            lines.append(f'@utility blob {{ border-radius: {self.d["shape"]["blob"]}; }}')
        return "\n".join(lines) + "\n"

    def shadcn(self):
        def block(mode):
            r = self.roles(mode)
            m = {
                "background": r["background"], "foreground": r["foreground"],
                "card": r["card"], "card-foreground": r["card-foreground"],
                "popover": r["card"], "popover-foreground": r["card-foreground"],
                "primary": r["primary"], "primary-foreground": r["primary-foreground"],
                "secondary": r["secondary"], "secondary-foreground": r["secondary-foreground"],
                "muted": r["card"], "muted-foreground": r["muted-foreground"],
                "accent": r.get("accent", r["secondary"]), "accent-foreground": r["card-foreground"],
                "destructive": r["destructive"], "destructive-foreground": r["destructive-foreground"],
                "border": r["foreground"], "input": r["card-foreground"], "ring": r["primary"],
            }
            for k in ("success", "pending", "achievement"):
                if k in r:
                    m[k] = r[k]
            return "\n".join(f"  --{k}: {self.css_color(v)};" for k, v in m.items())
        radius = next((r["px"] for r in self.d["shape"]["radius"] if r["name"] in ("lg", "md")), 12)
        return ("/* shadcn/ui theme generated from brand.json. Paste into your global CSS (replaces the :root/.dark blocks). */\n"
                f":root {{\n  --radius: {radius}px;\n{block('light')}\n  --line: var(--foreground);\n}}\n"
                f".dark {{\n{block('dark')}\n}}\n"
                "/* Surfaces keep ink lines in both shells */\n[data-slot=card], .card { --line: var(--card-foreground); }\n")

    def tailwind3(self):
        roles = list(self.roles("light"))
        colors = ",\n".join(f'        "{r}": "var(--{r})"' for r in roles + ["line"])
        radius = ",\n".join(f'        "{r["name"]}": "{r["px"]}px"' for r in self.d["shape"]["radius"])
        shadow = ",\n".join(f'        "{l["name"]}": "{self.shadow(l)}"' for l in self.levels)
        fonts = ",\n".join(f'        {k}: ["var(--font-{k})"]' for k in ("display", "body", "mono"))
        return ("// Tailwind v3 — load tokens.css globally, then spread this into tailwind.config.js\n"
                "module.exports = {\n  darkMode: 'class',\n  theme: {\n    extend: {\n"
                f"      colors: {{\n{colors}\n      }},\n      borderRadius: {{\n{radius}\n      }},\n"
                f"      boxShadow: {{\n{shadow}\n      }},\n      fontFamily: {{\n{fonts}\n      }},\n"
                "    },\n  },\n};\n")


EXPORTERS = {"dtcg": ("tokens.json", "dtcg"), "css": ("tokens.css", "css"), "tailwind4": ("tailwind4.css", "tailwind4"),
             "shadcn": ("shadcn.css", "shadcn"), "tailwind3": ("tailwind3.js", "tailwind3"),
             "flutter": ("brand_theme.dart", "flutter"), "swift": ("BrandTheme.swift", "swift"),
             "compose": ("BrandTheme.kt", "compose"), "rn": ("theme.ts", "rn")}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--only", nargs="*", choices=list(EXPORTERS))
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.brand)), "tokens")
    os.makedirs(out, exist_ok=True)
    t = Tokens(a.brand)
    for key in (a.only or EXPORTERS):
        fname, meth = EXPORTERS[key]
        open(os.path.join(out, fname), "w", encoding="utf-8").write(getattr(t, meth)())
        print("wrote", os.path.join(out, fname))
