/**
 * RegisterScreen.tsx — Aurora Intelligence styled sign-up screen.
 */

import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, KeyboardAvoidingView, Platform,
  ScrollView, TouchableOpacity, Dimensions,
} from 'react-native';
import Svg, { Defs, RadialGradient, Stop, Circle } from 'react-native-svg';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { signUp, clearError } from '../store/slices/authSlice';
import { useTheme } from '../hooks/useTheme';
import { NeonButton } from '../components/NeonButton';
import { AuthInput } from '../components/AuthInput';
import { Mail, Lock, User, Bot } from '../constants/icons';
import type { AuthStackParamList } from '../navigation';

const { width: SW } = Dimensions.get('window');
type Props = NativeStackScreenProps<AuthStackParamList, 'Register'>;

const AuroraOrbs = () => {
  const { colors } = useTheme();
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <Svg width={SW} height={400} style={{ position: 'absolute', top: -80 }}>
        <Defs>
          <RadialGradient id="o1" cx="80%" cy="25%" r="50%">
            <Stop offset="0%" stopColor={colors.auroraMid} stopOpacity="0.3" />
            <Stop offset="100%" stopColor={colors.auroraMid} stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="o2" cx="20%" cy="55%" r="40%">
            <Stop offset="0%" stopColor={colors.auroraEnd} stopOpacity="0.25" />
            <Stop offset="100%" stopColor={colors.auroraEnd} stopOpacity="0" />
          </RadialGradient>
        </Defs>
        <Circle cx={SW * 0.8} cy={100} r={200} fill="url(#o1)" />
        <Circle cx={SW * 0.2} cy={220} r={160} fill="url(#o2)" />
      </Svg>
    </View>
  );
};

export const RegisterScreen = ({ navigation }: Props) => {
  const dispatch = useAppDispatch();
  const { error: globalError } = useAppSelector((s) => s.auth);
  const { colors, spacing, borderRadius, mode } = useTheme();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [nameError, setNameError] = useState('');
  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [confirmError, setConfirmError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => { return () => { dispatch(clearError()); }; }, [dispatch]);

  const validate = (): boolean => {
    let valid = true;
    setNameError(''); setEmailError(''); setPasswordError(''); setConfirmError('');
    if (!name.trim()) { setNameError('Full name is required.'); valid = false; }
    else if (name.trim().length < 2) { setNameError('Min 2 characters.'); valid = false; }
    if (!email.trim()) { setEmailError('Email is required.'); valid = false; }
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) { setEmailError('Enter a valid email.'); valid = false; }
    if (!password) { setPasswordError('Password is required.'); valid = false; }
    else if (password.length < 8) { setPasswordError('Min 8 characters.'); valid = false; }
    if (!confirmPassword) { setConfirmError('Confirm your password.'); valid = false; }
    else if (password !== confirmPassword) { setConfirmError('Passwords do not match.'); valid = false; }
    return valid;
  };

  const handleRegister = async () => {
    if (!validate()) return;
    setIsSubmitting(true);
    await dispatch(signUp({ name: name.trim(), email: email.trim(), password }));
    setIsSubmitting(false);
  };

  return (
    <KeyboardAvoidingView style={[s.root, { backgroundColor: colors.background }]} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <AuroraOrbs />
      <ScrollView contentContainerStyle={[s.scroll, { padding: spacing.xl }]} keyboardShouldPersistTaps="handled">
        <View style={[s.header, { marginBottom: spacing.xl }]}>
          <View style={[s.logoIcon, { backgroundColor: colors.primaryMuted, borderRadius: borderRadius.xl }]}>
            <Bot size={32} color={colors.primary} />
          </View>
          <Text style={[s.logo, { color: colors.text }]}>Sales<Text style={{ color: colors.primary }}>Ops</Text></Text>
          <Text style={[s.sub, { color: colors.textSecondary, marginTop: spacing.xs }]}>Autonomous Sales Intelligence</Text>
        </View>

        <View style={[s.form, { backgroundColor: colors.glassBg, borderColor: colors.glassStroke, borderRadius: borderRadius.xl, padding: spacing.xl, gap: spacing.md }, mode === 'dark' && s.dShadow, mode === 'light' && s.lShadow]}>
          <View>
            <Text style={[s.title, { color: colors.text }]}>Create account</Text>
            <Text style={[s.subtitle, { color: colors.textSecondary, marginBottom: spacing.sm }]}>Start your SalesOps journey</Text>
          </View>

          {!!globalError && (
            <View style={[s.err, { backgroundColor: colors.errorMuted, borderColor: colors.error, borderRadius: borderRadius.sm, padding: spacing.md }]}>
              <Text style={{ color: colors.error, fontSize: 14 }}>{globalError}</Text>
            </View>
          )}

          <AuthInput label="Full Name" placeholder="Jane Smith" autoCapitalize="words" value={name} onChangeText={setName} error={nameError} icon={<User size={18} color={colors.textMuted} />} />
          <AuthInput label="Email" placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none" value={email} onChangeText={setEmail} error={emailError} icon={<Mail size={18} color={colors.textMuted} />} />
          <AuthInput label="Password" placeholder="Min 8 characters" isPassword value={password} onChangeText={setPassword} error={passwordError} icon={<Lock size={18} color={colors.textMuted} />} />
          <AuthInput label="Confirm Password" placeholder="Re-enter password" isPassword value={confirmPassword} onChangeText={setConfirmPassword} error={confirmError} icon={<Lock size={18} color={colors.textMuted} />} />

          <NeonButton title="Create Account" onPress={handleRegister} loading={isSubmitting} variant="aurora" style={{ marginTop: spacing.sm }} />

          <View style={[s.linkRow, { marginTop: spacing.sm }]}>
            <Text style={{ color: colors.textSecondary, fontSize: 14 }}>Already have an account?</Text>
            <TouchableOpacity onPress={() => navigation.navigate('Login')}>
              <Text style={{ color: colors.primary, fontSize: 14, fontWeight: '600' }}> Sign in</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const s = StyleSheet.create({
  root: { flex: 1 },
  scroll: { flexGrow: 1, justifyContent: 'center' },
  header: { alignItems: 'center' },
  logoIcon: { width: 64, height: 64, justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  logo: { fontSize: 40, fontWeight: '800', letterSpacing: 1 },
  sub: { fontSize: 14, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '500' },
  form: { borderWidth: 1 },
  dShadow: { shadowColor: '#6D5CFF', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.15, shadowRadius: 24, elevation: 8 },
  lShadow: { shadowColor: '#64748B', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.1, shadowRadius: 16, elevation: 4 },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 2 },
  subtitle: { fontSize: 14 },
  err: { borderWidth: 1 },
  linkRow: { flexDirection: 'row', justifyContent: 'center' },
});
