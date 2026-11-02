/** On web the session is an HttpOnly cookie the API sets: page scripts can't read it (so a
 * script injected into the page can't steal it), and there's nothing to keep here. */
export function readToken(): Promise<string | null> {
  return Promise.resolve(null);
}

export function writeToken(_token: string | null): Promise<void> {
  return Promise.resolve();
}
