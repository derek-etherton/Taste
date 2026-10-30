/** Profile and quality-weight choices, shown at the top of each screen (the PoC's sidebar). */
import Slider from '@react-native-community/slider';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { useProfiles } from '@/api/hooks';
import { ThemedText } from '@/components/themed-text';
import { ACCENT, Chips } from '@/components/kit';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

export function SettingsBar({ showQuality = true }: { showQuality?: boolean }) {
  const { user, setUser, quality, setQuality } = useSettings();
  const profiles = useProfiles();
  return (
    <View style={styles.bar}>
      <View style={styles.row}>
        <ThemedText type="small" themeColor="textSecondary" style={styles.label}>
          Profile
        </ThemedText>
        <Chips options={(profiles.data ?? [user]).map((p) => ({ value: p, label: p }))} value={user} onChange={setUser} />
      </View>
      {showQuality && (
        <View style={styles.row}>
          <QualitySlider value={quality} onChange={setQuality} />
        </View>
      )}
    </View>
  );
}

/** 0 to 1 in steps of 0.05. Lists only refetch when you let go, not on every step of the drag. */
function QualitySlider({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  const theme = useTheme();
  const [dragging, setDragging] = useState<number | null>(null);
  return (
    <>
      <ThemedText type="small" themeColor="textSecondary" style={styles.label}>
        Weight on general quality: {(dragging ?? value).toFixed(2)}
      </ThemedText>
      <Slider
        style={styles.slider}
        minimumValue={0}
        maximumValue={1}
        step={0.05}
        value={value}
        onValueChange={setDragging}
        onSlidingComplete={(v) => {
          onChange(Math.round(v * 20) / 20);
          setDragging(null);
        }}
        minimumTrackTintColor={ACCENT}
        maximumTrackTintColor={theme.backgroundSelected}
        thumbTintColor={ACCENT}
      />
    </>
  );
}

const styles = StyleSheet.create({
  bar: { gap: Spacing.two, paddingVertical: Spacing.two },
  row: { gap: Spacing.one },
  label: { fontSize: 12 },
  slider: { width: '100%', maxWidth: 320, height: 28 },
});
