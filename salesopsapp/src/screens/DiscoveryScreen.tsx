import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../hooks/useTheme';
import { Mail, Phone, ArrowLeft, Users } from '../constants/icons';
import { useNavigation } from '@react-navigation/native';
import { discoveryApi, type Lead } from '../services/discoveryApi';

const PAGE_SIZE = 10;

function statusColor(
  status: string,
  colors: Record<string, string>,
): { bg: string; border: string; text: string } {
  switch (status.toLowerCase()) {
    case 'opportunity':
      return { bg: colors.primaryMuted, border: colors.primary, text: colors.primary };
    case 'lead':
      return { bg: colors.successMuted, border: colors.success, text: colors.success };
    case 'converted':
      return { bg: colors.accentMuted ?? colors.successMuted, border: colors.accent, text: colors.accent };
    default:
      return { bg: colors.surfaceHighlight, border: colors.border, text: colors.textMuted };
  }
}

function formatDate(raw: string): string {
  try {
    return new Date(raw).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return raw;
  }
}

export const DiscoveryScreen = () => {
  const { colors, spacing, borderRadius } = useTheme();
  const navigation = useNavigation();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);

  const fetchLeads = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await discoveryApi.getLeads(PAGE_SIZE, 0);
      setLeads(res.data);
      setTotal(res.total_returned);
      setOffset(PAGE_SIZE);
      setHasMore(res.data.length === PAGE_SIZE);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load leads');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) {
      return;
    }
    try {
      setLoadingMore(true);
      const res = await discoveryApi.getLeads(PAGE_SIZE, offset);
      setLeads(prev => [...prev, ...res.data]);
      setOffset(prev => prev + PAGE_SIZE);
      setHasMore(res.data.length === PAGE_SIZE);
    } catch {
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, offset]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const renderLead = ({ item }: { item: Lead }) => {
    const sc = statusColor(item.status, colors as unknown as Record<string, string>);
    return (
      <View style={[
        styles.card,
        {
          backgroundColor: colors.surface,
          borderColor: colors.border,
          borderRadius: borderRadius.sm,
          padding: spacing.md,
          marginBottom: spacing.md,
        },
      ]}>
        <View style={styles.cardHeader}>
          <Text style={[styles.name, { color: colors.text, flex: 1 }]} numberOfLines={1}>
            {item.lead_name}
          </Text>
          <View style={[styles.badge, { backgroundColor: sc.bg, borderColor: sc.border }]}>
            <Text style={{ color: sc.text, fontSize: 11, fontWeight: '700' }}>{item.status}</Text>
          </View>
        </View>

        <Text style={[styles.crmId, { color: colors.textMuted }]}>{item.name}</Text>

        {item.email_id ? (
          <View style={[styles.row, { marginTop: spacing.sm }]}>
            <Mail size={13} color={colors.textMuted} />
            <Text style={[styles.detail, { color: colors.textSecondary }]}>{item.email_id}</Text>
          </View>
        ) : null}

        {item.mobile_no ? (
          <View style={[styles.row, { marginTop: 4 }]}>
            <Phone size={13} color={colors.textMuted} />
            <Text style={[styles.detail, { color: colors.textSecondary }]}>{item.mobile_no}</Text>
          </View>
        ) : null}

        <Text style={[styles.date, { color: colors.textMuted, marginTop: spacing.sm }]}>
          Added {formatDate(item.creation)}
        </Text>
      </View>
    );
  };

  const ListHeader = () => (
    <>
      <View style={[
        styles.infoBar,
        {
          backgroundColor: colors.primaryMuted,
          borderRadius: borderRadius.md,
          padding: spacing.md,
          marginBottom: spacing.lg,
        },
      ]}>
        <View style={styles.row}>
          <Users size={16} color={colors.primary} />
          <Text style={[styles.infoTitle, { color: colors.primary }]}>
            CRM Leads  ·  {total} total
          </Text>
        </View>
        <Text style={[styles.infoSub, { color: colors.textSecondary, marginTop: 4 }]}>
          Pulled from ERPNext CRM
        </Text>
      </View>
    </>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <View style={[styles.header, { paddingHorizontal: spacing.lg, paddingVertical: spacing.md }]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <ArrowLeft size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Lead Discovery</Text>
        <View style={{ width: 32 }} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} size="large" />
          <Text style={[styles.loadingTxt, { color: colors.textMuted }]}>Loading leads…</Text>
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={[styles.errorTxt, { color: colors.textSecondary }]}>{error}</Text>
          <TouchableOpacity onPress={() => fetchLeads()} style={[styles.retryBtn, { borderColor: colors.primary, borderRadius: borderRadius.md }]}>
            <Text style={[styles.retryTxt, { color: colors.primary }]}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={leads}
          keyExtractor={item => item.name}
          renderItem={renderLead}
          ListHeaderComponent={<ListHeader />}
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={[styles.emptyTxt, { color: colors.textMuted }]}>No leads found.</Text>
            </View>
          }
          contentContainerStyle={{ paddingHorizontal: spacing.xl, paddingBottom: spacing.xl }}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => fetchLeads(true)}
              tintColor={colors.primary}
            />
          }
          onEndReached={loadMore}
          onEndReachedThreshold={0.3}
          ListFooterComponent={
            loadingMore ? (
              <View style={styles.footer}>
                <ActivityIndicator size="small" color={colors.primary} />
              </View>
            ) : null
          }
        />
      )}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 20, fontWeight: '700' },
  infoBar: { borderWidth: 1, borderColor: 'rgba(99,102,241,0.2)' },
  infoTitle: { fontSize: 15, fontWeight: '700' },
  infoSub: { fontSize: 13 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  card: { borderWidth: 1 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  name: { fontSize: 16, fontWeight: '700' },
  crmId: { fontSize: 12, marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, borderWidth: 1 },
  detail: { fontSize: 13 },
  date: { fontSize: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 40, gap: 12 },
  loadingTxt: { fontSize: 14, marginTop: 8 },
  errorTxt: { fontSize: 14, textAlign: 'center', paddingHorizontal: 24 },
  retryBtn: { borderWidth: 1, paddingHorizontal: 20, paddingVertical: 8, marginTop: 4 },
  retryTxt: { fontSize: 14, fontWeight: '600' },
  emptyTxt: { fontSize: 15 },
  footer: { paddingVertical: 16, alignItems: 'center' },
});
