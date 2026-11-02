/** Where a phone keeps its session token: the iOS Keychain / Android Keystore (expo-secure-store),
 * never plain storage. */
import * as SecureStore from 'expo-secure-store';

const KEY = 'taste.session';

export function readToken(): Promise<string | null> {
  return SecureStore.getItemAsync(KEY).catch(() => null);
}

export function writeToken(token: string | null): Promise<void> {
  return (token ? SecureStore.setItemAsync(KEY, token) : SecureStore.deleteItemAsync(KEY)).catch(() => {});
}
