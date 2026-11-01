/** Where the chosen light/dark appearance is saved on web: localStorage, read synchronously so the
 * first paint already has it (no flash of the other appearance). */
export const KEY = 'taste.appearance';

export function readNow(): string | null {
  try {
    return globalThis.localStorage?.getItem(KEY) ?? null;
  } catch {
    return null; // private mode, blocked storage
  }
}

export function read(): Promise<string | null> {
  return Promise.resolve(readNow());
}

export function write(value: string): void {
  try {
    globalThis.localStorage?.setItem(KEY, value);
  } catch {
    // not saved: the choice still holds until the page reloads
  }
}
