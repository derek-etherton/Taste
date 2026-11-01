/** Discover: book recommendations ("For you"), the most useful books to rate ("Rate"), and your ratings. */
import { useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, TextInput, View } from 'react-native';

import type { ItemCard } from '@/api/client';
import { type Mode, useItems, useRated, useSummary } from '@/api/hooks';
import { ExplanationSheet } from '@/components/explanation-sheet';
import { ItemRow } from '@/components/item-row';
import { Chips, Loading, Note, Screen, listPadding } from '@/components/kit';
import { TagFilter } from '@/components/tag-filter';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

type View_ = Mode | 'rated';

function useDebounced<T>(value: T, ms = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export default function Discover() {
  const { user, domain, quality } = useSettings();
  const theme = useTheme();
  const summary = useSummary(user);
  const [view, setView] = useState<View_>('for_you');
  const [text, setText] = useState('');
  const q = useDebounced(text.trim());
  const [explaining, setExplaining] = useState<ItemCard | null>(null);
  const [tags, setTags] = useState<string[]>([]);

  const items = useItems(user, domain, view === 'rated' ? 'for_you' : view, q, quality, tags);
  const rated = useRated(user, domain, quality);
  const name = 'Books';
  const thisDomain = summary.data?.find((d) => d.domain === domain);

  const pages = items.data?.pages;
  const source = pages?.[0]?.source ?? '';
  const data: ItemCard[] = useMemo(
    () => (view === 'rated' ? (rated.data ?? []) : (pages?.flatMap((p) => p.items) ?? [])),
    [view, rated.data, pages],
  );
  const loading = view === 'rated' ? rated.isPending : items.isPending;
  const error = view === 'rated' ? rated.error : items.error;

  const header = (
    <View style={styles.header}>
      {thisDomain && (
        <ThemedText type="small" themeColor="textSecondary">
          {thisDomain.confidence}
        </ThemedText>
      )}
      <Chips
        options={[
          { value: 'for_you', label: 'For you' },
          { value: 'rate', label: `Rate ${name.toLowerCase()}` },
          { value: 'rated', label: `Your ratings${rated.data ? ` (${rated.data.length})` : ''}` },
        ]}
        value={view}
        onChange={(v) => setView(v as View_)}
      />
      {view !== 'rated' && (
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder={`Search ${name.toLowerCase()} by title or name…`}
          placeholderTextColor={theme.textSecondary}
          autoCorrect={false}
          style={[styles.search, { backgroundColor: theme.backgroundElement, color: theme.text }]}
        />
      )}
      {view !== 'rated' && <TagFilter domain={domain} value={tags} onChange={setTags} />}
      {view === 'for_you' && !q && thisDomain?.rated === 0 && !source && (
        <Note>{`Rate a few ${name.toLowerCase()}. Until then this is just the best-rated overall.`}</Note>
      )}
      {view === 'rate' && !q && (
        <Note>{`Well-known ${name.toLowerCase()} your profile knows least about, spread across different kinds. Rating these teaches it the most.`}</Note>
      )}
      {error && <Note tone="error">{error.message}</Note>}
    </View>
  );

  return (
    <Screen>
      <FlatList
        data={data}
        keyExtractor={(c) => c.key}
        renderItem={({ item, index }) => (
          <ItemRow item={item} rank={view === 'rated' || q ? undefined : index + 1} source={source} onExplain={setExplaining} />
        )}
        ListHeaderComponent={header}
        ListEmptyComponent={loading ? <Loading /> : <Note>{q ? 'No matches.' : 'Nothing here yet.'}</Note>}
        ListFooterComponent={items.isFetchingNextPage ? <Loading /> : undefined}
        onEndReached={() => view !== 'rated' && items.hasNextPage && !items.isFetchingNextPage && items.fetchNextPage()}
        onEndReachedThreshold={0.5}
        contentContainerStyle={listPadding}
        keyboardShouldPersistTaps="handled"
      />
      <ExplanationSheet domain={domain} item={explaining} source={source} onClose={() => setExplaining(null)} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { gap: Spacing.three, paddingBottom: Spacing.two },
  search: { paddingHorizontal: Spacing.three, paddingVertical: Spacing.two + 2, borderRadius: Spacing.three, fontSize: 16 },
});
