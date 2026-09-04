/**
 * GlassCard.tsx
 *
 * Glassmorphism card with translucent background, subtle border,
 * rounded corners, and soft shadow. Supports intensity variants.
 */

import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { useTheme } from '../hooks/useTheme';

interface GlassCardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  variant?: 'default' | 'elevated' | 'subtle';
  noPadding?: boolean;
}

export const GlassCard = ({
  children,
  style,
  variant = 'default',
  noPadding = false,
}: GlassCardProps) => {
  const { colors, borderRadius, spacing, mode } = useTheme();

  const getBg = () => {
    if (mode === 'dark') {
      switch (variant) {
        case 'elevated': return 'rgba(18, 31, 53, 0.8)';
        case 'subtle': return 'rgba(13, 23, 40, 0.4)';
        default: return colors.glassBg;
      }
    } else {
      switch (variant) {
        case 'elevated': return 'rgba(255, 255, 255, 0.9)';
        case 'subtle': return 'rgba(255, 255, 255, 0.5)';
        default: return colors.glassBg;
      }
    }
  };

  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: getBg(),
          borderColor: colors.glassStroke,
          borderRadius: borderRadius.lg,
          padding: noPadding ? 0 : spacing.md,
        },
        mode === 'light' && styles.lightShadow,
        mode === 'dark' && styles.darkShadow,
        style,
      ]}>
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    overflow: 'hidden',
  },
  darkShadow: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 6,
  },
  lightShadow: {
    shadowColor: '#64748B',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
});
