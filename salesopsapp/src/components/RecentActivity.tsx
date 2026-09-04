import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../hooks/useTheme';
import type { ActivityItem } from '../services/dashboardApi';

interface Props {
  items: ActivityItem[];
  initialCount?: number;
}

const INITIAL_COUNT = 5;

function formatTime(iso: string): string {
  try {
    const date = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60_000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    return `${Math.floor(diffHrs / 24)}d ago`;
  } catch {
    return '';
  }
}

function trimDescription(desc: string): string {
  const plain = desc.replace(/\*\*/g, '').replace(/\n/g, ' ');
  return plain.length > 80 ? plain.slice(0, 80).trimEnd() + '…' : plain;
}

export const RecentActivity = ({ items, initialCount = INITIAL_COUNT }: Props) => {
  const { colors, borderRadius } = useTheme();
  const [expanded, setExpanded] = useState(false);

  if (!items.length) return null;

  const visible = expanded ? items : items.slice(0, initialCount);
  const hasMore = items.length > initialCount;

  return (
    <View>
      {visible.map((item, index) => {
        const isMessage = item.type === 'message';
        const dotColor = isMessage ? colors.primary : colors.accent;
        const labelColor = isMessage ? colors.primary : colors.accent;
        const label = isMessage ? 'Message' : 'Tool';

        return (
          <View
            key={`${item.timestamp}-${index}`}
            style={[
              st.row,
              {
                backgroundColor: colors.surfaceHighlight,
                borderColor: colors.border,
                borderRadius: borderRadius.md,
                marginBottom: 8,
              },
            ]}
          >
            <View style={[st.dot, { backgroundColor: dotColor }]} />
            <View style={st.body}>
              <View style={st.topRow}>
                <Text style={[st.label, { color: labelColor }]}>{label}</Text>
                <Text style={[st.time, { color: colors.textMuted }]}>
                  {formatTime(item.timestamp)}
                </Text>
              </View>
              <Text style={[st.desc, { color: colors.text }]} numberOfLines={2}>
                {trimDescription(item.description)}
              </Text>
            </View>
          </View>
        );
      })}

      {hasMore && (
        <TouchableOpacity
          onPress={() => setExpanded(prev => !prev)}
          style={[
            st.toggleBtn,
            { borderColor: colors.border, borderRadius: borderRadius.md },
          ]}
        >
          <Text style={[st.toggleTxt, { color: colors.primary }]}>
            {expanded ? 'See less ↑' : `See more (${items.length - initialCount} more) ↓`}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const st = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 12,
    borderWidth: 1,
    gap: 10,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 5,
    flexShrink: 0,
  },
  body: { flex: 1 },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 3,
  },
  label: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  time: { fontSize: 11 },
  desc: { fontSize: 13, lineHeight: 18 },
  toggleBtn: {
    borderWidth: 1,
    paddingVertical: 10,
    alignItems: 'center',
    marginTop: 2,
  },
  toggleTxt: { fontSize: 13, fontWeight: '600' },
});
