import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  ScrollView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { signOut } from '../store/slices/authSlice';
import { toggleTheme } from '../store/slices/themeSlice';
import { useTheme } from '../hooks/useTheme';
import {
  User,
  Mail,
  LogOut,
  Moon,
  Sun,
  Shield,
  Settings,
  ChevronRight,
  Server,
  Calendar,
  CheckCircle,
  XCircle,
} from '../constants/icons';
import { useNavigation } from '@react-navigation/native';
import { calendarApi } from '../services/calendarApi';
import { ToggleSwitch } from '../components/ToggleSwitch';
import type { CalendarStatus } from '../services/calendarApi';
import { config } from '../config';
import { GoogleSignin } from '@react-native-google-signin/google-signin';
const InfoRow = ({ icon: IconComponent, label, value, colors }: any) => (
  <View style={styles.infoRow}>
    <View
      style={[
        styles.iconContainer,
        { backgroundColor: colors.surfaceHighlight },
      ]}
    >
      <IconComponent size={18} color={colors.primary} />
    </View>
    <View style={styles.infoContent}>
      <Text style={[styles.infoLabel, { color: colors.textMuted }]}>
        {label}
      </Text>
      <Text style={[styles.infoValue, { color: colors.text }]}>
        {value ?? '—'}
      </Text>
    </View>
  </View>
);

const SettingRow = ({
  icon: IconComponent,
  label,
  rightElement,
  onPress,
  colors,
}: any) => (
  <TouchableOpacity
    style={styles.settingRow}
    onPress={onPress}
    disabled={!onPress}
    activeOpacity={0.7}
  >
    <View
      style={[
        styles.iconContainer,
        { backgroundColor: colors.surfaceHighlight },
      ]}
    >
      <IconComponent size={18} color={colors.textSecondary} />
    </View>
    <Text style={[styles.settingLabel, { color: colors.text }]}>{label}</Text>
    <View style={styles.settingRight}>
      {rightElement || <ChevronRight size={18} color={colors.textMuted} />}
    </View>
  </TouchableOpacity>
);

export const AccountScreen = () => {
  const dispatch = useAppDispatch();
  const navigation = useNavigation<any>();
  const user = useAppSelector(s => s.auth.user);
  const { mode } = useAppSelector(s => s.theme);
  const { colors, spacing, borderRadius } = useTheme();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const [calendarStatus, setCalendarStatus] = useState<CalendarStatus>({
    connected: false,
  });
  const [isCalendarLoading, setIsCalendarLoading] = useState(false);
  const [isCalendarChecking, setIsCalendarChecking] = useState(true);

  const displayName = user?.name ?? user?.email?.split('@')[0] ?? 'User';
  const initials = displayName
    .split(' ')
    .map((s: string) => s[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  const fetchCalendarStatus = useCallback(async () => {
    try {
      setIsCalendarChecking(true);
      const status = await calendarApi.getCalendarStatus();
      setCalendarStatus(status);
    } catch {
      setCalendarStatus({ connected: false });
    } finally {
      setIsCalendarChecking(false);
    }
  }, []);

  useEffect(() => {
    fetchCalendarStatus();
  }, [fetchCalendarStatus]);

  const handleConnectCalendar = async () => {
    try {
      setIsCalendarLoading(true);

      if (!GoogleSignin || typeof GoogleSignin.configure !== 'function') {
        Alert.alert(
          'Native Module Missing',
          'Google Sign-In native module is not linked.\n\nRun:\n  cd ios && pod install\nThen rebuild with: npm run ios',
        );
        return;
      }

      let webClientId = config.GOOGLE_WEB_CLIENT_ID;
      let iosClientId: string | undefined = config.GOOGLE_IOS_CLIENT_ID || undefined;
      let scopes = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
      ];

      try {
        const calendarConfig = await calendarApi.getCalendarConfig();
        const platformConfig =
          Platform.OS === 'ios' ? calendarConfig.ios : calendarConfig.android;
        if (platformConfig.web_client_id) {
          webClientId = platformConfig.web_client_id;
        }
        if (calendarConfig.scopes?.length) {
          scopes = calendarConfig.scopes;
        }
        if (Platform.OS === 'ios') {
          const iosCfg = calendarConfig.ios;
          if (iosCfg.ios_client_id) {
            iosClientId = iosCfg.ios_client_id;
          }
        }
      } catch {
        // Fall back to local config values if backend config fetch fails
      }

      if (!webClientId) {
        Alert.alert(
          'Configuration Error',
          'Google Web Client ID is missing. Add GOOGLE_WEB_CLIENT_ID to .env and rebuild.',
        );
        return;
      }

      const signInConfig: Parameters<typeof GoogleSignin.configure>[0] = {
        offlineAccess: true,
        forceCodeForRefreshToken: true,
        scopes,
        webClientId,
      };

      if (Platform.OS === 'ios' && iosClientId) {
        (signInConfig as any).iosClientId = iosClientId;
      }

      GoogleSignin.configure(signInConfig);

      const userInfo = await GoogleSignin.signIn();
      const serverAuthCode = userInfo?.data?.serverAuthCode;

      if (!serverAuthCode) {
        Alert.alert(
          'Error',
          'Could not retrieve authorization code from Google. Please try again.',
        );
        return;
      }

      const result = await calendarApi.syncCalendar(serverAuthCode);

      if (result.success) {
        setCalendarStatus({ connected: true, email: result.email });
        Alert.alert(
          'Connected!',
          `Google Calendar linked${result.email ? ` (${result.email})` : ''}.`,
        );
      } else {
        Alert.alert('Error', 'Failed to sync calendar. Please try again.');
      }
    } catch (error: any) {
      if (error?.code !== 'SIGN_IN_CANCELLED') {
        Alert.alert(
          'Error',
          error?.message || 'Failed to connect Google Calendar.',
        );
      }
    } finally {
      setIsCalendarLoading(false);
    }
  };

  const handleDisconnectCalendar = () => {
    Alert.alert(
      'Disconnect Calendar',
      'Are you sure you want to disconnect Google Calendar? The agent will no longer be able to check your availability.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: async () => {
            try {
              setIsCalendarLoading(true);
              await calendarApi.disconnectCalendar();

              try {
                const { GoogleSignin } = await import(
                  '@react-native-google-signin/google-signin'
                );
                await GoogleSignin.revokeAccess();
              } catch {
              }

              setCalendarStatus({ connected: false });
              Alert.alert('Disconnected', 'Google Calendar has been unlinked.');
            } catch (error: any) {
              Alert.alert(
                'Error',
                error?.message || 'Failed to disconnect calendar.',
              );
            } finally {
              setIsCalendarLoading(false);
            }
          },
        },
      ],
    );
  };

  const handleSignOut = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign Out',
        style: 'destructive',
        onPress: async () => {
          setIsLoggingOut(true);
          await dispatch(signOut());
        },
      },
    ]);
  };

  const handleThemeToggle = () => {
    dispatch(toggleTheme());
  };

  const CalendarStatusBadge = () => {
    if (isCalendarChecking) {
      return <ActivityIndicator size="small" color={colors.textMuted} />;
    }
    if (calendarStatus.connected) {
      return (
        <View
          style={[
            styles.calendarBadge,
            { backgroundColor: colors.successMuted },
          ]}
        >
          <CheckCircle size={14} color={colors.success} />
          <Text style={[styles.calendarBadgeText, { color: colors.success }]}>
            Connected
          </Text>
        </View>
      );
    }
    return (
      <View
        style={[styles.calendarBadge, { backgroundColor: colors.warningMuted }]}
      >
        <XCircle size={14} color={colors.warning} />
        <Text style={[styles.calendarBadgeText, { color: colors.warning }]}>
          Not Connected
        </Text>
      </View>
    );
  };

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      <ScrollView
        contentContainerStyle={{ paddingBottom: spacing.xl }}
        showsVerticalScrollIndicator={false}
      >
        <View style={[styles.avatarBlock, { paddingBottom: spacing.xl }]}>
          <View
            style={[
              styles.avatar,
              { backgroundColor: colors.primary, shadowColor: colors.primary },
            ]}
          >
            <Text style={styles.avatarText}>{initials}</Text>
          </View>
          <Text style={[styles.displayName, { color: colors.text }]}>
            {displayName}
          </Text>
          <Text style={[styles.emailText, { color: colors.textMuted }]}>
            {user?.email}
          </Text>
        </View>

        <View style={[styles.section, { paddingHorizontal: spacing.xl }]}>
          <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
            ACCOUNT DETAILS
          </Text>
          <View
            style={[
              styles.card,
              {
                backgroundColor: colors.surface,
                borderColor: colors.border,
                borderRadius: borderRadius.lg,
                padding: spacing.md,
              },
            ]}
          >
            <InfoRow
              icon={User}
              label="Name"
              value={user?.name}
              colors={colors}
            />
            <InfoRow
              icon={Mail}
              label="Email"
              value={user?.email}
              colors={colors}
            />
          </View>
        </View>

        <View
          style={[
            styles.section,
            { paddingHorizontal: spacing.xl, marginTop: spacing.xl },
          ]}
        >
          <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
            INTEGRATIONS
          </Text>
          <View
            style={[
              styles.card,
              {
                backgroundColor: colors.surface,
                borderColor: colors.border,
                borderRadius: borderRadius.lg,
                overflow: 'hidden',
              },
            ]}
          >
            <View style={styles.calendarRow}>
              <View
                style={[
                  styles.iconContainer,
                  { backgroundColor: colors.surfaceHighlight },
                ]}
              >
                <Calendar size={18} color={colors.primary} />
              </View>
              <View style={styles.calendarInfo}>
                <Text style={[styles.calendarTitle, { color: colors.text }]}>
                  Google Calendar
                </Text>
                {calendarStatus.connected && calendarStatus.email && (
                  <Text
                    style={[styles.calendarEmail, { color: colors.textMuted }]}
                  >
                    {calendarStatus.email}
                  </Text>
                )}
                <CalendarStatusBadge />
              </View>
              {isCalendarLoading ? (
                <ActivityIndicator size="small" color={colors.primary} />
              ) : calendarStatus.connected ? (
                <TouchableOpacity
                  style={[
                    styles.calendarButton,
                    {
                      backgroundColor: colors.errorMuted,
                      borderColor: colors.errorMuted,
                    },
                  ]}
                  onPress={handleDisconnectCalendar}
                  activeOpacity={0.7}
                >
                  <Text
                    style={[styles.calendarButtonText, { color: colors.error }]}
                  >
                    Disconnect
                  </Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  style={[
                    styles.calendarButton,
                    {
                      backgroundColor: colors.primaryMuted,
                      borderColor: colors.primaryMuted,
                    },
                  ]}
                  onPress={handleConnectCalendar}
                  activeOpacity={0.7}
                >
                  <Text
                    style={[
                      styles.calendarButtonText,
                      { color: colors.primary },
                    ]}
                  >
                    Connect
                  </Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        </View>

        <View
          style={[
            styles.section,
            { paddingHorizontal: spacing.xl, marginTop: spacing.xl },
          ]}
        >
          <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
            PREFERENCES
          </Text>
          <View
            style={[
              styles.card,
              {
                backgroundColor: colors.surface,
                borderColor: colors.border,
                borderRadius: borderRadius.lg,
              },
            ]}
          >
            <SettingRow
              icon={mode === 'dark' ? Moon : Sun}
              label="Dark Mode"
              colors={colors}
              rightElement={
                <ToggleSwitch
                  value={mode === 'dark'}
                  onValueChange={handleThemeToggle}
                  activeColor={colors.primary}
                  inactiveColor={colors.border}
                />
              }
            />
            <SettingRow
              icon={Server}
              label="Simulation Console"
              colors={colors}
              onPress={() => navigation.navigate('SimulationConsole')}
            />
            <SettingRow
              icon={Shield}
              label="Logs"
              colors={colors}
              onPress={() => navigation.navigate('Logs')}
            />
          </View>
        </View>

        <View style={{ paddingHorizontal: spacing.xl, marginTop: spacing.md }}>
          <TouchableOpacity
            style={[
              styles.logoutButton,
              {
                backgroundColor: colors.errorMuted,
                borderColor: colors.errorMuted,
                borderRadius: borderRadius.md,
                padding: spacing.md,
              },
            ]}
            onPress={handleSignOut}
            disabled={isLoggingOut}
            activeOpacity={0.8}
          >
            {isLoggingOut ? (
              <ActivityIndicator color={colors.error} />
            ) : (
              <>
                <LogOut size={20} color={colors.error} />
                <Text style={[styles.logoutText, { color: colors.error }]}>
                  Sign Out
                </Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { alignItems: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '700' },
  avatarBlock: { alignItems: 'center' },
  avatar: {
    width: 88,
    height: 88,
    borderRadius: 44,
    justifyContent: 'center',
    alignItems: 'center',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 8,
    marginBottom: 16,
  },
  avatarText: { color: '#FFF', fontSize: 32, fontWeight: '700' },
  displayName: { fontSize: 24, fontWeight: '700', marginBottom: 4 },
  emailText: { fontSize: 15 },
  section: {},
  sectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 8,
    marginLeft: 4,
  },
  card: { borderWidth: 1, overflow: 'hidden' },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    marginBottom: 16,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  infoContent: { flex: 1 },
  infoLabel: { fontSize: 12, marginBottom: 2 },
  infoValue: { fontSize: 15, fontWeight: '500' },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(150,150,150,0.1)',
  },
  settingLabel: { fontSize: 16, fontWeight: '500', flex: 1, marginLeft: 16 },
  settingRight: {},
  // Calendar integration styles
  calendarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    gap: 12,
  },
  calendarInfo: { flex: 1, gap: 4 },
  calendarTitle: { fontSize: 16, fontWeight: '600' },
  calendarEmail: { fontSize: 13 },
  calendarBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginTop: 2,
  },
  calendarBadgeText: { fontSize: 11, fontWeight: '600' },
  calendarButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  calendarButtonText: { fontSize: 13, fontWeight: '700' },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderWidth: 1,
  },
  logoutText: { fontSize: 16, fontWeight: '600' },
});
