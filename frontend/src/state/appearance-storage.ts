/** Where the chosen light/dark appearance is saved on phones: AsyncStorage (read once, at start). */
import AsyncStorage from '@react-native-async-storage/async-storage';

export const KEY = 'taste.appearance';

export function readNow(): string | null {
  return null; // AsyncStorage is asynchronous: see read()
}

export function read(): Promise<string | null> {
  return AsyncStorage.getItem(KEY).catch(() => null);
}

export function write(value: string): void {
  AsyncStorage.setItem(KEY, value).catch(() => {});
}
