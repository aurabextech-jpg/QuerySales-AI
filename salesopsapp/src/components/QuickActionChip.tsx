/**
 * QuickActionChip.tsx
 *
 * Pill-shaped action chip with aurora border styling.
 * Used in chat for quick actions like "Find new leads", "Check my pipeline".
 */

import React from 'react';
import { Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../hooks/useTheme';

interface QuickActionChipProps {
  label: string;
  onPress?: () => void;
  active?: boolean;
}

export const QuickActionChip = ({
  label,
  onPress,
  active = false,
}: QuickActionChipProps) => {
  const { colors, borderRadius, mode } = useTheme();

  return (
    <TouchableOpacity
      style={[
        styles.chip,
        {
          backgroundColor: active
            ? colors.primary
            : mode === 'dark'
              ? colors.surfaceHighlight
              : colors.surfaceHighlight,
          borderColor: active ? colors.primary : colors.border,
          borderRadius: borderRadius.round,
        },
      ]}
      onPress={onPress}
      activeOpacity={0.7}>
      <Text
        style={[
          styles.label,
          {
            color: active ? '#FFFFFF' : colors.text,
          },
        ]}>
        {label}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderWidth: 1,
  },
  label: {
    fontSize: 13,
    fontWeight: '500',
    letterSpacing: 0.2,
  },
});
