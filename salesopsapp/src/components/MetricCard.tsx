/**
 * MetricCard.tsx
 *
 * Enhanced metric card with glassmorphism, trend indicators,
 * and "vs last 7 days" subtext. Used in Home and Outcome screens.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../hooks/useTheme';
import { TrendingUp, TrendingDown } from '../constants/icons';

interface MetricCardProps {
  title: string;
  value: string;
  trendValue?: string;
  trendLabel?: string;
  positive?: boolean;
  badgeText?: string;
  badgeColor?: string;
}

export const MetricCard = ({
  title,
  value,
  trendValue,
  trendLabel,
  positive = true,
  badgeText,
  badgeColor,
}: MetricCardProps) => {
  const { colors, spacing, borderRadius, mode } = useTheme();
  const tColor = positive ? colors.success : colors.warning;

  return (
    <View style={[
      s.metricCard,
      {
        backgroundColor: mode === 'dark' ? colors.surface : colors.card,
        borderColor: colors.border,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
      },
      mode === 'light' && s.lightShadow,
    ]}>
      <Text style={[s.metricTitle, { color: colors.textSecondary }]}>{title}</Text>
      <Text style={[s.metricValue, { color: colors.text }]}>{value}</Text>
      {trendValue ? (
        <View style={s.trendRow}>
          {positive ? (
            <TrendingUp size={12} color={tColor} />
          ) : (
            <TrendingDown size={12} color={tColor} />
          )}
          <Text style={[s.trendText, { color: tColor }]}>{trendValue}</Text>
          {trendLabel && (
            <Text style={[s.trendLabel, { color: colors.textMuted }]}>{trendLabel}</Text>
          )}
        </View>
      ) : badgeText ? (
        <View style={[
          s.badge,
          { backgroundColor: (badgeColor || colors.warning) + '20', borderRadius: borderRadius.xs },
        ]}>
          <Text style={[s.badgeLabel, { color: badgeColor || colors.warning }]}>{badgeText}</Text>
        </View>
      ) : null}
    </View>
  );
};

const s = StyleSheet.create({
  metricCard: { flex: 1, borderWidth: 1 },
  lightShadow: {
    shadowColor: '#64748B',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  metricTitle: { fontSize: 12, fontWeight: '500', marginBottom: 6 },
  metricValue: { fontSize: 28, fontWeight: '700', letterSpacing: -0.5, marginBottom: 8 },
  trendRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  trendText: { fontSize: 12, fontWeight: '600' },
  trendLabel: { fontSize: 11, fontWeight: '400' },
  badge: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3 },
  badgeLabel: { fontSize: 11, fontWeight: '600' },
});
