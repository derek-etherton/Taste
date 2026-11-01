/** Colour maths for the theme: WCAG contrast, and nudging a colour's lightness until it has enough. */

type RGB = [number, number, number];

function rgb(hex: string): RGB {
  const h = hex.replace('#', '').slice(0, 6);
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as RGB;
}

function luminance(hex: string): number {
  const [r, g, b] = rgb(hex).map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function toHsl([r, g, b]: RGB): RGB {
  const [R, G, B] = [r / 255, g / 255, b / 255];
  const max = Math.max(R, G, B);
  const min = Math.min(R, G, B);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  const h = max === R ? (G - B) / d + (G < B ? 6 : 0) : max === G ? (B - R) / d + 2 : (R - G) / d + 4;
  return [h / 6, s, l];
}

function fromHsl([h, s, l]: RGB): string {
  const f = (n: number) => {
    const k = (n + h * 12) % 12;
    const a = s * Math.min(l, 1 - l);
    return Math.round(255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))));
  };
  return `#${[f(0), f(8), f(4)].map((c) => c.toString(16).padStart(2, '0')).join('')}`.toUpperCase();
}

/** `hex`, made darker or lighter (whichever moves away from `surface`) until it has `min`
 * contrast against it. Hue and saturation stay. */
export function onSurface(hex: string, surface: string, min: number): string {
  const [h, s, l0] = toHsl(rgb(hex));
  const darken = luminance(surface) > 0.5;
  let out = hex;
  for (let l = l0; contrast(out, surface) < min && l >= 0 && l <= 1; l += darken ? -0.01 : 0.01) {
    out = fromHsl([h, s, l]);
  }
  return out;
}

export function alpha(hex: string, a: number): string {
  const [r, g, b] = rgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

/** A colour for chart marks: `hex`'s hue, saturated enough not to read as grey, and only as
 * far from mid-lightness as it takes to have `min` contrast against `surface` (on dark
 * surfaces, starting darker, so marks don't glare). Checked with the dataviz validator. */
export function forChart(hex: string, surface: string, min = 3.2): string {
  const [h, s] = toHsl(rgb(hex));
  const darken = luminance(surface) > 0.5;
  const sat = Math.max(s, 0.85);
  const start = darken ? 0.5 : 0.4;
  let out = fromHsl([h, sat, start]);
  for (let l = start; contrast(out, surface) < min && l >= 0 && l <= 1; l += darken ? -0.01 : 0.01) {
    out = fromHsl([h, sat, l]);
  }
  return out;
}
