/** Shelf scan: photograph a bookshelf, get the books on it ranked for you, with where to find them. */
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { FlatList, Platform, StyleSheet, View } from 'react-native';

import type { ItemCard } from '@/api/client';
import { scanImageUrl, useScan, useStartScan } from '@/api/hooks';
import { ExplanationSheet } from '@/components/explanation-sheet';
import { ItemRow } from '@/components/item-row';
import { ACCENT, Button, Loading, Note, Screen, listPadding } from '@/components/kit';
import { ThemedText } from '@/components/themed-text';
import { Collapsible } from '@/components/ui/collapsible';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

export default function ShelfScan() {
  const { user, quality } = useSettings();
  const theme = useTheme();
  const scan = useScan(user, quality);
  const start = useStartScan(user);
  const [preview, setPreview] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [explaining, setExplaining] = useState<ItemCard | null>(null);

  async function pick(camera: boolean) {
    setProblem(null);
    if (camera) {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        setProblem('Camera access is needed to take a photo. You can allow it in Settings, or choose a photo instead.');
        return;
      }
    }
    const options: ImagePicker.ImagePickerOptions = { mediaTypes: 'images', quality: 0.9 };
    const result = camera ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
    if (result.canceled || !result.assets?.length) return;
    setPreview(result.assets[0].uri);
    start.mutate(result.assets[0]);
  }

  const s = scan.data;
  const running = start.isPending || s?.status === 'running';
  const progress = s?.progress && s.progress.total ? s.progress.done / s.progress.total : 0;
  const read = (s?.books.length ?? 0) + (s?.unmatched.length ?? 0);
  const photo = running && preview ? preview : s?.scanned ? scanImageUrl(user, s.scanned) : preview;

  const header = (
    <View style={styles.header}>
      <ThemedText type="small" themeColor="textSecondary">
        Snap or upload a photo of a bookshelf, at home or in a shop. We read the spines and sort the books we know by how
        much you&apos;d like them.
      </ThemedText>
      <View style={styles.actions}>
        {Platform.OS !== 'web' && <Button primary label="Take photo" onPress={() => pick(true)} disabled={running} />}
        <Button primary={Platform.OS === 'web'} label="Choose photo" onPress={() => pick(false)} disabled={running} />
      </View>
      {problem && <Note tone="error">{problem}</Note>}
      {start.isError && <Note tone="error">{start.error.message}</Note>}
      {s?.status === 'failed' && <Note tone="error">{`That scan failed: ${s.error}`}</Note>}
      {scan.isError && <Note tone="error">{scan.error.message}</Note>}

      {(photo || running) && (
        <View style={styles.result}>
          {photo && <Image source={{ uri: photo }} style={styles.photo} contentFit="contain" />}
          <View style={styles.summary}>
            {running ? (
              <>
                <ThemedText type="smallBold">
                  {s?.progress?.total ? `Reading the spines: part ${Math.min(s.progress.done + 1, s.progress.total)} of ${s.progress.total}…` : 'Finding the shelves…'}
                </ThemedText>
                <View style={[styles.track, { backgroundColor: theme.backgroundElement }]}>
                  <View style={[styles.fill, { width: `${Math.round(progress * 100)}%` }]} />
                </View>
                <ThemedText type="small" themeColor="textSecondary">
                  About a minute for a full bookcase.
                </ThemedText>
              </>
            ) : s?.status !== 'none' && s ? (
              <>
                <ThemedText type="smallBold">
                  On this shelf, best for you first · {s.books.length} of {read} books recognised
                </ThemedText>
                <ThemedText type="small" themeColor="textSecondary">
                  {s.photo_name}, scanned {s.scanned?.replace('T', ' at ')}
                </ThemedText>
                {s.unmatched.length > 0 && (
                  <Collapsible title={`Read but not in our catalogue (${s.unmatched.length})`}>
                    {s.unmatched.map((u, i) => (
                      <ThemedText key={`${u.title}-${i}`} type="small">
                        • {u.title}
                        {u.author ? ` · ${u.author}` : ''}
                      </ThemedText>
                    ))}
                  </Collapsible>
                )}
              </>
            ) : null}
          </View>
        </View>
      )}
    </View>
  );

  return (
    <Screen>
      <FlatList
        data={running ? [] : (s?.books ?? [])}
        keyExtractor={(c) => c.key}
        renderItem={({ item, index }) => <ItemRow item={item} rank={index + 1} onExplain={setExplaining} />}
        ListHeaderComponent={header}
        ListEmptyComponent={scan.isPending ? <Loading /> : undefined}
        contentContainerStyle={listPadding}
      />
      <ExplanationSheet domain="book" item={explaining} onClose={() => setExplaining(null)} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { gap: Spacing.three, paddingBottom: Spacing.two },
  actions: { flexDirection: 'row', gap: Spacing.two, flexWrap: 'wrap' },
  result: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.three },
  photo: { width: 160, height: 220, borderRadius: Spacing.two },
  summary: { flex: 1, minWidth: 220, gap: Spacing.two },
  track: { height: 8, borderRadius: 4, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4, backgroundColor: ACCENT },
});
