/** App-wide choices. One profile and one domain for now, and no weight on general quality
 * (other readers' ratings): scores are pure taste match. The API keeps users, domains and its
 * `quality` parameter, so bringing them back is a UI change. */
import { createContext, type PropsWithChildren, useContext } from 'react';

type Settings = {
  user: string;
  domain: string;
  quality: number;
};

const SETTINGS: Settings = { user: 'main', domain: 'book', quality: 0 };

const SettingsContext = createContext<Settings>(SETTINGS);

export function SettingsProvider({ children }: PropsWithChildren) {
  return <SettingsContext.Provider value={SETTINGS}>{children}</SettingsContext.Provider>;
}

export function useSettings(): Settings {
  return useContext(SettingsContext);
}
