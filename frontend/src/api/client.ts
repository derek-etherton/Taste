/**
 * The backend API. Types come from the backend's OpenAPI spec:
 *   (in backend/) python scripts/export_openapi.py   then   (in frontend/) npm run api:types
 *
 * EXPO_PUBLIC_API_URL points the app at the backend. On a phone that's the PC's LAN address,
 * e.g. http://192.168.1.20:8000, since "localhost" is the phone itself.
 */
import createClient, { type Middleware } from 'openapi-fetch';

import type { components, paths } from './schema';

export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

/** Who's signed in. Phones send the session token as a bearer header; the web app's session is
 * an HttpOnly cookie, sent because every request includes credentials. */
let token: string | null = null;
let onSignedOut: () => void = () => {};

export function setSessionToken(t: string | null) {
  token = t;
}

/** Called when the API says the session is gone (expired, signed out elsewhere, account deleted). */
export function onSessionLost(handler: () => void) {
  onSignedOut = handler;
}

const session: Middleware = {
  onRequest({ request }) {
    if (token) request.headers.set('Authorization', `Bearer ${token}`);
    return request;
  },
  onResponse({ response, request }) {
    if (response.status === 401 && !new URL(request.url).pathname.startsWith('/auth/')) onSignedOut();
    return response;
  },
};

export const api = createClient<paths>({ baseUrl: API_URL, credentials: 'include' });
api.use(session);

/** fetch() for the few calls openapi-fetch can't make (multipart uploads), with the session. */
export function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(`${API_URL}${path}`, { ...init, headers, credentials: 'include' }).then((r) => {
    if (r.status === 401) onSignedOut();
    return r;
  });
}

type Schemas = components['schemas'];
export type ItemCard = Schemas['ItemCard'];
export type ItemPage = Schemas['ItemPage'];
export type ItemDetail = Schemas['ItemDetail'];
export type TagStrength = Schemas['TagStrength'];
export type TagContribution = Schemas['TagContribution'];
export type Explanation = Schemas['Explanation'];
export type Profile = Schemas['Profile'];
export type Claims = Schemas['Claims'];
export type Claim = Schemas['Claim'];
export type ShelfScan = Schemas['ShelfScan'];
export type DomainSummary = Schemas['DomainSummary'];
export type BookInfo = Schemas['BookInfo'];
export type Me = Schemas['Me'];
export type SignedIn = Schemas['SignedIn'];
export type Rating = -1 | 0 | 1;

/** The message to show for a failed request: FastAPI's `detail`, or the HTTP status. */
export function errorMessage(error: unknown, response?: Response): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join('; ');
  return response ? `${response.status} ${response.statusText}` : String(error);
}

/** The data of an openapi-fetch call, or a thrown Error with a readable message. */
export async function unwrap<T>(call: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined || !response.ok) throw new Error(errorMessage(error, response));
  return data as T;
}
