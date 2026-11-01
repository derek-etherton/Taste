/**
 * The brand palette: the only colours that aren't Apple's system colours.
 *
 * To swap it: paste a new palette into `palette` (e.g. the "CSS HEX" export from coolors.co,
 * any names), then point the three roles at its colours. theme.ts derives everything else,
 * including light and dark variants with enough contrast, so a pale colour still works as an
 * accent.
 */

export const palette = {
  azureMist: '#CEE0DC',
  paleSky: '#B9CFD4',
  lilacAsh: '#AFAAB9',
  oldRose: '#B48291',
  cherryRose: '#A5243D',
} as const;

export const roles = {
  /** The app's tint (Apple's "accent colour"): buttons, selection, links, controls, slider. */
  accent: palette.cherryRose,
  /** A second hue that pairs with the accent in charts: tags pulling a score up (the accent
   * marks those pushing it down). */
  secondary: palette.paleSky,
  /** Quiet decoration: empty cover placeholders. */
  surfaceTint: palette.azureMist,
};
