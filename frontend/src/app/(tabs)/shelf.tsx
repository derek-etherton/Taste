/** Shelf scan: photograph a bookshelf, get the books on it ranked for you, with where to find them. */
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { ActivityIndicator, FlatList, Platform, StyleSheet, View } from 'react-native';

import type { ItemCard } from '@/api/client';
import { scanImageUrl, useScan, useStartScan } from '@/api/hooks';
import { ExplanationSheet } from '@/components/explanation-sheet';
import { ItemRow } from '@/components/item-row';
import { Button, LargeTitle, Loading, Note, Screen, Section, Separator, listPadding } from '@/components/kit';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

/** A camera to take a photo with: phones, and phone or tablet browsers (a finger as the main
 * pointer). Desktop browsers would only open a file picker, the same as Choose Photo. */
const HAS_CAMERA =
  Platform.OS !== 'web' || (typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches);

export default function ShelfScan() {
  const { user, quality } = useSettings();
  const theme = useTheme();
  const scan = useScan(user, quality);
  const start = useStartScan(user, quality);
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
    const options: ImagePicker.ImagePickerOptions = {
      mediaTypes: 'images',
      quality: 0.9,
      cameraType: ImagePicker.CameraType.back, // the shelf is in front of you
    };
    const result = camera ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
    if (result.canceled || !result.assets?.length) return;
    setPreview(result.assets[0].uri);
    start.mutate(result.assets[0]);
  }

  const s = scan.data;
  const running = start.isPending;
  const read = (s?.books.length ?? 0) + (s?.unmatched.length ?? 0);
  const photo = running && preview ? preview : (scanImageUrl(s?.image_url) ?? preview);
  const books = running ? [] : (s?.books ?? []);
  const done = !running && s && s.status !== 'none';

  const header = (
    <View style={styles.header}>
      <View>
        <LargeTitle title="Shelf Scan" />
        <ThemedText type="subheadline" themeColor="secondaryLabel">
          Photograph a bookshelf, at home or in a shop. We read the spines and sort the books we know by how much
          you&apos;d like them.
        </ThemedText>
      </View>
      <View style={styles.actions}>
        {HAS_CAMERA && (
          <Button
            variant="filled"
            icon={{ ios: 'camera', md: 'photo_camera' }}
            label="Take Photo"
            onPress={() => pick(true)}
            disabled={running}
          />
        )}
        <Button
          variant={HAS_CAMERA ? 'gray' : 'filled'}
          icon={{ ios: 'photo.on.rectangle', md: 'photo_library' }}
          label="Choose Photo"
          onPress={() => pick(false)}
          disabled={running}
        />
      </View>
      {problem && <Note tone="error">{problem}</Note>}
      {start.isError && <Note tone="error">{start.error.message}</Note>}
      {scan.isError && <Note tone="error">{scan.error.message}</Note>}

      {(photo || running) && (
        <Section>
          <View style={styles.result}>
            {photo && <Image source={{ uri: photo }} style={styles.photo} contentFit="cover" />}
            <View style={styles.summary}>
              {running ? (
                <>
                  <View style={styles.reading}>
                    <ActivityIndicator color={theme.secondaryLabel} />
                    <ThemedText type="headline">Reading the spines…</ThemedText>
                  </View>
                  <ThemedText type="footnote" themeColor="secondaryLabel">
                    Usually under a minute.
                  </ThemedText>
                </>
              ) : done ? (
                <>
                  <ThemedText type="headline">
                    {s.books.length} of {read} books recognised
                  </ThemedText>
                  <ThemedText type="footnote" themeColor="secondaryLabel">
                    {s.photo_name}, scanned {s.scanned?.replace('T', ' at ')}
                  </ThemedText>
                </>
              ) : null}
            </View>
          </View>
        </Section>
      )}
      {books.length > 0 && (
        <ThemedText type="title3" accessibilityRole="header" style={styles.listTitle}>
          On this shelf, best for you first
        </ThemedText>
      )}
    </View>
  );

  const footer =
    done && s.unmatched.length > 0 ? (
      <View style={styles.footer}>
        <Section title="Not in our catalogue" footer="Spines we read but couldn't find among our books.">
          {s.unmatched.map((u, i) => (
            <View key={`${u.title}-${i}`}>
              {i > 0 && <Separator />}
              <View style={styles.unmatched}>
                <ThemedText type="body">{u.title}</ThemedText>
                {u.author && (
                  <ThemedText type="subheadline" themeColor="secondaryLabel">
                    {u.author}
                  </ThemedText>
                )}
              </View>
            </View>
          ))}
        </Section>
      </View>
    ) : undefined;

  return (
    <Screen>
      <FlatList
        data={books}
        keyExtractor={(c) => c.key}
        renderItem={({ item, index }) => <ItemRow item={item} index={index} count={books.length} onExplain={setExplaining} />}
        ListHeaderComponent={header}
        ListEmptyComponent={scan.isPending ? <Loading /> : undefined}
        ListFooterComponent={footer}
        contentContainerStyle={listPadding}
      />
      <ExplanationSheet domain="book" item={explaining} onClose={() => setExplaining(null)} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { gap: Spacing.three, paddingBottom: Spacing.two },
  actions: { flexDirection: 'row', gap: Spacing.two, flexWrap: 'wrap' },
  result: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.three, padding: Spacing.three, alignItems: 'center' },
  photo: { width: 96, height: 128, borderRadius: Radius.field },
  summary: { flex: 1, minWidth: 200, gap: Spacing.two },
  reading: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  listTitle: { paddingHorizontal: Spacing.one, paddingTop: Spacing.two },
  footer: { paddingTop: Spacing.four },
  unmatched: { paddingVertical: 11, paddingHorizontal: Spacing.three },
});
