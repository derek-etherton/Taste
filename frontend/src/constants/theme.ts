/**
 * Colours, type and spacing, after Apple's Human Interface Guidelines.
 *
 * Everything but the brand colours is an iOS system colour, in its light and dark variant:
 * grouped backgrounds, labels, separators and fills. The brand colours come from palette.ts and
 * are adjusted here for contrast in each appearance, the way Apple's own system colours shift
 * between light and dark.
 */

import '@/global.css';

import { Platform } from 'react-native';

import { alpha, contrast, forChart, onSurface } from '@/constants/color';
import { roles } from '@/constants/palette';

// --- the themes ---------------------------------------------------------------------------

const SYSTEM = {
  light: {
    background: '#FFFFFF', // systemBackground: sheets
    groupedBackground: '#F2F2F7', // systemGroupedBackground: behind grouped lists
    card: '#FFFFFF', // secondarySystemGroupedBackground: the grouped rows themselves
    label: '#000000',
    secondaryLabel: 'rgba(60, 60, 67, 0.6)',
    tertiaryLabel: 'rgba(60, 60, 67, 0.3)',
    separator: 'rgba(60, 60, 67, 0.29)',
    fill: 'rgba(118, 118, 128, 0.12)', // tertiarySystemFill: search fields, idle buttons
    destructive: '#FF3B30', // systemRed
    neutral: '#8E8E93', // systemGray: the neutral midpoint of diverging charts (meh)
  },
  dark: {
    background: '#1C1C1E',
    groupedBackground: '#000000',
    card: '#1C1C1E',
    label: '#FFFFFF',
    secondaryLabel: 'rgba(235, 235, 245, 0.6)',
    tertiaryLabel: 'rgba(235, 235, 245, 0.3)',
    separator: 'rgba(84, 84, 88, 0.65)',
    fill: 'rgba(118, 118, 128, 0.24)',
    destructive: '#FF453A',
    neutral: '#8E8E93',
  },
} as const;

function brand(scheme: 'light' | 'dark') {
  const s = SYSTEM[scheme];
  const accent = onSurface(roles.accent, s.card, 4.5); // text contrast: it colours links and labels
  // Filled buttons keep a deep fill with a white label in both appearances, as Apple's do.
  const button = onSurface(roles.accent, '#FFFFFF', 4.5);
  return {
    accent,
    accentFill: alpha(accent, scheme === 'light' ? 0.12 : 0.24), // "tinted" controls
    button,
    onButton: contrast('#FFFFFF', button) >= 4.5 ? '#FFFFFF' : '#000000',
    // Charts: a diverging pair, checked with the dataviz palette validator for both appearances.
    chartUp: forChart(roles.secondary, s.card),
    chartDown: forChart(roles.accent, s.card),
    placeholder: scheme === 'light' ? roles.surfaceTint : alpha(roles.surfaceTint, 0.16),
  };
}

export const Colors = {
  light: { ...SYSTEM.light, ...brand('light') },
  dark: { ...SYSTEM.dark, ...brand('dark') },
};

export type ThemeColor = keyof typeof Colors.light;

// --- type, after Apple's text styles (sizes in points, at the default Dynamic Type size) ---

const family = Platform.select({
  web: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif',
  default: undefined, // the system font: SF Pro on iOS, Roboto on Android
});

export const Type = {
  largeTitle: { fontFamily: family, fontSize: 34, lineHeight: 41, fontWeight: '700' },
  title1: { fontFamily: family, fontSize: 28, lineHeight: 34, fontWeight: '700' },
  title2: { fontFamily: family, fontSize: 22, lineHeight: 28, fontWeight: '700' },
  title3: { fontFamily: family, fontSize: 20, lineHeight: 25, fontWeight: '600' },
  headline: { fontFamily: family, fontSize: 17, lineHeight: 22, fontWeight: '600' },
  body: { fontFamily: family, fontSize: 17, lineHeight: 22, fontWeight: '400' },
  callout: { fontFamily: family, fontSize: 16, lineHeight: 21, fontWeight: '400' },
  subheadline: { fontFamily: family, fontSize: 15, lineHeight: 20, fontWeight: '400' },
  footnote: { fontFamily: family, fontSize: 13, lineHeight: 18, fontWeight: '400' },
  caption: { fontFamily: family, fontSize: 12, lineHeight: 16, fontWeight: '400' },
} as const;

export type TextStyleName = keyof typeof Type;

// --- layout -------------------------------------------------------------------------------

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const Radius = {
  cover: 4,
  field: 10, // search fields, small controls
  card: 12, // grouped lists and cards
  sheet: 14,
  capsule: 999, // buttons
} as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 720;
