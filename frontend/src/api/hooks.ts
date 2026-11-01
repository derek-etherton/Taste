/** Server state, via TanStack Query. Query keys start with the user so switching profile is clean. */
import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ImagePickerAsset } from 'expo-image-picker';
import { Platform } from 'react-native';

import { API_URL, api, errorMessage, type ItemCard, type ItemDetail, type Rating, type ShelfScan, unwrap } from './client';

export const PAGE_SIZE = 25;
export type Mode = 'for_you' | 'rate';

export function useProfiles() {
  return useQuery({ queryKey: ['profiles'], queryFn: () => unwrap(api.GET('/profiles')) });
}

/** Each domain's genomes. Server-wide, so not under a user. */
export function useGenomes() {
  return useQuery({ queryKey: ['genomes'], queryFn: () => unwrap(api.GET('/genomes')) });
}

/** Switch a domain's genome on the server. Every catalogue-derived list changes, so refetch all. */
export function useSwitchGenome() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ domain, genome }: { domain: string; genome: string }) =>
      unwrap(api.PUT('/genomes/{domain}', { params: { path: { domain } }, body: { genome } })),
    onSuccess: () => client.invalidateQueries(),
  });
}

export function useSummary(user: string) {
  return useQuery({
    queryKey: [user, 'summary'],
    queryFn: () => unwrap(api.GET('/profiles/{user}', { params: { path: { user } } })),
  });
}

export function useItems(user: string, domain: string, mode: Mode, q: string, quality: number, tags: string[] = []) {
  return useInfiniteQuery({
    queryKey: [user, 'items', domain, mode, q, quality, tags],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET('/profiles/{user}/{domain}/items', {
          params: { path: { user, domain }, query: { mode, q, quality, tags, page: pageParam, page_size: PAGE_SIZE } },
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
      unwrap(api.GET('/profiles/{user}/{domain}/rated', { params: { path: { user, domain }, query: { quality } } })),
  });
}

/** An item's page. The domain is the key's prefix ("book:115"). */
export function useItem(user: string, key: string, quality: number) {
  const domain = key.split(':')[0];
  return useQuery({
    queryKey: [user, 'item', key, quality],
    queryFn: () =>
      unwrap(
        api.GET('/profiles/{user}/{domain}/items/{key}', {
          params: { path: { user, domain, key }, query: { quality } },
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
        api.GET('/profiles/{user}/{domain}/items/{key}/explanation', {
          params: { path: { user, domain, key: key! }, query: { quality } },
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
        ? unwrap(api.DELETE('/profiles/{user}/ratings/{key}', { params: { path: { user, key } } }))
        : unwrap(api.PUT('/profiles/{user}/ratings/{key}', { params: { path: { user, key } }, body: { value } })),
    onMutate: ({ key, value, current }) => setRatedEverywhere(client, user, key, current === value ? null : value),
    onSettled: () => client.invalidateQueries({ queryKey: [user] }),
  });
}

export function useProfile(user: string) {
  return useQuery({
    queryKey: [user, 'profile'],
    queryFn: () => unwrap(api.GET('/profiles/{user}/profile', { params: { path: { user } } })),
  });
}

export function useDescription(user: string) {
  return useQuery({
    queryKey: [user, 'description'],
    queryFn: () => unwrap(api.GET('/profiles/{user}/description', { params: { path: { user } } })),
  });
}

export function useDescribe(user: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST('/profiles/{user}/description', { params: { path: { user } } })),
    onSuccess: (d) => client.setQueryData([user, 'description'], d),
  });
}

/** The latest shelf scan; polled every 2 s while one is running. */
export function useScan(user: string, quality: number) {
  return useQuery({
    queryKey: [user, 'scan', quality],
    queryFn: () =>
      unwrap(api.GET('/profiles/{user}/shelf-scan', { params: { path: { user }, query: { quality } } })),
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 2000 : false),
  });
}

export function scanImageUrl(user: string, scanned: string | null | undefined): string {
  return `${API_URL}/profiles/${user}/shelf-scan/image?v=${encodeURIComponent(scanned ?? '')}`;
}

/** Upload a photo and start a scan. Multipart bodies differ: a File on web, {uri, name, type} on native. */
export function useStartScan(user: string) {
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
      const response = await fetch(`${API_URL}/profiles/${user}/shelf-scans`, { method: 'POST', body: form });
      if (!response.ok) throw new Error(errorMessage(await response.json().catch(() => undefined), response));
      return (await response.json()) as ShelfScan;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [user, 'scan'] }),
  });
}
