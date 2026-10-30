import { useSyncExternalStore } from 'react';
import { useColorScheme as useRNColorScheme } from 'react-native';

const subscribe = () => () => {};

/**
 * Light during any server/static rendering, the real scheme once running in the browser.
 */
export function useColorScheme() {
  const inBrowser = useSyncExternalStore(subscribe, () => true, () => false);
  const colorScheme = useRNColorScheme();
  return inBrowser ? colorScheme : 'light';
}
