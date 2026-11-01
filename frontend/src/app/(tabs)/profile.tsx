/** Profile: the algorithm's settings, then what the model has inferred about your taste in books. */
import { ScrollView, StyleSheet, View } from 'react-native';

import type { Claim, Claims } from '@/api/client';
import { useProfile } from '@/api/hooks';
import { ACCENT, Loading, Note, Screen, listPadding } from '@/components/kit';
import { QualitySlider } from '@/components/quality-slider';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

const ICON: Record<number, string> = { 1: '👍', 0: '😐', [-1]: '👎' };

function ClaimRow({ claim, top }: { claim: Claim; top: number }) {
  const theme = useTheme();
  const items = (es: Claim['supporting']) =>
    es.map((e) => `${ICON[e.rating]} ${e.item}`).join('; ');
  return (
    <View style={styles.claim}>
      <ThemedText type="smallBold">{claim.tag}</ThemedText>
      <View style={[styles.track, { backgroundColor: theme.backgroundElement }]}>
        <View style={[styles.fill, { width: `${Math.min(100, (Math.abs(claim.weight) / top) * 100)}%` }]} />
      </View>
      {claim.supporting.length > 0 && (
        <ThemedText type="small" themeColor="textSecondary">for: {items(claim.supporting)}</ThemedText>
      )}
      {claim.contradicting.length > 0 && (
        <ThemedText type="small" themeColor="textSecondary">against: {items(claim.contradicting)}</ThemedText>
      )}
    </View>
  );
}

function ClaimLists({ claims, empty }: { claims: Claims; empty: string }) {
  const all = [...claims.respond_to, ...claims.push_back_on];
  if (all.length === 0) return <Note>{empty}</Note>;
  const top = Math.max(...all.map((c) => Math.abs(c.weight)));
  return (
    <View style={styles.columns}>
      {(
        [
          ['You respond to', claims.respond_to],
          ['You push back on', claims.push_back_on],
        ] as const
      ).map(([title, list]) => (
        <View key={title} style={styles.column}>
          <ThemedText type="subtitle" style={styles.columnTitle}>
            {title}
          </ThemedText>
          {list.map((c) => (
            <ClaimRow key={c.tag} claim={c} top={top} />
          ))}
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
        <View style={styles.section}>
          <ThemedText type="subtitle">Algorithm</ThemedText>
          <QualitySlider />
        </View>
        <View style={styles.section}>
          <ThemedText type="subtitle">Taste</ThemedText>
          {profile.isPending && <Loading />}
          {profile.isError && <Note tone="error">{profile.error.message}</Note>}
          {books && (
            <>
              <ThemedText type="small" themeColor="textSecondary">
                Your taste in books, {books.confidence}. Evidence lists only books that clearly have the trait. for:
                rated the way the trait points. against: rated the other way, or meh.
              </ThemedText>
              <ClaimLists claims={books.claims} empty="No books rated yet." />
            </>
          )}
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  page: { gap: Spacing.three },
  section: { gap: Spacing.two },
  columns: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.four },
  column: { flex: 1, minWidth: 260, gap: Spacing.three },
  columnTitle: { fontSize: 22, lineHeight: 28 },
  claim: { gap: 4 },
  track: { height: 6, borderRadius: 3, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3, backgroundColor: ACCENT },
});
