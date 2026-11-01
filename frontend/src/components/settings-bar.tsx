/** Profile, quality-weight and book-genome choices, shown at the top of each screen (the PoC's sidebar). */
import Slider from '@react-native-community/slider';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { useGenomes, useProfiles, useSwitchGenome } from '@/api/hooks';
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
      <GenomePicker domain="book" label="Book genome" />
      {showQuality && (
        <View style={styles.row}>
          <QualitySlider value={quality} onChange={setQuality} />
        </View>
      )}
    </View>
  );
}

/** Which genome a domain's catalogue is built from. Server-wide (a testing switch); hidden with one option. */
function GenomePicker({ domain, label }: { domain: string; label: string }) {
  const genomes = useGenomes();
  const switchGenome = useSwitchGenome();
  const g = genomes.data?.find((x) => x.domain === domain);
  if (!g || g.options.length < 2) return null;
  const linked = g.linked == null ? '' : `, ${g.linked} linked`;
  return (
    <View style={styles.row}>
      <ThemedText type="small" themeColor="textSecondary" style={styles.label}>
        {label}: {switchGenome.isPending ? 'switching…' : `${g.items} books${linked}`}
        {switchGenome.error ? ` (${switchGenome.error.message})` : ''}
      </ThemedText>
      <Chips
        options={g.options.map((o) => ({ value: o.name, label: o.name }))}
        value={switchGenome.isPending ? switchGenome.variables.genome : g.active}
        onChange={(genome) => genome !== g.active && !switchGenome.isPending && switchGenome.mutate({ domain, genome })}
      />
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
