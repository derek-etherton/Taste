/** Profile: your taste in books as an infographic, and the books you've rated. */
import { SegmentedControl } from '@expo/ui/community/segmented-control';
import { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';

import { useItems, useProfile, useRated } from '@/api/hooks';
import { ItemRow } from '@/components/item-row';
import { LargeTitle, Loading, Note, Screen, listPadding } from '@/components/kit';
import { type RatingCounts, TasteChart } from '@/components/taste-chart';
import { Spacing } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useSettings } from '@/state/settings';

type Tab = 'taste' | 'ratings';
const TABS: Tab[] = ['taste', 'ratings'];

export default function ProfileScreen() {
  const { user, domain, quality } = useSettings();
  const scheme = useColorScheme();
  const [tab, setTab] = useState<Tab>('taste');
  const profile = useProfile(user);
  const rated = useRated(user, domain, quality);
  const forYou = useItems(user, domain, 'for_you', '', quality); // Discover's list: the same cache
  // Your 3 books sum up your taste, so they're the best matches among books you liked as well as
  // ones you haven't read; meh and disliked books are out.
  const top = useMemo(() => {
    const unrated = forYou.data?.pages[0]?.items;
    if (!unrated || !rated.data) return undefined;
    return [...rated.data.filter((c) => c.rated === 1), ...unrated].sort((a, b) => b.score - a.score).slice(0, 3);
  }, [forYou.data, rated.data]);
  const books = profile.data?.domains.find((d) => d.domain === domain);
  const counts = useMemo<RatingCounts | undefined>(
    () =>
      rated.data && {
        liked: rated.data.filter((c) => c.rated === 1).length,
        meh: rated.data.filter((c) => c.rated === 0).length,
        disliked: rated.data.filter((c) => c.rated === -1).length,
      },
    [rated.data],
  );

  return (
    <Screen>
      <ScrollView contentContainerStyle={[listPadding, styles.page]}>
        <LargeTitle title="Profile" />
        <SegmentedControl
          values={['Taste', `Ratings${rated.data ? ` (${rated.data.length})` : ''}`]}
          selectedIndex={TABS.indexOf(tab)}
          onChange={(e) => setTab(TABS[e.nativeEvent.selectedSegmentIndex])}
          appearance={scheme === 'dark' ? 'dark' : 'light'} // the app's choice, which may differ from the system's
        />
        {tab === 'taste' ? (
          <>
            {profile.isPending && <Loading />}
            {profile.isError && <Note tone="error">{profile.error.message}</Note>}
            {books &&
              (books.rated === 0 ? (
                <Note>Rate a few books and your taste shows up here.</Note>
              ) : (
                <TasteChart claims={books.claims} counts={counts} confidence={books.confidence} top={top} />
              ))}
          </>
        ) : (
          <View>
            {rated.isPending && <Loading />}
            {rated.isError && <Note tone="error">{rated.error.message}</Note>}
            {rated.data?.length === 0 && <Note>Books you rate show up here.</Note>}
            {rated.data?.map((item, i) => (
              <ItemRow key={item.key} item={item} index={i} count={rated.data.length} />
            ))}
          </View>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  page: { gap: Spacing.three },
});
