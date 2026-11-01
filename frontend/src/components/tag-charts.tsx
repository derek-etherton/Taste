/** Tag charts for a book's page: plain Views, one labelled row per tag, so each doubles as a
 * table. Drawn inside a Section card. */
import { StyleSheet, View } from 'react-native';

import type { TagContribution, TagStrength } from '@/api/client';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const BAR = 8; // px: thin marks
const RADIUS = 4; // rounded at the data end only; square where the bar starts

/** Signed, so a lean either way reads at a glance: +0.42, −0.17. */
export function signed(x: number, digits = 2): string {
  const s = Math.abs(x).toFixed(digits);
  return Number(s) === 0 ? s : `${x > 0 ? '+' : '−'}${s}`;
}

function Legend({ items }: { items: { label: string; color: string; tick?: boolean }[] }) {
  return (
    <View style={styles.legend}>
      {items.map((i) => (
        <View key={i.label} style={styles.legendItem}>
          <View style={[i.tick ? styles.tickSwatch : styles.swatch, { backgroundColor: i.color }]} />
          <ThemedText type="footnote" themeColor="secondaryLabel">
            {i.label}
          </ThemedText>
        </View>
      ))}
    </View>
  );
}

function Value({ children }: { children: string }) {
  return (
    <ThemedText type="footnote" themeColor="secondaryLabel" style={styles.value}>
      {children}
    </ThemedText>
  );
}

/** How strongly the book has each tag (0 to 1), with a tick where the average book sits. */
export function DistinctiveTags({ tags, noun }: { tags: TagStrength[]; noun: string }) {
  const theme = useTheme();
  if (!tags.length) return <ThemedText themeColor="secondaryLabel" style={styles.chart}>Nothing stands out.</ThemedText>;
  return (
    <View style={styles.chart}>
      <Legend items={[{ label: `this ${noun}`, color: theme.chartUp }, { label: `average ${noun}`, color: theme.secondaryLabel, tick: true }]} />
      {tags.map((t) => (
        <View key={t.tag} style={styles.row} accessibilityLabel={`${t.tag}: ${t.score.toFixed(2)}, average ${t.average.toFixed(2)}`}>
          <ThemedText type="subheadline" style={styles.label} numberOfLines={1}>
            {t.tag}
          </ThemedText>
          <View style={[styles.track, { backgroundColor: theme.fill }]}>
            <View style={[styles.fromLeft, { width: `${t.score * 100}%`, backgroundColor: theme.chartUp }]} />
            <View style={[styles.tick, { left: `${t.average * 100}%`, backgroundColor: theme.label }]} />
          </View>
          <Value>{t.score.toFixed(2)}</Value>
        </View>
      ))}
    </View>
  );
}

/** What the score is made of: tags pulling it up (right of zero) and pushing it down (left). */
export function ScoreBreakdown({ up, down, source }: { up: TagContribution[]; down: TagContribution[]; source?: string }) {
  const theme = useTheme();
  const rows = [...up, ...down];
  if (!rows.length) return <ThemedText themeColor="secondaryLabel" style={styles.chart}>Rate a few books to see what drives this.</ThemedText>;
  const max = Math.max(...rows.map((t) => Math.abs(t.contribution)));
  const carried = rows.some((t) => t.from_other_domain);
  return (
    <View style={styles.chart}>
      <Legend items={[{ label: 'pulling it up', color: theme.chartUp }, { label: 'pushing it down', color: theme.chartDown }]} />
      {rows.map((t) => {
        const width = `${(Math.abs(t.contribution) / max) * 100}%` as const;
        const positive = t.contribution > 0;
        return (
          <View key={t.tag} style={styles.row} accessibilityLabel={`${t.tag}: ${signed(t.contribution, 3)}`}>
            <ThemedText type="subheadline" style={styles.label} numberOfLines={1}>
              {t.tag}
              {t.from_other_domain ? ' ↔' : ''}
            </ThemedText>
            <View style={styles.diverging}>
              <View style={styles.half}>
                {!positive && <View style={[styles.fromRight, { width, backgroundColor: theme.chartDown }]} />}
              </View>
              <View style={[styles.zero, { backgroundColor: theme.separator }]} />
              <View style={styles.half}>
                {positive && <View style={[styles.fromLeft, { width, backgroundColor: theme.chartUp }]} />}
              </View>
            </View>
            <Value>{signed(t.contribution, 3)}</Value>
          </View>
        );
      })}
      {carried && (
        <ThemedText type="footnote" themeColor="secondaryLabel">
          ↔ carried over from your {source || 'ratings in another domain'}
        </ThemedText>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  chart: { gap: Spacing.two, padding: Spacing.three },
  legend: { flexDirection: 'row', gap: Spacing.three, flexWrap: 'wrap', marginBottom: Spacing.one },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  swatch: { width: 12, height: BAR, borderRadius: 2 },
  tickSwatch: { width: 2, height: 14 },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, minHeight: 24 },
  label: { width: '34%' },
  value: { width: 52, textAlign: 'right', fontVariant: ['tabular-nums'] },
  track: { flex: 1, height: BAR, borderRadius: BAR / 2, justifyContent: 'center' },
  fromLeft: { height: BAR, borderTopRightRadius: RADIUS, borderBottomRightRadius: RADIUS },
  fromRight: { height: BAR, alignSelf: 'flex-end', borderTopLeftRadius: RADIUS, borderBottomLeftRadius: RADIUS },
  tick: { position: 'absolute', width: 2, height: 14, marginLeft: -1 },
  diverging: { flex: 1, flexDirection: 'row', alignItems: 'center' },
  half: { flex: 1, height: BAR, justifyContent: 'center' },
  zero: { width: 1, height: 18 },
});
