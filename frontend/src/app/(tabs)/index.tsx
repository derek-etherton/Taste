/** Discover: book recommendations, as one inset-grouped list under a large title, with search and
 * the tag filter. (Your ratings are on Profile; the API's "rate" mode isn't shown for now.) */
import { useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';

import type { ItemCard } from '@/api/client';
import { useItems, useSummary } from '@/api/hooks';
import { ExplanationSheet } from '@/components/explanation-sheet';
import { ItemRow } from '@/components/item-row';
import { LargeTitle, Loading, Note, Screen, SearchField, listPadding } from '@/components/kit';
import { TagFilter } from '@/components/tag-filter';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useSettings } from '@/state/settings';

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
  const summary = useSummary(user);
  const [text, setText] = useState('');
  const q = useDebounced(text.trim());
  const [explaining, setExplaining] = useState<ItemCard | null>(null);
  const [tags, setTags] = useState<string[]>([]);

  const items = useItems(user, domain, 'for_you', q, quality, tags);
  const thisDomain = summary.data?.find((d) => d.domain === domain);

  const pages = items.data?.pages;
  const source = pages?.[0]?.source ?? '';
  const data: ItemCard[] = useMemo(() => pages?.flatMap((p) => p.items) ?? [], [pages]);
  const loading = items.isPending;
  const error = items.error;

  const header = (
    <View style={styles.header}>
      <View>
        <LargeTitle title="Discover" />
        {thisDomain && (
          <ThemedText type="subheadline" themeColor="secondaryLabel">
            {thisDomain.confidence.charAt(0).toUpperCase() + thisDomain.confidence.slice(1)}
          </ThemedText>
        )}
      </View>
      <SearchField value={text} onChangeText={setText} placeholder="Title or author" />
      <TagFilter domain={domain} value={tags} onChange={setTags} />
      {!q && thisDomain?.rated === 0 && !source && (
        <ThemedText type="footnote" themeColor="secondaryLabel">
          Rate a few books to get recommendations.
        </ThemedText>
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
          <ItemRow item={item} index={index} count={data.length} source={source} onExplain={setExplaining} />
        )}
        ListHeaderComponent={header}
        ListEmptyComponent={loading ? <Loading /> : <Note>{q ? 'No matches.' : 'Nothing here yet.'}</Note>}
        ListFooterComponent={items.isFetchingNextPage ? <Loading /> : undefined}
        onEndReached={() => items.hasNextPage && !items.isFetchingNextPage && items.fetchNextPage()}
        onEndReachedThreshold={0.5}
        contentContainerStyle={listPadding}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
      />
      <ExplanationSheet domain={domain} item={explaining} source={source} onClose={() => setExplaining(null)} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { gap: Spacing.three, paddingBottom: Spacing.three },
});
