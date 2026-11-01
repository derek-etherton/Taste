/** App-wide choices: the weight on general quality (set on Profile). One profile and one domain
 * for now: the API keeps users and domains, so bringing them back is a UI change. */
import { createContext, type PropsWithChildren, useContext, useMemo, useState } from 'react';

type Settings = {
  user: string;
  domain: string;
  quality: number;
  setQuality: (quality: number) => void;
};

const USER = 'main';
const DOMAIN = 'book';

const SettingsContext = createContext<Settings | null>(null);

export function SettingsProvider({ children }: PropsWithChildren) {
  const [quality, setQuality] = useState(0.1);
  const value = useMemo(() => ({ user: USER, domain: DOMAIN, quality, setQuality }), [quality]);
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): Settings {
  const settings = useContext(SettingsContext);
  if (!settings) throw new Error('useSettings must be used inside <SettingsProvider>');
  return settings;
}
