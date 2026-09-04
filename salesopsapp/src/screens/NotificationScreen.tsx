/**
 * screens/NotificationScreen.tsx
 *
 * Displays a list of mock notifications.
 */

import React from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../hooks/useTheme';
import { Bell, CheckCircle, AlertTriangle, Info, Clock } from '../constants/icons';

type Notification = {
  id: string;
  title: string;
  message: string;
  type: 'success' | 'warning' | 'info';
  time: string;
  isRead: boolean;
};

const mockNotifications: Notification[] = [
  {
    id: '1',
    title: 'New Lead Discovered',
    message: 'Found a potential lead in Gulberg Lahore matching your criteria.',
    type: 'success',
    time: '2m ago',
    isRead: false,
  },
  {
    id: '2',
    title: 'Meeting Scheduled',
    message: 'Google Calendar event created for product demo with Tech Innovators.',
    type: 'info',
    time: '1h ago',
    isRead: false,
  },
  {
    id: '3',
    title: 'Duplicate Detected',
    message: 'A lead you tried to create already exists in ERPNext.',
    type: 'warning',
    time: '3h ago',
    isRead: true,
  },
  {
    id: '4',
    title: 'Daily Summary',
    message: 'You have 5 follow-ups pending for today.',
    type: 'info',
    time: '1d ago',
    isRead: true,
  },
];

export const NotificationScreen = () => {
  const { colors, spacing, borderRadius } = useTheme();

  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return <CheckCircle size={20} color={colors.success} />;
      case 'warning':
        return <AlertTriangle size={20} color={colors.warning} />;
      case 'info':
        return <Info size={20} color={colors.info} />;
    }
  };

  const renderItem = ({ item }: { item: Notification }) => (
    <TouchableOpacity
      style={[
        styles.card,
        {
          backgroundColor: item.isRead ? colors.surface : colors.surfaceHighlight,
          borderColor: colors.border,
          borderRadius: borderRadius.lg,
          padding: spacing.md,
          marginBottom: spacing.md,
        },
      ]}
      activeOpacity={0.7}
    >
      <View style={styles.cardHeader}>
        <View style={styles.iconContainer}>{getIcon(item.type)}</View>
        <Text style={[styles.title, { color: colors.text, flex: 1 }]}>{item.title}</Text>
        <Text style={[styles.time, { color: colors.textMuted }]}>{item.time}</Text>
      </View>
      <Text style={[styles.message, { color: colors.textSecondary, marginTop: spacing.sm }]}>
        {item.message}
      </Text>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <View style={[styles.header, { paddingHorizontal: spacing.xl, paddingTop: spacing.md, paddingBottom: spacing.lg }]}>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Notifications</Text>
        <TouchableOpacity style={styles.markAllRead}>
          <Text style={[styles.markAllReadText, { color: colors.primary }]}>Mark all read</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={mockNotifications}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={{ paddingHorizontal: spacing.xl, paddingBottom: spacing.xl }}
        showsVerticalScrollIndicator={false}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: '700',
  },
  markAllRead: {
    paddingVertical: 4,
  },
  markAllReadText: {
    fontSize: 14,
    fontWeight: '600',
  },
  card: {
    borderWidth: 1,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconContainer: {
    marginRight: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
  },
  time: {
    fontSize: 12,
  },
  message: {
    fontSize: 14,
    lineHeight: 20,
  },
});
