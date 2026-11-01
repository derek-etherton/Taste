/** App-wide choices: which profile, which domain on Discover, and the weight on general quality. */
import { createContext, type PropsWithChildren, useContext, useMemo, useState } from 'react';

type Settings = {
  user: string;
  setUser: (user: string) => void;
  domain: string;
  setDomain: (domain: string) => void;
  quality: number;
  setQuality: (quality: number) => void;
};

const SettingsContext = createContext<Settings | null>(null);

export function SettingsProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState('main');
  const [domain, setDomain] = useState('film');
  const [quality, setQuality] = useState(0.1);
  const value = useMemo(() => ({ user, setUser, domain, setDomain, quality, setQuality }), [user, domain, quality]);
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): Settings {
  const settings = useContext(SettingsContext);
  if (!settings) throw new Error('useSettings must be used inside <SettingsProvider>');
  return settings;
}
