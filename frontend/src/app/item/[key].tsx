/** One book: its details, its score for you, the tags that set it apart and drive the score, and the
 * most similar books. Pushed over the tabs, under a native navigation bar. */
import { useLocalSearchParams } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';

import { useItem } from '@/api/hooks';
import { BookAbout, BookCover, bookFacts } from '@/components/book-info';
import { ItemRow, RatingButtons } from '@/components/item-row';
import { Loading, Note, Section } from '@/components/kit';
import { DistinctiveTags, ScoreBreakdown, signed } from '@/components/tag-charts';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useSettings } from '@/state/settings';

export default function ItemPage() {
  const { key } = useLocalSearchParams<{ key: string }>();
  const { user, quality } = useSettings();
  const item = useItem(user, key, quality);
  const d = item.data;
  const ex = d?.explanation;
  const card = d?.card;
  const book = d?.book;
  const facts = book ? bookFacts(book) : '';

  return (
    <ThemedView style={styles.screen}>
      <ScrollView contentInsetAdjustmentBehavior="automatic" contentContainerStyle={styles.page}>
        {item.isPending && <Loading />}
        {item.isError && <Note tone="error">{item.error.message}</Note>}
        {card && ex && d && (
          <>
            <View style={styles.head}>
              <BookCover book={book} />
              <ThemedText type="title2" style={styles.center}>
                {card.title}
              </ThemedText>
              <ThemedText type="body" themeColor="secondaryLabel" style={styles.center}>
                {card.creator}
              </ThemedText>
              {(facts || card.year) && (
                <ThemedText type="footnote" themeColor="secondaryLabel" style={styles.center}>
                  {facts || card.year}
                </ThemedText>
              )}
            </View>

            <Section
              title="For You"
              footer={`Beats ${Math.floor(card.percentile)}% of the books you haven't rated.${ex.transferred_part ? ` ${signed(ex.transferred_part, 3)} of it carried over from your other ratings.` : ''}`}>
              <View style={styles.score}>
                <ThemedText type="title1" style={styles.number}>
                  {signed(card.score)}
                </ThemedText>
                <ThemedText type="footnote" themeColor="secondaryLabel">
                  Predicted rating: +1 like, 0 meh, −1 dislike
                </ThemedText>
              </View>
              <View style={styles.rate}>
                <RatingButtons item={card} labelled />
              </View>
            </Section>

            {book && <BookAbout book={book} />}

            <Section title="What sets it apart">
              <DistinctiveTags tags={d.distinctive} noun="book" />
            </Section>

            <Section
              title={`Why it scores ${signed(card.score)}`}
              footer={(() => {
                const shown = [...ex.pulling_up, ...ex.pushing_down].reduce((s, t) => s + t.contribution, 0);
                const rest = ex.score - ex.quality_part - shown;
                return `${signed(ex.score)} = ${signed(shown)} from these tags, ${signed(rest)} from all the others.`;
              })()}>
              <ScoreBreakdown up={ex.pulling_up} down={ex.pushing_down} />
            </Section>

            <Section
              title="Similar books"
              footer="How alike two books' tags are, measured by how each differs from the average book.">
              {d.related.map((r, i) => (
                <ItemRow key={r.key} item={r} index={i} />
              ))}
            </Section>
          </>
        )}
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  page: {
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
    padding: Spacing.three,
    paddingBottom: BottomTabInset + Spacing.six,
    gap: Spacing.four,
  },
  head: { alignItems: 'center', gap: Spacing.one, paddingTop: Spacing.two },
  center: { textAlign: 'center' },
  score: { padding: Spacing.three, paddingBottom: Spacing.two },
  number: { fontVariant: ['tabular-nums'] },
  rate: { paddingHorizontal: Spacing.three, paddingBottom: Spacing.three },
});
