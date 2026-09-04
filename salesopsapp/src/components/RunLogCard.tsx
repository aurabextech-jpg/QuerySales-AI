import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../hooks/useTheme';
import type { Run } from '../services/runsApi';

interface Props {
  run: Run;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function statusColor(
  status: string,
  colors: { success: string; error: string; warning: string; textMuted: string },
): string {
  switch (status) {
    case 'completed':
      return colors.success;
    case 'running':
      return colors.warning;
    case 'failed':
      return colors.error;
    default:
      return colors.textMuted;
  }
}

export const RunLogCard = ({ run }: Props) => {
  const { colors, spacing, borderRadius } = useTheme();
  const dotColor = statusColor(run.status, colors as any);

  return (
    <View
      style={[
        st.card,
        {
          backgroundColor: colors.surface,
          borderColor: colors.border,
          borderRadius: borderRadius.md,
          marginBottom: spacing.sm,
        },
      ]}
    >
      <View style={st.header}>
        <View style={st.statusRow}>
          <View style={[st.dot, { backgroundColor: dotColor }]} />
          <Text style={[st.status, { color: dotColor }]}>
            {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
          </Text>
        </View>
        <Text style={[st.date, { color: colors.textMuted }]}>
          {formatDate(run.created_at)}
        </Text>
      </View>

      <View style={st.row}>
        <Chip label={run.workflow_type} colors={colors} />
        <Chip label={run.mode} colors={colors} />
      </View>

      <View style={[st.footer, { borderTopColor: colors.border }]}>
        <Stat label="Tool calls" value={run.tool_call_count} colors={colors} />
        <Stat label="Traces" value={run.trace_count} colors={colors} />
      </View>
    </View>
  );
};

const Chip = ({
  label,
  colors,
}: {
  label: string;
  colors: any;
}) => (
  <View
    style={[
      st.chip,
      { backgroundColor: colors.surfaceHighlight, borderColor: colors.border },
    ]}
  >
    <Text style={[st.chipTxt, { color: colors.textSecondary }]}>{label}</Text>
  </View>
);

const Stat = ({
  label,
  value,
  colors,
}: {
  label: string;
  value: number;
  colors: any;
}) => (
  <View style={st.stat}>
    <Text style={[st.statValue, { color: colors.text }]}>{value}</Text>
    <Text style={[st.statLabel, { color: colors.textMuted }]}>{label}</Text>
  </View>
);

const st = StyleSheet.create({
  card: {
    borderWidth: 1,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 8,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  status: {
    fontSize: 13,
    fontWeight: '700',
  },
  date: {
    fontSize: 12,
  },
  row: {
    flexDirection: 'row',
    gap: 6,
    paddingHorizontal: 14,
    paddingBottom: 10,
  },
  chip: {
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  chipTxt: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  footer: {
    flexDirection: 'row',
    borderTopWidth: 1,
    paddingVertical: 10,
    paddingHorizontal: 14,
    gap: 20,
  },
  stat: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 4,
  },
  statValue: {
    fontSize: 14,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 12,
  },
});
