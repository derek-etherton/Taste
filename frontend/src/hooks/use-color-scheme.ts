import { useColorScheme as useSystemColorScheme } from 'react-native';

import { useChosenScheme } from '@/state/appearance';

/** The appearance in effect: the one chosen with the toggle, else the system's. */
export function useColorScheme() {
  const system = useSystemColorScheme();
  return useChosenScheme() ?? system;
}
