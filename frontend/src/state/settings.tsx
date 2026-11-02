/** App-wide choices. The user is whoever's signed in (state/session.tsx); query caches are keyed
 * by their id. One domain for now, and no weight on general quality (other readers' ratings):
 * scores are pure taste match. The API keeps domains and its `quality` parameter, so bringing
 * them back is a UI change. */
import { createContext, type PropsWithChildren, useContext, useMemo } from 'react';

import { useSession } from '@/state/session';

type Settings = {
  user: string;
  domain: string;
  quality: number;
};

const SettingsContext = createContext<Settings>({ user: '', domain: 'book', quality: 0 });

export function SettingsProvider({ children }: PropsWithChildren) {
  const { user } = useSession();
  const value = useMemo(() => ({ user: user?.id ?? '', domain: 'book', quality: 0 }), [user]);
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): Settings {
  return useContext(SettingsContext);
}
