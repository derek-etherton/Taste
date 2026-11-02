/** Server state, via TanStack Query. Everything about the user is under /me (the session says who);
 * query keys start with the user's id so a different person never sees cached data. */
import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ImagePickerAsset } from 'expo-image-picker';
import { Platform } from 'react-native';

import { API_URL, api, authFetch, errorMessage, type ItemCard, type ItemDetail, type Rating, type ShelfScan, unwrap } from './client';

export const PAGE_SIZE = 25;
export type Mode = 'for_you' | 'rate';

export function useSummary(user: string) {
  return useQuery({
    queryKey: [user, 'summary'],
    queryFn: () => unwrap(api.GET('/me/summary')),
  });
}

export function useItems(user: string, domain: string, mode: Mode, q: string, quality: number, tags: string[] = []) {
  return useInfiniteQuery({
    queryKey: [user, 'items', domain, mode, q, quality, tags],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET('/me/{domain}/items', {
          params: { path: { domain }, query: { mode, q, quality, tags, page: pageParam, page_size: PAGE_SIZE } },
        }),
      ),
    getNextPageParam: (last) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
    placeholderData: keepPreviousData, // keep the old list on screen while a new search loads
  });
}

/** What a domain's list can be filtered by: its genome's tags, alphabetical. */
export function useTags(domain: string) {
  return useQuery({
    queryKey: ['tags', domain],
    queryFn: () => unwrap(api.GET('/domains/{domain}/tags', { params: { path: { domain } } })),
    staleTime: Infinity, // changes only when the genome is switched, which invalidates everything
  });
}

export function useRated(user: string, domain: string, quality: number) {
  return useQuery({
    queryKey: [user, 'rated', domain, quality],
    queryFn: () =>
      unwrap(api.GET('/me/{domain}/rated', { params: { path: { domain }, query: { quality } } })),
  });
}

/** An item's page. The domain is the key's prefix ("book:115"). */
export function useItem(user: string, key: string, quality: number) {
  const domain = key.split(':')[0];
  return useQuery({
    queryKey: [user, 'item', key, quality],
    queryFn: () =>
      unwrap(
        api.GET('/me/{domain}/items/{key}', {
          params: { path: { domain, key }, query: { quality } },
        }),
      ),
  });
}

export function useExplanation(user: string, domain: string, key: string | null, quality: number) {
  return useQuery({
    queryKey: [user, 'explanation', domain, key, quality],
    enabled: key !== null,
    queryFn: () =>
      unwrap(
        api.GET('/me/{domain}/items/{key}/explanation', {
          params: { path: { domain, key: key! }, query: { quality } },
        }),
      ),
  });
}

/** Mark `key` as rated `value` in every cached list of cards, so buttons respond instantly. */
function setRatedEverywhere(client: ReturnType<typeof useQueryClient>, user: string, key: string, value: Rating | null) {
  const patch = (c: ItemCard) => (c.key === key ? { ...c, rated: value } : c);
  client.setQueriesData({ queryKey: [user] }, (data: unknown) => {
    if (!data || typeof data !== 'object') return data;
    if ('pages' in data) {
      const d = data as { pages: { items: ItemCard[] }[] };
      return { ...d, pages: d.pages.map((p) => ({ ...p, items: p.items.map(patch) })) };
    }
    if (Array.isArray(data)) return (data as ItemCard[]).map((c) => (c?.key ? patch(c) : c));
    if ('card' in data && 'related' in data) {
      const d = data as ItemDetail;
      return { ...d, card: patch(d.card), related: d.related.map(patch) };
    }
    if ('books' in data) {
      const s = data as ShelfScan;
      return { ...s, books: (s.books ?? []).map(patch) };
    }
    return data;
  });
}

/** Rate an item; giving it the rating it already has clears it. */
export function useRate(user: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value, current }: { key: string; value: Rating; current: Rating | null }) =>
      current === value
        ? unwrap(api.DELETE('/me/ratings/{key}', { params: { path: { key } } }))
        : unwrap(api.PUT('/me/ratings/{key}', { params: { path: { key } }, body: { value } })),
    onMutate: ({ key, value, current }) => setRatedEverywhere(client, user, key, current === value ? null : value),
    onSettled: () => client.invalidateQueries({ queryKey: [user] }),
  });
}

export function useProfile(user: string) {
  return useQuery({
    queryKey: [user, 'profile'],
    queryFn: () => unwrap(api.GET('/me/profile')),
  });
}

/** The latest shelf scan. */
export function useScan(user: string, quality: number) {
  return useQuery({
    queryKey: [user, 'scan', quality],
    queryFn: () => unwrap(api.GET('/me/shelf-scan', { params: { query: { quality } } })),
  });
}

/** The scan photo's address: the API hands out a signed link (an <Image> can't send the session). */
export function scanImageUrl(imageUrl: string | null | undefined): string | null {
  return imageUrl ? `${API_URL}${imageUrl}` : null;
}

/** Upload a photo and read it: one request (20-40 s) that answers with the scan, which is then the
 * latest. Multipart bodies differ: a File on web, {uri, name, type} on native. */
export function useStartScan(user: string, quality: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (photo: ImagePickerAsset) => {
      const name = photo.fileName ?? 'shelf.jpg';
      const form = new FormData();
      if (Platform.OS === 'web' && photo.file) {
        form.append('photo', photo.file, name);
      } else {
        form.append('photo', { uri: photo.uri, name, type: photo.mimeType ?? 'image/jpeg' } as unknown as Blob);
      }
      const response = await authFetch(`/me/shelf-scans?quality=${quality}`, { method: 'POST', body: form });
      if (!response.ok) throw new Error(errorMessage(await response.json().catch(() => undefined), response));
      return (await response.json()) as ShelfScan;
    },
    onSuccess: (scan) => {
      client.setQueryData([user, 'scan', quality], scan);
      void client.invalidateQueries({ queryKey: [user, 'scan'] }); // other qualities, if any
    },
  });
}
