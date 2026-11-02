/** Who's using the app: a guest (an anonymous profile kept by this device's session) or a member
 * signed in with Apple or Google. Until there's a session the app shows the sign-in screen. */
import { useQueryClient } from '@tanstack/react-query';
import { createContext, type PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Platform } from 'react-native';

import { api, authFetch, type Me, onSessionLost, setSessionToken, type SignedIn, unwrap } from '@/api/client';
import { readToken, writeToken } from '@/state/session-storage';

type Status = 'loading' | 'signedOut' | 'signedIn';

type Session = {
  status: Status;
  user: Me | null;
  continueAsGuest: () => Promise<void>;
  signInWithApple: (identityToken: string, name?: string | null) => Promise<void>;
  signInWithGoogle: (idToken: string) => Promise<void>;
  signInDev: (email: string) => Promise<void>;
  signOut: (everywhere?: boolean) => Promise<void>;
  deleteAccount: () => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: PropsWithChildren) {
  const queries = useQueryClient();
  const [status, setStatus] = useState<Status>('loading');
  const [user, setUser] = useState<Me | null>(null);

  const forget = useCallback(() => {
    setSessionToken(null);
    void writeToken(null);
    setUser(null);
    setStatus('signedOut');
    queries.clear(); // the next person sees nothing of this one's
  }, [queries]);

  // On start: a saved token (phones) or the cookie (web) may still be good.
  useEffect(() => {
    onSessionLost(forget);
    let live = true;
    (async () => {
      const token = await readToken();
      setSessionToken(token);
      const { data } = await api.GET('/me').catch(() => ({ data: undefined }));
      if (!live) return;
      if (data) {
        setUser(data);
        setStatus('signedIn');
      } else {
        forget();
      }
    })();
    return () => {
      live = false;
    };
  }, [forget]);

  const start = useCallback(
    async (call: Promise<{ data?: SignedIn; error?: unknown; response: Response }>) => {
      const out = await unwrap(call);
      if (Platform.OS !== 'web' && out.token) {
        // Only the native app gets a token; on web the session is an HttpOnly cookie.
        setSessionToken(out.token);
        await writeToken(out.token);
      }
      queries.clear(); // a guest who signed in may now be someone else (a merged account)
      setUser(out.user);
      setStatus('signedIn');
    },
    [queries],
  );

  const value = useMemo<Session>(
    () => ({
      status,
      user,
      continueAsGuest: () => start(api.POST('/auth/guest')),
      signInWithApple: (identityToken, name) => start(api.POST('/auth/apple', { body: { identity_token: identityToken, name } })),
      signInWithGoogle: (idToken) => start(api.POST('/auth/google', { body: { id_token: idToken } })),
      // Not in the API spec (development only), so a plain request.
      signInDev: (email) =>
        start(
          authFetch('/auth/dev', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
          }).then(async (response) => {
            const body = await response.json().catch(() => undefined);
            return response.ok ? { data: body as SignedIn, response } : { error: body, response };
          }),
        ),
      // Only forgets the session once the API has ended it: on web the cookie would otherwise
      // stay valid while the app looked signed out.
      signOut: async (everywhere = false) => {
        await unwrap(api.POST('/auth/logout', { params: { query: { everywhere } } }));
        forget();
      },
      deleteAccount: async () => {
        await unwrap(api.DELETE('/me'));
        forget();
      },
    }),
    [status, user, start, forget],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error('useSession must be used inside <SessionProvider>');
  return session;
}
