/** "Continue with Google" on web: Google Identity Services' own button (the native library has no
 * free web version). Needs EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID, with this site's origin added to that
 * client in the Google Cloud console; hidden until it's set. */
import { useEffect, useRef } from 'react';
import { View } from 'react-native';

import { useColorScheme } from '@/hooks/use-color-scheme';

const WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
export const GOOGLE_READY = Boolean(WEB_CLIENT_ID);
const SCRIPT = 'https://accounts.google.com/gsi/client';

type Gis = {
  accounts: {
    id: {
      initialize: (o: { client_id: string; callback: (r: { credential?: string }) => void }) => void;
      renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
    };
  };
};

function loadGis(): Promise<Gis> {
  const w = window as unknown as { google?: Gis };
  if (w.google?.accounts) return Promise.resolve(w.google);
  return new Promise((resolve, reject) => {
    const tag = document.createElement('script');
    tag.src = SCRIPT;
    tag.async = true;
    tag.onload = () => (w.google ? resolve(w.google) : reject(new Error('Google sign-in failed to load.')));
    tag.onerror = () => reject(new Error('Google sign-in failed to load.'));
    document.head.appendChild(tag);
  });
}

export function GoogleButton({ onToken, onError }: { onToken: (idToken: string) => void; onError: (message: string) => void }) {
  const ref = useRef<HTMLElement | null>(null);
  const dark = useColorScheme() === 'dark';
  useEffect(() => {
    if (!GOOGLE_READY) return;
    let live = true;
    loadGis()
      .then((google) => {
        const el = ref.current;
        if (!live || !el) return;
        google.accounts.id.initialize({
          client_id: WEB_CLIENT_ID!,
          callback: (r) => (r.credential ? onToken(r.credential) : onError('Google sent no ID token.')),
        });
        el.innerHTML = '';
        google.accounts.id.renderButton(el, {
          type: 'standard',
          shape: 'pill',
          size: 'large',
          text: 'continue_with',
          theme: dark ? 'filled_black' : 'outline',
        });
      })
      .catch((err: Error) => onError(err.message));
    return () => {
      live = false;
    };
  }, [dark, onToken, onError]);
  if (!GOOGLE_READY) return null;
  return <View ref={(node) => { ref.current = node as unknown as HTMLElement | null; }} />; // a div on web
}
