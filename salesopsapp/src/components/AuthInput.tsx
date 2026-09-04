/**
 * AuthInput.tsx
 *
 * Reusable styled text input with label, error message, and optional icon.
 * Aurora Intelligence glassmorphism styling with focus ring.
 * Used across Login, Register screens.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TextInputProps,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { useTheme } from '../hooks/useTheme';
import { Eye, EyeOff } from '../constants/icons';

interface AuthInputProps extends TextInputProps {
  label: string;
  error?: string;
  isPassword?: boolean;
  icon?: React.ReactNode;
}

export const AuthInput = ({
  label,
  error,
  isPassword = false,
  icon,
  ...props
}: AuthInputProps) => {
  const [secureText, setSecureText] = useState(isPassword);
  const [isFocused, setIsFocused] = useState(false);
  const { colors, spacing, borderRadius, mode } = useTheme();

  return (
    <View style={styles.wrapper}>
      <Text style={[styles.label, { color: colors.textSecondary }]}>{label}</Text>
      <View
        style={[
          styles.inputRow,
          {
            backgroundColor: mode === 'dark'
              ? colors.surfaceHighlight
              : colors.surfaceHighlight,
            borderColor: colors.border,
            borderRadius: borderRadius.md,
            paddingHorizontal: spacing.md,
          },
          isFocused && {
            borderColor: colors.primary,
            backgroundColor: mode === 'dark'
              ? 'rgba(109, 92, 255, 0.08)'
              : 'rgba(91, 87, 255, 0.04)',
          },
          !!error && {
            borderColor: colors.error,
          },
        ]}>
        {icon && <View style={styles.inputIcon}>{icon}</View>}
        <TextInput
          style={[styles.input, { color: colors.text, paddingVertical: spacing.md }]}
          placeholderTextColor={colors.textMuted}
          secureTextEntry={secureText}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          autoCapitalize={isPassword ? 'none' : props.autoCapitalize}
          {...props}
        />
        {isPassword && (
          <TouchableOpacity
            onPress={() => setSecureText(v => !v)}
            style={styles.eyeButton}
            accessibilityLabel={secureText ? 'Show password' : 'Hide password'}>
            {secureText ? (
              <EyeOff size={20} color={colors.textMuted} />
            ) : (
              <Eye size={20} color={colors.textMuted} />
            )}
          </TouchableOpacity>
        )}
      </View>
      {!!error && <Text style={[styles.errorText, { color: colors.error }]}>{error}</Text>}
    </View>
  );
};

const styles = StyleSheet.create({
  wrapper: {
    gap: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: '500',
    letterSpacing: 0.3,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
  },
  inputIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    fontSize: 16,
  },
  eyeButton: {
    padding: 4,
  },
  errorText: {
    fontSize: 12,
    marginTop: 2,
  },
});
