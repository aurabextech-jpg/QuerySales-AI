import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  TouchableOpacity,
  Dimensions,
} from 'react-native';
import Svg, { Defs, RadialGradient, Stop, Circle } from 'react-native-svg';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { signIn, clearError } from '../store/slices/authSlice';
import { useTheme } from '../hooks/useTheme';
import { AuthInput } from '../components/AuthInput';
import { Mail, Lock, Bot } from '../constants/icons';
import type { AuthStackParamList } from '../navigation';
import { NeonButton } from '../components/NeonButton';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

type Props = NativeStackScreenProps<AuthStackParamList, 'Login'>;

const AuroraOrbs = () => {
  const { colors } = useTheme();
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <Svg width={SCREEN_WIDTH} height={400} style={{ position: 'absolute', top: -80 }}>
        <Defs>
          <RadialGradient id="orb1" cx="20%" cy="30%" r="50%">
            <Stop offset="0%" stopColor={colors.auroraStart} stopOpacity="0.3" />
            <Stop offset="100%" stopColor={colors.auroraStart} stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="orb2" cx="80%" cy="50%" r="40%">
            <Stop offset="0%" stopColor={colors.auroraMid} stopOpacity="0.25" />
            <Stop offset="100%" stopColor={colors.auroraMid} stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="orb3" cx="50%" cy="70%" r="35%">
            <Stop offset="0%" stopColor={colors.auroraEnd} stopOpacity="0.2" />
            <Stop offset="100%" stopColor={colors.auroraEnd} stopOpacity="0" />
          </RadialGradient>
        </Defs>
        <Circle cx={SCREEN_WIDTH * 0.2} cy={120} r={200} fill="url(#orb1)" />
        <Circle cx={SCREEN_WIDTH * 0.8} cy={200} r={160} fill="url(#orb2)" />
        <Circle cx={SCREEN_WIDTH * 0.5} cy={280} r={140} fill="url(#orb3)" />
      </Svg>
    </View>
  );
};

export const LoginScreen = ({ navigation }: Props) => {
  const dispatch = useAppDispatch();
  const { error: globalError, isLoading } = useAppSelector((s) => s.auth);
  const { colors, spacing, borderRadius, mode } = useTheme();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  const validate = (): boolean => {
    let valid = true;
    setEmailError('');
    setPasswordError('');

    if (!email.trim()) {
      setEmailError('Email is required.');
      valid = false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setEmailError('Enter a valid email address.');
      valid = false;
    }
    if (!password) {
      setPasswordError('Password is required.');
      valid = false;
    }
    return valid;
  };

  const handleLogin = async () => {
    if (!validate()) return;
    setIsSubmitting(true);
    await dispatch(signIn({ email: email.trim(), password }));
    setIsSubmitting(false);
  };

  return (
    <KeyboardAvoidingView
      style={[styles.container, { backgroundColor: colors.background }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <AuroraOrbs />
      <ScrollView
        contentContainerStyle={[styles.scroll, { padding: spacing.xl }]}
        keyboardShouldPersistTaps="handled">
        {/* Logo */}
        <View style={[styles.header, { marginBottom: spacing.xxl }]}>
          <View
            style={[
              styles.logoIcon,
              {
                backgroundColor: colors.primaryMuted,
                borderRadius: borderRadius.xl,
              },
            ]}>
            <Bot size={32} color={colors.primary} />
          </View>
          <Text
            style={[
              styles.logo,
              {
                color: colors.text,
              },
            ]}>
            Sales<Text style={{ color: colors.primary }}>Ops</Text>
          </Text>
          <Text style={[styles.subtitle, { color: colors.textSecondary, marginTop: spacing.xs }]}>
            Autonomous Sales Intelligence
          </Text>
        </View>

        {/* Form Card */}
        <View
          style={[
            styles.form,
            {
              backgroundColor: mode === 'dark' ? colors.glassBg : colors.glassBg,
              borderColor: colors.glassStroke,
              borderRadius: borderRadius.xl,
              padding: spacing.xl,
              gap: spacing.md,
            },
            mode === 'dark' && styles.darkFormShadow,
            mode === 'light' && styles.lightFormShadow,
          ]}>
          <View>
            <Text style={[styles.formTitle, { color: colors.text }]}>
              Welcome back
            </Text>
            <Text
              style={[
                styles.formSubtitle,
                { color: colors.textSecondary, marginBottom: spacing.sm },
              ]}>
              Sign in to your account
            </Text>
          </View>

          {!!globalError && (
            <View
              style={[
                styles.errorBanner,
                {
                  backgroundColor: colors.errorMuted,
                  borderColor: colors.error,
                  borderRadius: borderRadius.sm,
                  padding: spacing.md,
                },
              ]}>
              <Text style={[styles.errorBannerText, { color: colors.error }]}>
                {globalError}
              </Text>
            </View>
          )}

          <AuthInput
            label="Email"
            placeholder="you@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
            value={email}
            onChangeText={setEmail}
            error={emailError}
            icon={<Mail size={18} color={colors.textMuted} />}
          />
          <AuthInput
            label="Password"
            placeholder="••••••••"
            isPassword
            value={password}
            onChangeText={setPassword}
            error={passwordError}
            icon={<Lock size={18} color={colors.textMuted} />}
          />

          <NeonButton
            title="Sign In"
            onPress={handleLogin}
            loading={isSubmitting}
            variant="aurora"
            style={{ marginTop: spacing.sm }}
          />

          <View style={[styles.linkRow, { marginTop: spacing.sm }]}>
            <Text style={[styles.linkLabel, { color: colors.textSecondary }]}>
              Don't have an account?
            </Text>
            <TouchableOpacity onPress={() => navigation.navigate('Register')}>
              <Text style={[styles.link, { color: colors.primary }]}>
                {' '}
                Sign up
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flexGrow: 1, justifyContent: 'center' },
  header: { alignItems: 'center' },
  logoIcon: {
    width: 64,
    height: 64,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  logo: {
    fontSize: 40,
    fontWeight: '800',
    letterSpacing: 1,
  },
  subtitle: {
    fontSize: 14,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    fontWeight: '500',
  },
  form: { borderWidth: 1 },
  darkFormShadow: {
    shadowColor: '#6D5CFF',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 24,
    elevation: 8,
  },
  lightFormShadow: {
    shadowColor: '#64748B',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 16,
    elevation: 4,
  },
  formTitle: { fontSize: 24, fontWeight: '700', marginBottom: 2 },
  formSubtitle: { fontSize: 14 },
  errorBanner: { borderWidth: 1 },
  errorBannerText: { fontSize: 14 },
  linkRow: { flexDirection: 'row', justifyContent: 'center' },
  linkLabel: { fontSize: 14 },
  link: { fontSize: 14, fontWeight: '600' },
});
