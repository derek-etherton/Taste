/** Tag charts for an item's page: plain Views, one labelled row per tag, so each doubles as a table. */
import { StyleSheet, View } from 'react-native';

import type { TagContribution, TagStrength } from '@/api/client';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const BAR = 10; // px: thin marks
const RADIUS = 4; // rounded at the data end only; square where the bar starts

/** Signed, so a lean either way reads at a glance: +0.42, −0.17. */
export function signed(x: number, digits = 2): string {
  const s = Math.abs(x).toFixed(digits);
  return Number(s) === 0 ? s : `${x > 0 ? '+' : '−'}${s}`;
}

function Swatch({ color, tick }: { color: string; tick?: boolean }) {
  return <View style={tick ? [styles.tickSwatch, { backgroundColor: color }] : [styles.swatch, { backgroundColor: color }]} />;
}

function Legend({ items }: { items: { label: string; color: string; tick?: boolean }[] }) {
  return (
    <View style={styles.legend}>
      {items.map((i) => (
        <View key={i.label} style={styles.legendItem}>
          <Swatch color={i.color} tick={i.tick} />
          <ThemedText type="small" themeColor="textSecondary">
            {i.label}
          </ThemedText>
        </View>
      ))}
    </View>
  );
}

/** How strongly the item has each tag (0 to 1), with a tick where the average item sits. */
export function DistinctiveTags({ tags, noun }: { tags: TagStrength[]; noun: string }) {
  const theme = useTheme();
  if (!tags.length) return <ThemedText themeColor="textSecondary">Nothing stands out.</ThemedText>;
  return (
    <View style={styles.chart}>
      <Legend items={[{ label: `this ${noun}`, color: theme.chartUp }, { label: `average ${noun}`, color: theme.text, tick: true }]} />
      {tags.map((t) => (
        <View key={t.tag} style={styles.row} accessibilityLabel={`${t.tag}: ${t.score.toFixed(2)}, average ${t.average.toFixed(2)}`}>
          <ThemedText type="small" style={styles.label} numberOfLines={1}>
            {t.tag}
          </ThemedText>
          <View style={[styles.track, { backgroundColor: theme.backgroundElement }]}>
            <View style={[styles.fromLeft, { width: `${t.score * 100}%`, backgroundColor: theme.chartUp }]} />
            <View style={[styles.tick, { left: `${t.average * 100}%`, backgroundColor: theme.text }]} />
          </View>
          <ThemedText type="code" style={styles.value}>
            {t.score.toFixed(2)}
          </ThemedText>
        </View>
      ))}
    </View>
  );
}

/** What the score is made of: tags pulling it up (right of zero) and pushing it down (left). */
export function ScoreBreakdown({ up, down, source }: { up: TagContribution[]; down: TagContribution[]; source?: string }) {
  const theme = useTheme();
  const rows = [...up, ...down];
  if (!rows.length) return <ThemedText themeColor="textSecondary">Rate a few to see what drives this.</ThemedText>;
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
            <ThemedText type="small" style={styles.label} numberOfLines={1}>
              {t.tag}
              {t.from_other_domain ? ' ↔' : ''}
            </ThemedText>
            <View style={styles.diverging}>
              <View style={styles.half}>
                {!positive && <View style={[styles.fromRight, { width, backgroundColor: theme.chartDown }]} />}
              </View>
              <View style={[styles.zero, { backgroundColor: theme.textSecondary }]} />
              <View style={styles.half}>
                {positive && <View style={[styles.fromLeft, { width, backgroundColor: theme.chartUp }]} />}
              </View>
            </View>
            <ThemedText type="code" style={styles.value}>
              {signed(t.contribution, 3)}
            </ThemedText>
          </View>
        );
      })}
      {carried && (
        <ThemedText type="small" themeColor="textSecondary">
          ↔ carried over from your {source || 'ratings in another domain'}
        </ThemedText>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  chart: { gap: Spacing.two },
  legend: { flexDirection: 'row', gap: Spacing.three, flexWrap: 'wrap', marginBottom: Spacing.one },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: Spacing.one + 2 },
  swatch: { width: 12, height: BAR, borderRadius: 2 },
  tickSwatch: { width: 2, height: 14 },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, minHeight: 22 },
  label: { width: '34%' },
  value: { width: 52, textAlign: 'right' },
  track: { flex: 1, height: BAR, justifyContent: 'center' },
  fromLeft: { height: BAR, borderTopRightRadius: RADIUS, borderBottomRightRadius: RADIUS },
  fromRight: { height: BAR, alignSelf: 'flex-end', borderTopLeftRadius: RADIUS, borderBottomLeftRadius: RADIUS },
  tick: { position: 'absolute', width: 2, height: 16, marginLeft: -1 },
  diverging: { flex: 1, flexDirection: 'row', alignItems: 'center' },
  half: { flex: 1, height: BAR, justifyContent: 'center' },
  zero: { width: 1, height: 18 },
});
