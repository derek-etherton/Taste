/** Why an item scores what it does: its score, the parts from quality and from other
 * domains, and the tags pulling it up and pushing it down. A modal, so it works the same everywhere. */
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import type { ItemCard } from '@/api/client';
import { useExplanation } from '@/api/hooks';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Button, Loading, Note } from '@/components/kit';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <ThemedText type="small" themeColor="textSecondary">
        {label}
      </ThemedText>
      <ThemedText type="subtitle" style={styles.metricValue}>
        {value}
      </ThemedText>
    </View>
  );
}

function TagList({ title, tags }: { title: string; tags: { tag: string; contribution: number; from_other_domain: boolean }[] }) {
  return (
    <View style={styles.tagList}>
      <ThemedText type="smallBold">{title}</ThemedText>
      {tags.length === 0 && <ThemedText type="small" themeColor="textSecondary">—</ThemedText>}
      {tags.map((t) => (
        <View key={t.tag} style={styles.tagRow}>
          <ThemedText type="small" style={{ flex: 1 }}>
            {t.tag}
            {t.from_other_domain ? ' ↔' : ''}
          </ThemedText>
          <ThemedText type="code">{t.contribution > 0 ? '+' : ''}{t.contribution.toFixed(3)}</ThemedText>
        </View>
      ))}
    </View>
  );
}

export function ExplanationSheet({
  domain,
  item,
  source,
  onClose,
}: {
  domain: string;
  item: ItemCard | null;
  source?: string;
  onClose: () => void;
}) {
  const { user, quality } = useSettings();
  const ex = useExplanation(user, domain, item?.key ?? null, quality);
  const theme = useTheme();
  const signed = (x: number) => `${x > 0 ? '+' : ''}${x.toFixed(3)}`;
  return (
    <Modal visible={item !== null} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable onPress={() => {}} style={styles.sheetWrap}>
          <ThemedView style={[styles.sheet, { borderColor: theme.backgroundSelected }]}>
            <ScrollView contentContainerStyle={styles.content}>
              <ThemedText type="smallBold">{item?.label}</ThemedText>
              {ex.isPending && <Loading />}
              {ex.isError && <Note tone="error">{ex.error.message}</Note>}
              {ex.data && (
                <>
                  <View style={styles.metrics}>
                    <Metric label="Score" value={signed(ex.data.score)} />
                    <Metric label="…from quality" value={signed(ex.data.quality_part)} />
                    <Metric label={`…from your ${source || 'other ratings'}`} value={signed(ex.data.transferred_part)} />
                  </View>
                  <View style={styles.lists}>
                    <TagList title="Pulling it up" tags={ex.data.pulling_up} />
                    <TagList title="Pushing it down" tags={ex.data.pushing_down} />
                  </View>
                  <ThemedText type="small" themeColor="textSecondary">
                    Score: the rating the model expects from you, on your ratings&apos; scale: +1 like, 0 meh, −1
                    dislike. Strong matches go past ±1. ↔ marks tags carried over from your ratings in another domain.
                  </ThemedText>
                </>
              )}
              <Button label="Close" onPress={onClose} />
            </ScrollView>
          </ThemedView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', padding: Spacing.three },
  sheetWrap: { alignSelf: 'center', width: '100%', maxWidth: 560, maxHeight: '90%' },
  sheet: { borderRadius: Spacing.four, borderWidth: StyleSheet.hairlineWidth, overflow: 'hidden' },
  content: { padding: Spacing.four, gap: Spacing.three },
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.three },
  metric: { minWidth: 110, flexGrow: 1 },
  metricValue: { fontSize: 22, lineHeight: 28 },
  lists: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.four },
  tagList: { flex: 1, minWidth: 200, gap: 2 },
  tagRow: { flexDirection: 'row', gap: Spacing.two },
});
