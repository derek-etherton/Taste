/** Why a book scores what it does: its score (and the part carried over from other domains, when
 * there are any), and the tags pulling it up and pushing it down. */
import { ScrollView, StyleSheet, View } from 'react-native';

import type { ItemCard } from '@/api/client';
import { useExplanation } from '@/api/hooks';
import { openItem } from '@/components/item-row';
import { Button, Loading, Note, Section, Separator } from '@/components/kit';
import { Sheet } from '@/components/sheet';
import { ScoreBreakdown, signed } from '@/components/tag-charts';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useSettings } from '@/state/settings';

function Value({ label, value, first }: { label: string; value: string; first?: boolean }) {
  return (
    <>
      {!first && <Separator />}
      <View style={styles.value}>
        <ThemedText type="body" style={styles.flex}>
          {label}
        </ThemedText>
        <ThemedText type="body" themeColor="secondaryLabel" style={styles.number}>
          {value}
        </ThemedText>
      </View>
    </>
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
  const d = ex.data;
  return (
    <Sheet visible={item !== null} title={item?.title ?? ''} onClose={onClose}>
      <ScrollView contentContainerStyle={styles.content}>
        {ex.isPending && <Loading />}
        {ex.isError && <Note tone="error">{ex.error.message}</Note>}
        {d && (
          <>
            <Section
              title="Score"
              footer="The rating the model expects from you: +1 like, 0 meh, −1 dislike. Strong matches go past ±1.">
              <Value first label="Predicted rating" value={signed(d.score)} />
              {source ? <Value label={`From your ${source}`} value={signed(d.transferred_part, 3)} /> : null}
            </Section>
            <Section title="Why">
              <ScoreBreakdown up={d.pulling_up} down={d.pushing_down} source={source} />
            </Section>
            {item && (
              <Button
                variant="tinted"
                label="View Book"
                onPress={() => {
                  onClose();
                  openItem(item.key);
                }}
              />
            )}
          </>
        )}
      </ScrollView>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  content: { padding: Spacing.three, gap: Spacing.four, paddingBottom: Spacing.five },
  value: { flexDirection: 'row', alignItems: 'center', minHeight: 44, paddingHorizontal: Spacing.three, gap: Spacing.two },
  flex: { flex: 1 },
  number: { fontVariant: ['tabular-nums'] },
});
