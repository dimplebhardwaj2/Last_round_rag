# LAST ROUND — UI/UX Design System ("Aurora")

> The current build is clean but *flat*. This doc defines the upgrade: a premium,
> gradient-rich, depth-driven aesthetic that feels like **Linear × Vercel × Stripe ×
> Arc Browser** — modern, confident, and expensive. Every value here is
> implementation-ready (drop into CSS custom properties).

**Codename:** Aurora · **Mode:** Light-first, gradient-accented · **Date:** 2026-06-16

---

## 1. Why the current UI feels "basic" (and the fix)

| Problem now | Upgrade |
|---|---|
| Flat solid fills, one blue→indigo gradient | A **gradient *system*** — signature aurora, mesh backgrounds, gradient borders, glow |
| Hard white background, no depth | **Layered depth**: soft mesh aurora, frosted glass, multi-layer shadows + glow |
| Uniform card shadows | **Elevation tiers** + colored glows that match the brand |
| Static, no life | **Motion**: animated gradients, hover lift, shimmer, spring easing |
| Generic spacing | Tighter **type scale**, larger headings, more whitespace, bento rhythm |

Design principle: **calm canvas, electric accents.** 90% of the screen is quiet
neutral + glass; gradient is a spotlight used on the 10% that matters (CTAs, hero,
score, the interviewer presence).

---

## 2. Color foundation

### Neutrals (the calm 90%)
```css
--ink:        #0B1020;  /* near-black headings (cool, not pure black) */
--slate-900:  #141A2E;
--slate-700:  #2A3350;
--muted:      #5B6478;  /* secondary text */
--faint:      #8A93A8;  /* tertiary / placeholders */
--line:       #ECE9F5;  /* hairline borders */
--surface:    #FFFFFF;
--surface-2:  #F7F8FC;  /* sunken / sections */
--canvas:     #F4F3FB;  /* page base under the mesh */
```

### Brand spectrum (the electric 10%)
```css
--indigo: #5B5BF5;
--violet: #8B5CF6;
--fuchsia:#D946EF;
--blue:   #3B82F6;
--cyan:   #22D3EE;
--pink:   #EC4899;
```

### Semantic
```css
--success:#16C098;  --warning:#F5A524;  --danger:#F23F5D;
```

---

## 3. The Gradient Catalog ⭐ (this is the "super cool" part)

Named, reusable gradients. Use **Signature** for the hero/CTAs, **Aurora Mesh** for
backgrounds, **Iris** for interactive surfaces.

```css
/* SIGNATURE — primary CTAs, logo, hero text. The brand in one stroke. */
--grad-signature: linear-gradient(135deg, #5B5BF5 0%, #8B5CF6 45%, #D946EF 100%);

/* IRIS — buttons/active states, calmer than signature */
--grad-iris: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);

/* OCEAN — secondary accent (charts, "live" cues) */
--grad-ocean: linear-gradient(135deg, #3B82F6 0%, #22D3EE 100%);

/* SUNSET — celebratory (strong-hire score, success states) */
--grad-sunset: linear-gradient(135deg, #8B5CF6 0%, #EC4899 60%, #F5A524 100%);

/* GLASS SHEEN — subtle highlight on frosted cards */
--grad-sheen: linear-gradient(180deg, rgba(255,255,255,.65), rgba(255,255,255,.15));

/* AURORA MESH — the page background. Multiple radial blobs = depth. */
--mesh:
  radial-gradient(46rem 30rem at 88% -6%,  rgba(139,92,246,.20), transparent 60%),
  radial-gradient(40rem 28rem at -4% 8%,   rgba(59,130,246,.16), transparent 55%),
  radial-gradient(36rem 26rem at 70% 108%, rgba(217,70,239,.12), transparent 60%),
  var(--canvas);

/* CONIC GLOW — for the interviewer orb / score ring rotation */
--grad-conic: conic-gradient(from 180deg, #5B5BF5, #8B5CF6, #D946EF, #3B82F6, #5B5BF5);
```

### Gradient techniques to use
- **Animated gradient** (CTAs, hero word): shift `background-position` on a 200% background → slow living shimmer.
- **Gradient text**: `background: var(--grad-signature); -webkit-background-clip: text; color: transparent;`
- **Gradient border** (premium card edge): double-background trick
  ```css
  border: 1px solid transparent;
  background:
    linear-gradient(#fff,#fff) padding-box,
    var(--grad-signature) border-box;
  ```
- **Glow** (not just shadow): colored, blurred drop under gradient elements
  `box-shadow: 0 20px 50px -16px rgba(124,77,255,.45);`
- **Mesh background**: fixed-attachment `--mesh` on body for an aurora that never tiles.

---

## 4. Depth, glass & elevation

Replace flat cards with **3 elevation tiers** + frosted glass for overlays.

```css
--shadow-1: 0 1px 2px rgba(16,24,40,.04), 0 2px 6px rgba(16,24,40,.05);     /* rest */
--shadow-2: 0 12px 30px -12px rgba(16,24,40,.14);                           /* cards */
--shadow-3: 0 30px 70px -24px rgba(16,24,40,.28);                           /* modals/hero */
--glow-brand: 0 24px 60px -20px rgba(124,77,255,.45);                        /* gradient elems */

/* Frosted glass (overlays, floating chips, question card) */
--glass-bg: rgba(255,255,255,.62);
--glass-bd: rgba(255,255,255,.7);
/* usage: background:var(--glass-bg); backdrop-filter: blur(20px) saturate(180%);
   border:1px solid var(--glass-bd); */
```

Rule: **gradient elements get a glow**, neutral cards get `--shadow-2`, floating things get glass.

---

## 5. Typography

```css
--font: 'Inter', 'SF Pro Display', system-ui, sans-serif;   /* + 'Inter Tight' for display */
```
Scale (clamp = responsive):
```
Display  clamp(2.8rem, 6vw, 4.5rem)   800   tracking -0.035em
H1       2.25rem  800   -0.03em
H2       1.6rem   700   -0.02em
H3       1.15rem  700
Body     1rem     400/500   line-height 1.6
Small    .875rem  500
Label    .75rem   700   uppercase  tracking .08em  (muted)
Mono     'JetBrains Mono'  — timers, scores, metrics
```
- Headlines: large, tight tracking, **one** gradient word.
- Never gradient-fill body text (contrast).

---

## 6. Shape & spacing

```css
--r-sm:10px;  --r:14px;  --r-md:18px;  --r-lg:24px;  --r-xl:32px;  --r-pill:999px;
```
- 8px grid. Section padding 80–120px desktop. Card padding 24–32px.
- Big rounded corners (20–24px) = the premium "soft product" feel.
- Generous whitespace > cramming features.

---

## 7. Components — the elevated treatment

**Primary button**
```
background: --grad-iris (or signature on hero); color:#fff;
radius: --r-md; padding:14px 26px; font-weight:600;
box-shadow:--glow-brand;  hover: translateY(-2px) + brighter glow;
optional: animated gradient (background-position shift on hover).
```
**Secondary** = white + `--shadow-1` + 1px `--line`, hover gradient-tinted border.
**Ghost/Glass** = frosted glass for in-stage controls.

**Card** = white, `--shadow-2`, `--r-lg`; **featured card** = gradient border + `--glow-brand` on hover, lift `-4px`.

**Inputs** = `--surface-2` fill, 1.5px `--line`; focus → gradient-ish ring `0 0 0 4px rgba(91,91,245,.18)` + border `--indigo`.

**Choice chips** = icon tile that fills with `--grad-iris` when active; lift on hover.

**Badges/pills** = soft tinted (`rgba(brand,.1)`); "live" = pulsing dot.

**Progress / meters** = track `--surface-2`, fill `--grad-iris`, rounded caps, animated width.

---

## 8. Backgrounds & texture

1. **Aurora mesh** (`--mesh`) on `body`, `background-attachment: fixed`.
2. **Subtle grain**: 2–4% opacity noise PNG/SVG overlay to kill banding on gradients.
3. **Faint grid** behind hero (`linear-gradient` 1px lines, 3% opacity) for a "product" feel.
4. **Glow blobs**: absolutely-positioned blurred radial divs behind hero/score for atmosphere.

---

## 9. Motion & micro-interactions

```css
--ease: cubic-bezier(.2,.8,.2,1);     /* standard */
--spring: cubic-bezier(.34,1.56,.64,1); /* playful overshoot */
--t-fast:140ms; --t:240ms; --t-slow:480ms;
```
- **Hover lift**: cards/buttons `translateY(-2 to -4px)` + glow, `--t`.
- **Page reveal**: stagger children rise+fade (60–90ms steps).
- **Animated gradient**: `@keyframes drift { background-position 0%→200% }` 8s on hero/CTA.
- **Score ring / radar**: draw-on animation (stroke-dashoffset / canvas tween) `--t-slow`.
- **Interviewer orb**: conic-gradient slow rotate + breathing scale; emit rings while speaking; scale to mic level while listening.
- **Waveform**: smooth bar interpolation (lerp), rounded caps, gradient fill.
- Respect `prefers-reduced-motion` → disable drift/auto-animations.

---

## 10. Iconography & imagery

- **Line icons** (current `icons.js`, Lucide-style), 1.75–2px stroke, `currentColor`.
- Icon tiles: rounded square with soft tinted bg; active → gradient bg, white icon.
- No emoji. No clip-art. **3D/illustrated accents** only as optional hero garnish.
- Avatars: gradient ring around photo/initial; the AI interviewer = gradient orb with conic glow (not a cartoon).

---

## 11. Screen art direction

**Landing** — full-bleed aurora mesh + faint grid; gradient display headline (one word gradient); glass dashboard mockup floating with glow + bobbing glass chips; trust logos at 50% opacity; bento feature grid with gradient-border featured tile.

**Setup** — centered glass card on mesh; gradient progress dots; icon choice-chips that fill with `--grad-iris` when active; live mic meter with gradient fill.

**Interview room** — cinematic: deep-navy stage with internal aurora glow; **gradient orb interviewer** (conic rotate + breathe); frosted-glass question card; glass control dock; right panel on white with gradient progress + glass transcript. The dark stage against the light app chrome = drama.

**Evaluation** — celebratory: big score ring with `--grad-sunset` + confetti-lite; radar chart with gradient fill; criteria bars `--grad-iris`; gradient-border verdict card with glow.

---

## 12. Accessibility (gradients done responsibly)

- Body text stays solid neutral on solid/near-solid bg — **never** gradient text for paragraphs.
- Maintain **4.5:1** contrast for text; pick the darker gradient stop when text sits on gradient.
- White text on `--grad-iris`/signature passes; test the lightest stop.
- Honor `prefers-reduced-motion` and `prefers-contrast`.
- Focus states always visible (gradient-tinted ring).

---

## 13. Drop-in token block (paste into base.css `:root`)

```css
:root{
  --ink:#0B1020; --muted:#5B6478; --faint:#8A93A8; --line:#ECE9F5;
  --surface:#fff; --surface-2:#F7F8FC; --canvas:#F4F3FB;
  --indigo:#5B5BF5; --violet:#8B5CF6; --fuchsia:#D946EF; --blue:#3B82F6; --cyan:#22D3EE;
  --grad-signature:linear-gradient(135deg,#5B5BF5,#8B5CF6 45%,#D946EF);
  --grad-iris:linear-gradient(135deg,#4F46E5,#7C3AED);
  --grad-ocean:linear-gradient(135deg,#3B82F6,#22D3EE);
  --grad-sunset:linear-gradient(135deg,#8B5CF6,#EC4899 60%,#F5A524);
  --grad-conic:conic-gradient(from 180deg,#5B5BF5,#8B5CF6,#D946EF,#3B82F6,#5B5BF5);
  --mesh:radial-gradient(46rem 30rem at 88% -6%,rgba(139,92,246,.20),transparent 60%),
        radial-gradient(40rem 28rem at -4% 8%,rgba(59,130,246,.16),transparent 55%),
        radial-gradient(36rem 26rem at 70% 108%,rgba(217,70,239,.12),transparent 60%),var(--canvas);
  --shadow-1:0 1px 2px rgba(16,24,40,.04),0 2px 6px rgba(16,24,40,.05);
  --shadow-2:0 12px 30px -12px rgba(16,24,40,.14);
  --shadow-3:0 30px 70px -24px rgba(16,24,40,.28);
  --glow-brand:0 24px 60px -20px rgba(124,77,255,.45);
  --glass-bg:rgba(255,255,255,.62); --glass-bd:rgba(255,255,255,.7);
  --r:14px; --r-md:18px; --r-lg:24px; --r-xl:32px; --r-pill:999px;
  --ease:cubic-bezier(.2,.8,.2,1); --spring:cubic-bezier(.34,1.56,.64,1);
  --t-fast:140ms; --t:240ms; --t-slow:480ms;
}
```

---

## 14. Do / Don't

✅ Gradient on hero, CTAs, score, orb, active states, charts.
✅ Glow under gradient elements. Glass for overlays. Mesh on the page.
✅ Big radii, big headings, big whitespace, springy hover.

🚫 Gradient on body text or large backgrounds of text.
🚫 More than ~2 gradient families on one screen.
🚫 Pure-black text or pure-white flat pages (use `--ink` / `--mesh`).
🚫 Harsh shadows without color; banding without grain.

---

## 15. Implementation order

1. Swap `:root` tokens (§13) + add `--mesh` to `body` + grain overlay.
2. Buttons/cards → gradient + glow + glass variants.
3. Landing hero → animated gradient headline + glass mockup + glow blobs.
4. Interview orb → conic-gradient rotate + breathe; glass question card & dock.
5. Evaluation → `--grad-sunset` score ring + gradient radar.
6. Motion pass (hover lift, staggered reveal, reduced-motion guard).
```
