/** Your taste in books as an infographic: how you've rated (stat tiles over a part-to-whole bar),
 * a one-line summary, a butterfly chart of the tags you're into (right, growing from a shared
 * zero) against those you're not (left), with the books behind a hovered tag, then your 3 books.
 * Plain Views, so it runs everywhere. */
import { useState } from 'react';
import { Platform, Pressable, StyleSheet, View } from 'react-native';

import type { Claim, Claims, ItemCard } from '@/api/client';
import { Section } from '@/components/kit';
import { signed } from '@/components/tag-charts';
import { ThemedText } from '@/components/themed-text';
import { TopBooks } from '@/components/top-books';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const ROWS = 10; // tags per side (the API sends 10)
const BAR = 14; // px: thin marks, under the 24px cap
const END = 4; // the data end is rounded; the zero end stays square
const GAP = 2; // surface gap between stacked segments

export type RatingCounts = { liked: number; meh: number; disliked: number };

/** Liked / meh / disliked as three stat tiles, over one bar of the whole. */
function RatingMix({ counts }: { counts: RatingCounts }) {
  const theme = useTheme();
  const parts = [
    { label: 'Liked', n: counts.liked, color: theme.chartUp },
    { label: 'Meh', n: counts.meh, color: theme.neutral },
    { label: 'Disliked', n: counts.disliked, color: theme.chartDown },
  ];
  const total = parts.reduce((s, p) => s + p.n, 0);
  return (
    <View style={styles.mix}>
      <View style={styles.tiles}>
        {parts.map((p) => (
          <View key={p.label} style={styles.tile} accessibilityLabel={`${p.label}: ${p.n}`}>
            <ThemedText type="largeTitle" style={styles.number}>
              {p.n}
            </ThemedText>
            <View style={styles.tileLabel}>
              <View style={[styles.swatch, { backgroundColor: p.color }]} />
              <ThemedText type="footnote" themeColor="secondaryLabel">
                {p.label}
              </ThemedText>
            </View>
          </View>
        ))}
      </View>
      {total > 0 && (
        <View style={styles.stack} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {parts
            .filter((p) => p.n > 0)
            .map((p) => (
              <View key={p.label} style={{ flex: p.n, backgroundColor: p.color }} />
            ))}
        </View>
      )}
    </View>
  );
}

/** "Into a, b and c. Not into d, e and f." The tags in bold label ink, not series colour. */
function Headline({ up, down }: { up: Claim[]; down: Claim[] }) {
  const list = (cs: Claim[]) => {
    const tags = cs.slice(0, 3).map((c) => c.tag);
    return tags.map((t, i) => (
      <ThemedText key={t} type="title3">
        {i === 0 ? '' : i === tags.length - 1 ? ' and ' : ', '}
        {t}
      </ThemedText>
    ));
  };
  return (
    <View style={styles.headline}>
      {up.length > 0 && (
        <ThemedText type="title3" style={styles.light}>
          Into {list(up)}.
        </ThemedText>
      )}
      {down.length > 0 && (
        <ThemedText type="title3" style={styles.light}>
          Not into {list(down)}.
        </ThemedText>
      )}
    </View>
  );
}

type Picked = Claim | null;

/** One side of a butterfly row: the bar grows from the shared zero axis, the label sits outside. */
function Half({
  claim,
  side,
  max,
  picked,
  onPick,
}: {
  claim?: Claim;
  side: 'up' | 'down';
  max: number;
  picked: Picked;
  onPick: (p: Picked) => void;
}) {
  const theme = useTheme();
  const up = side === 'up';
  const active = picked?.tag === claim?.tag;
  const dim = picked && !active ? 0.35 : 1;
  const pick = () => claim && onPick(claim);
  const bar = claim && (
    <View style={[styles.track, up ? styles.fromZeroRight : styles.fromZeroLeft]}>
      <View
        style={[
          styles.bar,
          up ? styles.endRight : styles.endLeft,
          { width: `${(Math.abs(claim.weight) / max) * 100}%`, backgroundColor: up ? theme.chartUp : theme.chartDown },
        ]}
      />
    </View>
  );
  const label = (
    <ThemedText type="footnote" numberOfLines={2} style={[styles.label, up ? styles.labelUp : styles.labelDown]}>
      {claim?.tag ?? ''}
    </ThemedText>
  );
  return (
    <Pressable
      disabled={!claim}
      accessibilityLabel={claim ? `${up ? 'Into' : 'Not into'} ${claim.tag}, weight ${signed(claim.weight, 3)}` : undefined}
      onHoverIn={pick}
      onHoverOut={() => onPick(null)}
      onPressIn={pick}
      onPress={pick}
      style={[styles.half, { opacity: dim }]}>
      {up ? (
        <>
          {bar}
          {label}
        </>
      ) : (
        <>
          {label}
          {bar}
        </>
      )}
    </Pressable>
  );
}

/** Under the chart: the hovered (or tapped) tag's weight and the books behind it, i.e. the ones
 * you rated its way that have a lot of it. Fixed height, so the page doesn't jump. */
function Readout({ picked }: { picked: Picked }) {
  if (!picked) {
    return (
      <ThemedText type="footnote" themeColor="secondaryLabel" style={styles.readout}>
        {Platform.OS === 'web' ? 'Hover over' : 'Tap'} a bar to see the books behind it. Longer bars move your scores
        more.
      </ThemedText>
    );
  }
  const into = picked.weight > 0;
  return (
    <View style={styles.readout}>
      <ThemedText type="footnote">
        <ThemedText type="footnote" style={styles.strong}>
          {picked.tag}
        </ThemedText>
        <ThemedText type="footnote" themeColor="secondaryLabel">
          {`  ${signed(picked.weight, 3)} on a book's score. ${picked.supporting.length ? `Books you ${into ? 'liked' : 'disliked'} that are full of it:` : ''}`}
        </ThemedText>
      </ThemedText>
      {picked.supporting.map((e) => (
        <ThemedText key={e.item} type="footnote" themeColor="secondaryLabel" numberOfLines={1}>
          {'·  '}
          {e.item}
        </ThemedText>
      ))}
    </View>
  );
}

function Butterfly({ up, down }: { up: Claim[]; down: Claim[] }) {
  const theme = useTheme();
  const [picked, setPicked] = useState<Picked>(null);
  const rows = Math.min(ROWS, Math.max(up.length, down.length));
  const max = Math.max(...[...up, ...down].map((c) => Math.abs(c.weight)), 1e-9);
  return (
    <View style={styles.butterfly}>
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.swatch, { backgroundColor: theme.chartDown }]} />
          <ThemedText type="footnote" themeColor="secondaryLabel">
            Not into
          </ThemedText>
        </View>
        <View style={styles.legendItem}>
          <ThemedText type="footnote" themeColor="secondaryLabel">
            Into
          </ThemedText>
          <View style={[styles.swatch, { backgroundColor: theme.chartUp }]} />
        </View>
      </View>
      <View>
        {/* The shared zero: one hairline the bars on both sides grow from. */}
        <View style={[styles.axis, { backgroundColor: theme.separator }]} />
        {Array.from({ length: rows }, (_, i) => (
          <View key={i} style={styles.row}>
            <Half claim={down[i]} side="down" max={max} picked={picked} onPick={setPicked} />
            <Half claim={up[i]} side="up" max={max} picked={picked} onPick={setPicked} />
          </View>
        ))}
      </View>
      <Readout picked={picked} />
    </View>
  );
}

export function TasteChart({
  claims,
  counts,
  confidence,
  top,
}: {
  claims: Claims;
  counts?: RatingCounts;
  confidence: string;
  /** The books that best match your taste (liked or unread), best first. */
  top?: ItemCard[];
}) {
  const up = claims.respond_to.slice(0, ROWS);
  const down = claims.push_back_on.slice(0, ROWS);
  // "based on 14 books (9 liked, 1 meh, 4 disliked): medium confidence": the tiles show the counts
  const level = confidence.split(':').pop()!.trim();
  const capital = level.charAt(0).toUpperCase() + level.slice(1);
  return (
    <View style={styles.page}>
      {counts && (
        <Section title="Your ratings" footer={`${capital}.`}>
          <RatingMix counts={counts} />
        </Section>
      )}
      {(up.length > 0 || down.length > 0) && (
        <Section>
          <Headline up={up} down={down} />
          <Butterfly up={up} down={down} />
        </Section>
      )}
      {top && top.length > 0 && (
        <Section title={`Your ${top.length} books`}>
          <TopBooks items={top} />
        </Section>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  page: { gap: Spacing.four },
  mix: { padding: Spacing.three, gap: Spacing.three },
  tiles: { flexDirection: 'row' },
  tile: { flex: 1, gap: 2 },
  number: { fontVariant: ['tabular-nums'] },
  tileLabel: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  swatch: { width: 10, height: 10, borderRadius: 2 },
  stack: { flexDirection: 'row', gap: GAP, height: 10, borderRadius: END, overflow: 'hidden' },
  headline: { paddingHorizontal: Spacing.three, paddingTop: Spacing.three, gap: 2 },
  light: { fontWeight: '400' },
  butterfly: { padding: Spacing.three, gap: Spacing.three },
  legend: { flexDirection: 'row', justifyContent: 'space-between' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  axis: { position: 'absolute', left: '50%', top: 0, bottom: 0, width: StyleSheet.hairlineWidth },
  row: { flexDirection: 'row', alignItems: 'center', minHeight: 28 },
  half: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: Spacing.two, minHeight: 28 },
  track: { flex: 1, height: BAR, flexDirection: 'row' },
  fromZeroRight: { justifyContent: 'flex-start' },
  fromZeroLeft: { justifyContent: 'flex-end' },
  bar: { height: BAR },
  endRight: { borderTopRightRadius: END, borderBottomRightRadius: END },
  endLeft: { borderTopLeftRadius: END, borderBottomLeftRadius: END },
  label: { width: '46%' },
  labelUp: { textAlign: 'left' },
  labelDown: { textAlign: 'right' },
  readout: { minHeight: 126, gap: 2 }, // the tag line and up to five books
  strong: { fontWeight: '600' },
});
