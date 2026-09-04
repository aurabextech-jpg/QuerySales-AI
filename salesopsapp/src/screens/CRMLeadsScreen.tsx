import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../hooks/useTheme';
import { ArrowLeft, Mail, Phone, Calendar } from '../constants/icons';
import { useNavigation } from '@react-navigation/native';
import { discoveryApi, type Lead } from '../services/discoveryApi';

function formatDate(raw: string): string {
  try {
    return new Date(raw).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return raw;
  }
}

export const CRMLeadsScreen = () => {
  const { colors, spacing, borderRadius } = useTheme();
  const navigation = useNavigation();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLeads = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await discoveryApi.getLeads(50, 0);
      setLeads(res.data.filter(l => l.status.toLowerCase() === 'opportunity'));
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load leads');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const renderLead = ({ item }: { item: Lead }) => (
    <View style={[
      styles.card,
      {
        backgroundColor: colors.surface,
        borderColor: colors.primary,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        marginBottom: spacing.md,
      },
    ]}>
      <View style={styles.cardHeader}>
        <Text style={[styles.name, { color: colors.text, flex: 1 }]} numberOfLines={1}>
          {item.lead_name}
        </Text>
        <View style={[styles.statusBadge, { backgroundColor: colors.primaryMuted }]}>
          <Text style={{ color: colors.primary, fontSize: 12, fontWeight: '700' }}>{item.status}</Text>
        </View>
      </View>

      <Text style={[styles.crmId, { color: colors.textMuted }]}>{item.name}</Text>

      {item.email_id ? (
        <View style={[styles.row, { marginTop: spacing.sm }]}>
          <Mail size={14} color={colors.textMuted} />
          <Text style={[styles.infoText, { color: colors.textSecondary }]}>{item.email_id}</Text>
        </View>
      ) : null}

      {item.mobile_no ? (
        <View style={[styles.row, { marginTop: spacing.xs }]}>
          <Phone size={14} color={colors.textMuted} />
          <Text style={[styles.infoText, { color: colors.textSecondary }]}>{item.mobile_no}</Text>
        </View>
      ) : null}

      <View style={[styles.row, { marginTop: spacing.sm }]}>
        <Calendar size={13} color={colors.textMuted} />
        <Text style={[styles.dateText, { color: colors.textMuted }]}>Added {formatDate(item.creation)}</Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <View style={[styles.header, { paddingHorizontal: spacing.xl, paddingVertical: spacing.md }]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <ArrowLeft size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Opportunity Leads</Text>
        <View style={{ width: 24 }} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} size="large" />
          <Text style={[styles.loadingTxt, { color: colors.textMuted }]}>Loading leads…</Text>
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={[styles.errorTxt, { color: colors.textSecondary }]}>{error}</Text>
          <TouchableOpacity
            onPress={() => fetchLeads()}
            style={[styles.retryBtn, { borderColor: colors.primary, borderRadius: borderRadius.md }]}>
            <Text style={[styles.retryTxt, { color: colors.primary }]}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={leads}
          keyExtractor={item => item.name}
          renderItem={renderLead}
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={[styles.emptyTxt, { color: colors.textMuted }]}>No opportunity leads found.</Text>
            </View>
          }
          contentContainerStyle={{ paddingHorizontal: spacing.xl, paddingBottom: spacing.xl, paddingTop: spacing.md }}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => fetchLeads(true)}
              tintColor={colors.primary}
            />
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
  card: { borderWidth: 1 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  name: { fontSize: 18, fontWeight: '700' },
  crmId: { fontSize: 12, marginTop: 2 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  infoText: { fontSize: 14 },
  dateText: { fontSize: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 40, gap: 12 },
  loadingTxt: { fontSize: 14, marginTop: 8 },
  errorTxt: { fontSize: 14, textAlign: 'center', paddingHorizontal: 24 },
  retryBtn: { borderWidth: 1, paddingHorizontal: 20, paddingVertical: 8 },
  retryTxt: { fontSize: 14, fontWeight: '600' },
  emptyTxt: { fontSize: 15 },
});
