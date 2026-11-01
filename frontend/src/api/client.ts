/**
 * The backend API. Types come from the backend's OpenAPI spec:
 *   (in backend/) python scripts/export_openapi.py   then   (in frontend/) npm run api:types
 *
 * EXPO_PUBLIC_API_URL points the app at the backend. On a phone that's the PC's LAN address,
 * e.g. http://192.168.1.20:8000, since "localhost" is the phone itself.
 */
import createClient from 'openapi-fetch';

import type { components, paths } from './schema';

export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export const api = createClient<paths>({ baseUrl: API_URL });

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
export type Description = Schemas['Description'];
export type ShelfScan = Schemas['ShelfScan'];
export type DomainSummary = Schemas['DomainSummary'];
export type Genomes = Schemas['Genomes'];
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
