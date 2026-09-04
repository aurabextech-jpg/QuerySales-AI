/**
 * OutcomeDashboardScreen.tsx — Aurora Intelligence Outcome Report.
 *
 * Gradient hero, impact metrics, workflow checklist, action buttons.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Defs, LinearGradient, Stop, Rect } from 'react-native-svg';
import { useTheme } from '../hooks/useTheme';
import { ArrowLeft, CheckCircle2, Clock, ArrowRight, Database } from '../constants/icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { agentApi } from '../services/agentApi';
import { MetricCard } from '../components/MetricCard';

const WORKFLOW_ITEMS = [
  { label: 'Search & Discovery', done: true },
  { label: 'Filter & Enrichment', done: true },
  { label: 'Scoring & Prioritization', done: true },
  { label: 'Saved to ERPNext CRM', done: true },
];

export const OutcomeDashboardScreen = () => {
  const { colors, spacing, borderRadius, mode } = useTheme();
  const navigation = useNavigation();
  const route = useRoute<any>();
  const runId: string | undefined = route.params?.runId;
  const [metrics, setMetrics] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setError('No workflow run selected.');
      return;
    }
    (async () => {
      try {
        const result = await agentApi.getOutcomeMetrics(runId);
        setMetrics(result.metrics);
      } catch (e: any) {
        setError(e?.message ?? 'Failed to load outcome data.');
      }
    })();
  }, [runId]);

  if (error) {
    return (
      <SafeAreaView style={[st.root, { backgroundColor: colors.background }]} edges={['top']}>
        <View style={st.center}>
          <Text style={{ color: colors.textMuted, fontSize: 14, textAlign: 'center' }}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!metrics) {
    return (
      <SafeAreaView style={[st.root, { backgroundColor: colors.background }]} edges={['top']}>
        <View style={st.center}><ActivityIndicator size="large" color={colors.primary} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[st.root, { backgroundColor: colors.background }]} edges={['top']}>
      {/* Header */}
      <View style={[st.header, { paddingHorizontal: spacing.xl, paddingVertical: spacing.md }]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={st.backBtn}>
          <ArrowLeft size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={[st.headerTitle, { color: colors.text }]}>Outcome Report</Text>
        <View style={{ width: 22 }} />
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: spacing.xl, paddingBottom: spacing.xxl }} showsVerticalScrollIndicator={false}>
        {/* Hero Card */}
        <View style={[st.heroCard, { borderRadius: borderRadius.xl, overflow: 'hidden', marginBottom: spacing.xl }]}>
          <View style={StyleSheet.absoluteFill}>
            <Svg width="100%" height="100%">
              <Defs>
                <LinearGradient id="heroGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <Stop offset="0%" stopColor={colors.auroraStart} />
                  <Stop offset="60%" stopColor={colors.auroraMid} />
                  <Stop offset="100%" stopColor={colors.auroraEnd} />
                </LinearGradient>
              </Defs>
              <Rect x="0" y="0" width="100%" height="100%" fill="url(#heroGrad)" />
            </Svg>
          </View>
          <View style={st.heroContent}>
            <View style={st.heroCheckWrap}>
              <CheckCircle2 size={32} color="#FFF" />
            </View>
            <Text style={st.heroTitle}>Agent Run Completed</Text>
            <Text style={st.heroSub}>Your SalesOps agent completed the workflow successfully.</Text>
            <View style={st.heroMeta}>
              <View style={st.heroMetaItem}>
                <Clock size={12} color="rgba(255,255,255,0.7)" />
                <Text style={st.heroMetaText}>May 18, 2025 · 9:40 AM</Text>
              </View>
              <View style={st.heroMetaItem}>
                <Clock size={12} color="rgba(255,255,255,0.7)" />
                <Text style={st.heroMetaText}>Duration: 04:32</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Impact Metrics */}
        <Text style={[st.sectionTitle, { color: colors.text, marginBottom: spacing.md }]}>Impact Metrics</Text>
        <View style={[st.metricsRow, { marginBottom: spacing.sm }]}>
          <MetricCard title="New Leads Found" value={String(metrics.leadsFound)} trendValue="↑ 32%" trendLabel="vs last run" positive />
          <MetricCard title="Hot Leads Identified" value={String(metrics.duplicatesPrevented)} trendValue="↑ 25%" positive />
        </View>
        <View style={[st.metricsRow, { marginBottom: spacing.xl }]}>
          <MetricCard title="Meetings Scheduled" value={String(metrics.meetingsScheduled)} />
          <MetricCard title="Revenue Potential" value="$128K" trendValue="↑ 18%" positive />
        </View>

        {/* Workflow Summary */}
        <Text style={[st.sectionTitle, { color: colors.text, marginBottom: spacing.md }]}>Workflow Summary</Text>
        <View style={[st.summaryCard, { backgroundColor: mode === 'dark' ? colors.surface : colors.card, borderColor: colors.border, borderRadius: borderRadius.lg, padding: spacing.md }, mode === 'light' && st.lightShadow]}>
          {WORKFLOW_ITEMS.map((item, i) => (
            <View key={i} style={[st.checkRow, i < WORKFLOW_ITEMS.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border, paddingBottom: 12, marginBottom: 12 }]}>
              <CheckCircle2 size={18} color={colors.success} />
              <Text style={[st.checkLabel, { color: colors.text }]}>{item.label}</Text>
              <Text style={[st.checkStatus, { color: colors.success }]}>Completed</Text>
            </View>
          ))}
        </View>

        {/* Action Buttons */}
        <View style={{ marginTop: spacing.xl, gap: spacing.sm }}>
          <TouchableOpacity style={[st.actionBtn, { borderRadius: borderRadius.md, overflow: 'hidden' }]} activeOpacity={0.85}>
            <View style={StyleSheet.absoluteFill}>
              <Svg width="100%" height="100%">
                <Defs>
                  <LinearGradient id="actGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <Stop offset="0%" stopColor={colors.auroraStart} />
                    <Stop offset="100%" stopColor={colors.auroraMid} />
                  </LinearGradient>
                </Defs>
                <Rect x="0" y="0" width="100%" height="100%" fill="url(#actGrad)" />
              </Svg>
            </View>
            <Text style={st.actionBtnText}>Review Leads</Text>
            <ArrowRight size={18} color="#FFF" />
          </TouchableOpacity>

          <TouchableOpacity style={[st.outlineBtn, { borderRadius: borderRadius.md, borderColor: colors.border }]} activeOpacity={0.7}>
            <Database size={16} color={colors.text} />
            <Text style={[st.outlineBtnText, { color: colors.text }]}>Sync to CRM</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const st = StyleSheet.create({
  root: { flex: 1 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 18, fontWeight: '700' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  heroCard: { minHeight: 200 },
  heroContent: { padding: 24, alignItems: 'center', justifyContent: 'center' },
  heroCheckWrap: { width: 56, height: 56, borderRadius: 28, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginBottom: 12 },
  heroTitle: { color: '#FFF', fontSize: 22, fontWeight: '700', marginBottom: 6, textAlign: 'center' },
  heroSub: { color: 'rgba(255,255,255,0.85)', fontSize: 14, textAlign: 'center', lineHeight: 20, marginBottom: 12 },
  heroMeta: { flexDirection: 'row', gap: 16 },
  heroMetaItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  heroMetaText: { color: 'rgba(255,255,255,0.7)', fontSize: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '700' },
  metricsRow: { flexDirection: 'row', gap: 12 },
  summaryCard: { borderWidth: 1 },
  lightShadow: { shadowColor: '#64748B', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.06, shadowRadius: 6, elevation: 2 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  checkLabel: { flex: 1, fontSize: 14, fontWeight: '500' },
  checkStatus: { fontSize: 12, fontWeight: '600' },
  actionBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', height: 50, gap: 8, shadowColor: '#6D5CFF', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 12, elevation: 4 },
  actionBtnText: { color: '#FFF', fontSize: 16, fontWeight: '600' },
  outlineBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', height: 50, borderWidth: 1, gap: 8 },
  outlineBtnText: { fontSize: 16, fontWeight: '600' },
});
