/**
 * PlaybookCard.tsx
 *
 * Playbook list item with colored icon circle, title, description,
 * and chevron. Color-coded by playbook type.
 */

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../hooks/useTheme';
import { ChevronRight } from '../constants/icons';

interface PlaybookCardProps {
  icon: React.ReactNode;
  iconBg: string;
  title: string;
  desc: string;
  rightIcon?: React.ReactNode;
  onPress?: () => void;
}

export const PlaybookCard = ({
  icon,
  iconBg,
  title,
  desc,
  rightIcon,
  onPress,
}: PlaybookCardProps) => {
  const { colors, spacing, borderRadius, mode } = useTheme();

  return (
    <TouchableOpacity
      style={[
        s.playbookCard,
        {
          backgroundColor: mode === 'dark' ? colors.surface : colors.card,
          borderColor: colors.border,
          borderRadius: borderRadius.lg,
          padding: spacing.md,
        },
        mode === 'light' && s.lightShadow,
      ]}
      activeOpacity={0.7}
      onPress={onPress}>
      <View style={[s.playbookIcon, { backgroundColor: iconBg + '20', borderRadius: 22 }]}>
        {icon}
      </View>
      <View style={s.playbookText}>
        <Text style={[s.playbookTitle, { color: colors.text }]}>{title}</Text>
        <Text style={[s.playbookDesc, { color: colors.textSecondary }]}>{desc}</Text>
      </View>
      {rightIcon || <ChevronRight size={18} color={colors.textMuted} />}
    </TouchableOpacity>
  );
};

const s = StyleSheet.create({
  playbookCard: {
    flexDirection: 'row', alignItems: 'center', borderWidth: 1, gap: 12,
  },
  playbookIcon: {
    width: 44, height: 44,
    justifyContent: 'center', alignItems: 'center',
  },
  playbookText: { flex: 1, gap: 2 },
  playbookTitle: { fontSize: 15, fontWeight: '600' },
  playbookDesc: { fontSize: 13, lineHeight: 18 },
  lightShadow: {
    shadowColor: '#64748B',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
});
