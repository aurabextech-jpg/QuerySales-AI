/**
 * SimulationConsoleScreen.tsx
 *
 * Settings screen to toggle between Simulation Mode (Dry-run) and Real Execution.
 */

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Switch, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../hooks/useTheme';
import { ArrowLeft, Server, AlertTriangle } from '../constants/icons';
import { useNavigation } from '@react-navigation/native';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { setSimulationMode } from '../store/slices/workflowSlice';

export const SimulationConsoleScreen = () => {
  const { colors, spacing, borderRadius } = useTheme();
  const navigation = useNavigation();
  const dispatch = useAppDispatch();
  const isSimulationMode = useAppSelector(s => s.workflow.isSimulationMode);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <View style={[styles.header, { paddingHorizontal: spacing.xl, paddingVertical: spacing.md }]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <ArrowLeft size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Simulation Console</Text>
        <View style={{ width: 24 }} />
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: spacing.xl, paddingBottom: spacing.xl, paddingTop: spacing.md }}>
        
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border, borderRadius: borderRadius.lg, padding: spacing.lg }]}>
          <View style={styles.cardHeader}>
            <View style={[styles.iconBox, { backgroundColor: colors.primaryMuted }]}>
              <Server size={20} color={colors.primary} />
            </View>
            <View style={{ flex: 1, marginLeft: spacing.md }}>
              <Text style={[styles.settingTitle, { color: colors.text }]}>Simulation Mode</Text>
              <Text style={[styles.settingSub, { color: colors.textSecondary }]}>Execute agent workflows in dry-run mode. No real writes to ERPNext or Google Calendar.</Text>
            </View>
            <Switch 
              value={isSimulationMode} 
              onValueChange={(val) => { dispatch(setSimulationMode(val)); }}
              trackColor={{ false: colors.border, true: colors.primary }}
              thumbColor="#FFF"
            />
          </View>
        </View>

        {!isSimulationMode && (
          <View style={[styles.warningBox, { backgroundColor: colors.warningMuted, borderColor: colors.warning, borderRadius: borderRadius.md, padding: spacing.md, marginTop: spacing.lg }]}>
            <View style={styles.warningHeader}>
              <AlertTriangle size={20} color={colors.warning} />
              <Text style={[styles.warningTitle, { color: colors.warning }]}>Live Execution Active</Text>
            </View>
            <Text style={[styles.warningText, { color: colors.warning }]}>
              The agent will perform real API calls and mutations. Ensure your ERPNext and Google API credentials are correctly configured in your environment.
            </Text>
          </View>
        )}

      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 20, fontWeight: '700' },
  card: { borderWidth: 1 },
  cardHeader: { flexDirection: 'row', alignItems: 'center' },
  iconBox: { width: 40, height: 40, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  settingTitle: { fontSize: 16, fontWeight: '600', marginBottom: 4 },
  settingSub: { fontSize: 13, lineHeight: 18 },
  warningBox: { borderWidth: 1 },
  warningHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  warningTitle: { fontSize: 15, fontWeight: '700' },
  warningText: { fontSize: 13, lineHeight: 18 },
});
