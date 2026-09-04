/**
 * navigation/index.tsx
 *
 * Auth gate driven by Redux store.
 * - AuthStack  (Login, Register)  — when no token
 * - AppStack   (BottomTabs + Deep screens) — when authenticated
 */

import React, { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useAppSelector, useAppDispatch } from '../store/hooks';
import { restoreSession } from '../store/slices/authSlice';
import { useTheme } from '../hooks/useTheme';

import { LoginScreen } from '../screens/LoginScreen';
import { RegisterScreen } from '../screens/RegisterScreen';
import { BottomTabs } from './BottomTabs';

import { DiscoveryScreen } from '../screens/DiscoveryScreen';
import { CRMLeadsScreen } from '../screens/CRMLeadsScreen';
import { TraceLogsScreen } from '../screens/TraceLogsScreen';
import { OutcomeDashboardScreen } from '../screens/OutcomeDashboardScreen';
import { SimulationConsoleScreen } from '../screens/SimulationConsoleScreen';
import { LogsScreen } from '../screens/LogsScreen';

export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
};

export type AppStackParamList = {
  MainTabs: undefined;
  Discovery: undefined;
  CRMLeads: undefined;
  TraceLogs: { runId: string } | undefined;
  OutcomeDashboard: { runId: string } | undefined;
  SimulationConsole: undefined;
  Logs: undefined;
};

const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const AppStack = createNativeStackNavigator<AppStackParamList>();

const AuthNavigator = () => {
  const { colors } = useTheme();
  return (
    <AuthStack.Navigator
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
      }}>
      <AuthStack.Screen name="Login" component={LoginScreen} />
      <AuthStack.Screen name="Register" component={RegisterScreen} />
    </AuthStack.Navigator>
  );
};

const AppNavigator = () => {
  const { colors } = useTheme();
  return (
    <AppStack.Navigator
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
      }}>
      <AppStack.Screen name="MainTabs" component={BottomTabs} />
      <AppStack.Screen name="Discovery" component={DiscoveryScreen} />
      <AppStack.Screen name="CRMLeads" component={CRMLeadsScreen} />
      <AppStack.Screen name="TraceLogs" component={TraceLogsScreen} />
      <AppStack.Screen name="OutcomeDashboard" component={OutcomeDashboardScreen} />
      <AppStack.Screen name="SimulationConsole" component={SimulationConsoleScreen} />
      <AppStack.Screen name="Logs" component={LogsScreen} />
    </AppStack.Navigator>
  );
};

export const RootNavigator = () => {
  const dispatch = useAppDispatch();
  const { token, isLoading } = useAppSelector((state) => state.auth);
  const { colors } = useTheme();

  useEffect(() => {
    dispatch(restoreSession());
  }, [dispatch]);

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return token ? <AppNavigator /> : <AuthNavigator />;
};
