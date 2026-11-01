/** Discover: book recommendations ("For You"), the most useful books to rate ("Rate"), and your
 * ratings, as one inset-grouped list under a large title. */
import { SegmentedControl } from '@expo/ui/community/segmented-control';
import { useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';

import type { ItemCard } from '@/api/client';
import { type Mode, useItems, useRated, useSummary } from '@/api/hooks';
import { ExplanationSheet } from '@/components/explanation-sheet';
import { ItemRow } from '@/components/item-row';
import { LargeTitle, Loading, Note, Screen, SearchField, listPadding } from '@/components/kit';
import { TagFilter } from '@/components/tag-filter';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useSettings } from '@/state/settings';

type View_ = Mode | 'rated';
const VIEWS: View_[] = ['for_you', 'rate', 'rated'];

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
  const scheme = useColorScheme();
  const summary = useSummary(user);
  const [view, setView] = useState<View_>('for_you');
  const [text, setText] = useState('');
  const q = useDebounced(text.trim());
  const [explaining, setExplaining] = useState<ItemCard | null>(null);
  const [tags, setTags] = useState<string[]>([]);

  const items = useItems(user, domain, view === 'rated' ? 'for_you' : view, q, quality, tags);
  const rated = useRated(user, domain, quality);
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
      <View>
        <LargeTitle title="Discover" />
        {thisDomain && (
          <ThemedText type="subheadline" themeColor="secondaryLabel">
            {thisDomain.confidence.charAt(0).toUpperCase() + thisDomain.confidence.slice(1)}
          </ThemedText>
        )}
      </View>
      <SegmentedControl
        values={['For You', 'Rate', `Ratings${rated.data ? ` (${rated.data.length})` : ''}`]}
        selectedIndex={VIEWS.indexOf(view)}
        onChange={(e) => setView(VIEWS[e.nativeEvent.selectedSegmentIndex])}
        appearance={scheme === 'dark' ? 'dark' : 'light'} // the app's choice, which may differ from the system's
      />
      {view !== 'rated' && (
        <>
          <SearchField value={text} onChangeText={setText} placeholder="Title or author" />
          <TagFilter domain={domain} value={tags} onChange={setTags} />
        </>
      )}
      {view === 'for_you' && !q && thisDomain?.rated === 0 && !source && (
        <ThemedText type="footnote" themeColor="secondaryLabel">
          Rate a few books. Until then this is just the best-rated overall.
        </ThemedText>
      )}
      {view === 'rate' && !q && (
        <ThemedText type="footnote" themeColor="secondaryLabel">
          Well-known books your profile knows least about, spread across different kinds. Rating these teaches it the
          most.
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
        onEndReached={() => view !== 'rated' && items.hasNextPage && !items.isFetchingNextPage && items.fetchNextPage()}
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
