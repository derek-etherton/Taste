import { useSyncExternalStore } from 'react';
import { useColorScheme as useSystemColorScheme } from 'react-native';

import { useChosenScheme } from '@/state/appearance';

const subscribe = () => () => {};

/**
 * The appearance in effect: the one chosen with the toggle, else the browser's. Light during any
 * server/static rendering.
 */
export function useColorScheme() {
  const inBrowser = useSyncExternalStore(subscribe, () => true, () => false);
  const system = useSystemColorScheme();
  const chosen = useChosenScheme();
  return inBrowser ? (chosen ?? system) : 'light';
}
