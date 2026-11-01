/** One film or book: its details, its score for you, the tags that set it apart and drive the score,
 * and the most similar items in its domain. */
import { router, useLocalSearchParams } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { useItem } from '@/api/hooks';
import { ItemRow, RatingButtons } from '@/components/item-row';
import { Loading, Note, Screen } from '@/components/kit';
import { DistinctiveTags, ScoreBreakdown, signed } from '@/components/tag-charts';
import { ThemedText } from '@/components/themed-text';
import { BottomTabInset, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

const NOUNS: Record<string, [string, string]> = { book: ['book', 'books'], film: ['film', 'films'] };

function back() {
  if (router.canGoBack()) router.back();
  else router.replace('/'); // opened straight from a link
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <ThemedText type="smallBold">{title}</ThemedText>
      {children}
    </View>
  );
}

export default function ItemPage() {
  const { key } = useLocalSearchParams<{ key: string }>();
  const { user, quality } = useSettings();
  const theme = useTheme();
  const item = useItem(user, key, quality);
  const domain = key.split(':')[0];
  const [noun, nouns] = NOUNS[domain] ?? ['item', 'items'];
  const d = item.data;
  const ex = d?.explanation;
  const card = d?.card;
  const details = card ? [card.creator, card.genres.join(' · ')].filter(Boolean) : [];
  const other = domain === 'book' ? 'films' : 'books';

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.page}>
        <Pressable accessibilityRole="button" onPress={back} style={({ pressed }) => [styles.back, pressed && { opacity: 0.6 }]}>
          <ThemedText type="small" themeColor="textSecondary">
            ‹ Back
          </ThemedText>
        </Pressable>
        {item.isPending && <Loading />}
        {item.isError && <Note tone="error">{item.error.message}</Note>}
        {card && ex && d && (
          <>
            <View style={styles.head}>
              <ThemedText type="subtitle">{card.label}</ThemedText>
              {details.map((line) => (
                <ThemedText key={line} themeColor="textSecondary">
                  {line}
                </ThemedText>
              ))}
              {card.series && (
                <ThemedText type="small" themeColor="textSecondary">
                  {card.series}
                </ThemedText>
              )}
            </View>

            <View style={[styles.score, { backgroundColor: theme.backgroundElement }]}>
              <View style={styles.scoreTop}>
                <View>
                  <ThemedText type="title" style={styles.scoreValue}>
                    {signed(card.score)}
                  </ThemedText>
                  <ThemedText type="small" themeColor="textSecondary">
                    your predicted rating: +1 like, 0 meh, −1 dislike
                  </ThemedText>
                </View>
                <RatingButtons item={card} />
              </View>
              <ThemedText type="small">
                Beats {Math.floor(card.percentile)}% of the {nouns} you haven&apos;t rated.
              </ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                {signed(ex.quality_part, 3)} from general quality · {signed(ex.transferred_part, 3)} from your {other}
              </ThemedText>
            </View>

            <Section title="What sets it apart">
              <DistinctiveTags tags={d.distinctive} noun={noun} />
            </Section>

            <Section title={`Why it scores ${signed(card.score)} for you`}>
              <ScoreBreakdown up={ex.pulling_up} down={ex.pushing_down} source={other} />
              <ThemedText type="small" themeColor="textSecondary">
                {(() => {
                  const shown = [...ex.pulling_up, ...ex.pushing_down].reduce((s, t) => s + t.contribution, 0);
                  const rest = ex.score - ex.quality_part - shown;
                  return `Score ${signed(ex.score)} = ${signed(shown)} from these tags ${signed(rest)} from all the others ${signed(ex.quality_part)} from general quality.`;
                })()}
              </ThemedText>
            </Section>

            <Section title={`Similar ${nouns}`}>
              <ThemedText type="small" themeColor="textSecondary">
                Similarity runs from 1 (the same tag profile) through 0 (unrelated) to −1 (opposites), comparing how
                each differs from the average {noun}.
              </ThemedText>
              <View>
                {d.related.map((r) => (
                  <ItemRow key={r.key} item={r} source={other} />
                ))}
              </View>
            </Section>
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  page: { padding: Spacing.three, paddingBottom: BottomTabInset + Spacing.six, gap: Spacing.four },
  back: { alignSelf: 'flex-start', paddingVertical: Spacing.one },
  head: { gap: Spacing.one },
  score: { borderRadius: Spacing.three, padding: Spacing.three, gap: Spacing.two },
  scoreTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.three, flexWrap: 'wrap' },
  scoreValue: { fontVariant: ['tabular-nums'] },
  section: { gap: Spacing.two },
});
