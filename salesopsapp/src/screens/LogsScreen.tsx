import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useTheme } from '../hooks/useTheme';
import { RunLogCard } from '../components/RunLogCard';
import { runsApi } from '../services/runsApi';
import type { Run } from '../services/runsApi';
import { ArrowLeft } from '../constants/icons';

const LIMIT = 10;

export const LogsScreen = () => {
  const navigation = useNavigation();
  const { colors, spacing, borderRadius } = useTheme();

  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      const data = await runsApi.getRuns(LIMIT, 0);
      setRuns(data);
      setOffset(LIMIT);
      setHasMore(data.length === LIMIT);
    } catch (e: any) {
      setError(e?.message || 'Failed to load logs.');
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
      const data = await runsApi.getRuns(LIMIT, offset);
      setRuns(prev => [...prev, ...data]);
      setOffset(prev => prev + LIMIT);
      setHasMore(data.length === LIMIT);
    } catch {
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, offset]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const renderItem = useCallback(
    ({ item }: { item: Run }) => <RunLogCard run={item} />,
    [],
  );

  const keyExtractor = useCallback((item: Run) => item.id, []);

  return (
    <SafeAreaView
      style={[st.safe, { backgroundColor: colors.background }]}
      edges={['top', 'left', 'right']}
    >
      <View style={[st.header]}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          style={st.backBtn}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <ArrowLeft size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={[st.title, { color: colors.text }]}>Run Logs</Text>
        <View style={st.backBtn} />
      </View>

      {loading ? (
        <View style={st.center}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={[st.loadingTxt, { color: colors.textMuted }]}>
            Loading logs…
          </Text>
        </View>
      ) : error ? (
        <View style={st.center}>
          <Text style={[st.errorTxt, { color: colors.error }]}>{error}</Text>
          <TouchableOpacity
            onPress={() => fetchRuns()}
            style={[
              st.retryBtn,
              {
                backgroundColor: colors.primary,
                borderRadius: borderRadius.md,
              },
            ]}
          >
            <Text style={st.retryTxt}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={runs}
          keyExtractor={keyExtractor}
          renderItem={renderItem}
          contentContainerStyle={[
            st.list,
            { paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
          ]}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => fetchRuns(true)}
              tintColor={colors.primary}
            />
          }
          ListHeaderComponent={
            runs.length > 0 ? (
              <Text style={[st.count, { color: colors.textMuted }]}>
                {runs.length} run{runs.length !== 1 ? 's' : ''} found
              </Text>
            ) : null
          }
          ListEmptyComponent={
            <View style={st.center}>
              <Text style={[st.emptyTxt, { color: colors.textMuted }]}>
                No runs yet.
              </Text>
            </View>
          }
          ListFooterComponent={
            loadingMore ? (
              <View style={st.footer}>
                <ActivityIndicator size="small" color={colors.primary} />
              </View>
            ) : null
          }
          onEndReached={loadMore}
          onEndReachedThreshold={0.3}
          removeClippedSubviews
        />
      )}
    </SafeAreaView>
  );
};

const st = StyleSheet.create({
  safe: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  backBtn: { width: 32 },
  title: { fontSize: 17, fontWeight: '700' },
  list: { flexGrow: 1 },
  count: { fontSize: 12, marginBottom: 10 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  loadingTxt: { fontSize: 14, marginTop: 8 },
  errorTxt: { fontSize: 14, textAlign: 'center', paddingHorizontal: 24 },
  retryBtn: { paddingHorizontal: 24, paddingVertical: 10 },
  retryTxt: { color: '#fff', fontWeight: '700', fontSize: 14 },
  emptyTxt: { fontSize: 14 },
  footer: { paddingVertical: 16, alignItems: 'center' },
});
