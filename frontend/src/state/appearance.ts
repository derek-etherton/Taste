/** The light/dark appearance the user chose with the sun/moon toggle, saved on the device. Until
 * they choose, the app follows the system. */
import { useSyncExternalStore } from 'react';
import { Appearance, Platform } from 'react-native';

import { read, readNow, write } from '@/state/appearance-storage';

export type Scheme = 'light' | 'dark';

const valid = (v: string | null): Scheme | null => (v === 'light' || v === 'dark' ? v : null);

let chosen: Scheme | null = valid(readNow());
const listeners = new Set<() => void>();

function apply(scheme: Scheme) {
  chosen = scheme;
  // On phones this also switches native UI (tab bar, controls, sheets); web has no such setting.
  if (Platform.OS !== 'web') Appearance.setColorScheme(scheme);
  listeners.forEach((l) => l());
}

// Phones read the saved choice asynchronously, just after start.
read().then((saved) => {
  const scheme = valid(saved);
  if (scheme && scheme !== chosen) apply(scheme);
});

export function setScheme(scheme: Scheme) {
  apply(scheme);
  write(scheme);
}

/** The chosen appearance, or null to follow the system. */
export function useChosenScheme(): Scheme | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => chosen,
    () => null,
  );
}
