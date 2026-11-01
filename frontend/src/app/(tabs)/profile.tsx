/** Profile: the algorithm's settings, then what the model has inferred about your taste in books. */
import { Fragment } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';

import type { Claim, Claims } from '@/api/client';
import { useProfile } from '@/api/hooks';
import { LargeTitle, Loading, Note, Screen, Section, Separator, listPadding } from '@/components/kit';
import { QualitySlider } from '@/components/quality-slider';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

const RATED: Record<number, string> = { 1: 'Liked', 0: 'Meh', [-1]: 'Disliked' };

/** "Liked: A, B; Meh: C": evidence grouped by how you rated it. */
function evidence(es: Claim['supporting']): string {
  return [1, 0, -1]
    .map((r) => [r, es.filter((e) => e.rating === r).map((e) => e.item)] as const)
    .filter(([, items]) => items.length)
    .map(([r, items]) => `${RATED[r]}: ${items.join(', ')}`)
    .join('; ');
}

function ClaimRow({ claim, top, color }: { claim: Claim; top: number; color: string }) {
  const theme = useTheme();
  return (
    <View style={styles.claim}>
      <ThemedText type="headline">{claim.tag}</ThemedText>
      <View style={[styles.track, { backgroundColor: theme.fill }]}>
        <View style={[styles.bar, { width: `${Math.min(100, (Math.abs(claim.weight) / top) * 100)}%`, backgroundColor: color }]} />
      </View>
      {claim.supporting.length > 0 && (
        <ThemedText type="footnote" themeColor="secondaryLabel">
          {evidence(claim.supporting)}
        </ThemedText>
      )}
      {claim.contradicting.length > 0 && (
        <ThemedText type="footnote" themeColor="secondaryLabel">
          Against it, {evidence(claim.contradicting)}
        </ThemedText>
      )}
    </View>
  );
}

function ClaimLists({ claims }: { claims: Claims }) {
  const theme = useTheme();
  const all = [...claims.respond_to, ...claims.push_back_on];
  if (all.length === 0) return <Note>No books rated yet.</Note>;
  const top = Math.max(...all.map((c) => Math.abs(c.weight)));
  return (
    <View style={styles.columns}>
      {(
        [
          ['You respond to', claims.respond_to, theme.chartUp],
          ['You push back on', claims.push_back_on, theme.chartDown],
        ] as const
      ).map(([title, list, color]) => (
        <View key={title} style={styles.column}>
          <Section title={title}>
            {list.map((c, i) => (
              <Fragment key={c.tag}>
                {i > 0 && <Separator />}
                <ClaimRow claim={c} top={top} color={color} />
              </Fragment>
            ))}
          </Section>
        </View>
      ))}
    </View>
  );
}

export default function ProfileScreen() {
  const { user, domain } = useSettings();
  const profile = useProfile(user);
  const books = profile.data?.domains.find((d) => d.domain === domain);

  return (
    <Screen>
      <ScrollView contentContainerStyle={[listPadding, styles.page]}>
        <LargeTitle title="Profile" />
        <Section title="Algorithm">
          <QualitySlider />
        </Section>
        <View style={styles.taste}>
          <View style={styles.tasteHead}>
            <ThemedText type="title2" accessibilityRole="header">
              Taste
            </ThemedText>
            {books && (
              <ThemedText type="footnote" themeColor="secondaryLabel">
                {books.confidence.charAt(0).toUpperCase() + books.confidence.slice(1)}. Each trait lists the rated books
                that clearly have it.
              </ThemedText>
            )}
          </View>
          {profile.isPending && <Loading />}
          {profile.isError && <Note tone="error">{profile.error.message}</Note>}
          {books && <ClaimLists claims={books.claims} />}
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  page: { gap: Spacing.four },
  taste: { gap: Spacing.three },
  tasteHead: { gap: Spacing.one, paddingHorizontal: Spacing.one },
  columns: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.four },
  column: { flex: 1, minWidth: 280 },
  claim: { gap: 6, paddingVertical: 12, paddingHorizontal: Spacing.three },
  track: { height: 4, borderRadius: 2, overflow: 'hidden' },
  bar: { height: 4, borderRadius: 2 },
});
