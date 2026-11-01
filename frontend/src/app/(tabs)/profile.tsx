/** Profile: Describe Me, then what the model has inferred: shared traits and each domain's own taste. */
import { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';

import type { Claim, Claims } from '@/api/client';
import { useDescribe, useDescription, useProfile } from '@/api/hooks';
import { ACCENT, Button, Chips, Loading, Note, Screen, listPadding } from '@/components/kit';
import { SettingsBar } from '@/components/settings-bar';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

const ICON: Record<number, string> = { 1: '👍', 0: '😐', [-1]: '👎' };
const DOMAIN_ICON: Record<string, string> = { film: '🎬', book: '📚' };

function DescribeMe() {
  const { user } = useSettings();
  const description = useDescription(user);
  const describe = useDescribe(user);
  const d = description.data;
  return (
    <View style={styles.section}>
      <View style={styles.describeRow}>
        <Button primary label="Describe Me" busy={describe.isPending} onPress={() => describe.mutate()} />
        {describe.isPending && (
          <ThemedText type="small" themeColor="textSecondary">
            Writing your reading… (about 30 seconds)
          </ThemedText>
        )}
      </View>
      {describe.isError && <Note tone="error">{describe.error.message}</Note>}
      {d && (
        <Note>
          <ThemedText>{d.text}</ThemedText>
          <ThemedText type="small" themeColor="textSecondary" style={{ marginTop: Spacing.two }}>
            Written {d.created.replace('T', ' at ')}
            {d.stale ? '. Your ratings have changed since; press Describe Me for a fresh one.' : ''}
          </ThemedText>
        </Note>
      )}
    </View>
  );
}

function ClaimRow({ claim, top }: { claim: Claim; top: number }) {
  const theme = useTheme();
  const items = (es: Claim['supporting']) =>
    es.map((e) => `${ICON[e.rating]} ${DOMAIN_ICON[e.domain] ?? ''} ${e.item}`).join('; ');
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
  const { user } = useSettings();
  const profile = useProfile(user);
  const [section, setSection] = useState('shared');
  const p = profile.data;
  const sections = [
    ...(p?.shared ? [{ value: 'shared', label: 'Shared traits' }] : []),
    ...(p?.domains ?? []).map((d) => ({ value: d.domain, label: `${d.name} only` })),
  ];
  const current = sections.some((s) => s.value === section) ? section : sections[0]?.value;
  const domain = p?.domains.find((d) => d.domain === current);

  return (
    <Screen>
      <ScrollView contentContainerStyle={[listPadding, styles.page]}>
        <SettingsBar showQuality={false} />
        <DescribeMe />
        <ThemedText type="small" themeColor="textSecondary">
          Evidence lists only items that clearly have the trait. for: rated the way the trait points. against: rated
          the other way, or meh.
        </ThemedText>
        {profile.isPending && <Loading />}
        {profile.isError && <Note tone="error">{profile.error.message}</Note>}
        {p && current && (
          <>
            <Chips options={sections} value={current} onChange={setSection} />
            {current === 'shared' && p.shared ? (
              <>
                <ThemedText type="small" themeColor="textSecondary">
                  Traits that mean the same across {p.domains.map((d) => d.name.toLowerCase()).join(' and ')}, fit on
                  all your ratings. This is what carries over between domains.
                </ThemedText>
                <ClaimLists claims={p.shared} empty="No ratings yet." />
              </>
            ) : domain ? (
              <>
                <ThemedText type="small" themeColor="textSecondary">
                  {domain.confidence}. Taste learnt from these ratings alone, on top of what carried over from other
                  domains.
                </ThemedText>
                <ClaimLists claims={domain.claims} empty={`No ${domain.name.toLowerCase()} rated yet.`} />
              </>
            ) : null}
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  page: { gap: Spacing.three },
  section: { gap: Spacing.two },
  describeRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, flexWrap: 'wrap' },
  columns: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.four },
  column: { flex: 1, minWidth: 260, gap: Spacing.three },
  columnTitle: { fontSize: 22, lineHeight: 28 },
  claim: { gap: 4 },
  track: { height: 6, borderRadius: 3, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3, backgroundColor: ACCENT },
});
