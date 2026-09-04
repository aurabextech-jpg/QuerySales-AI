/**
 * theme.ts — Aurora Intelligence Dark & Light theme palettes + shared design tokens.
 *
 * Dark: Deep navy (#07111F) with aurora gradients (#6D5CFF → #885CF6 → #36CFFF)
 * Light: Clean white (#F8F9FC) with vibrant aurora accents
 */

export type ThemeMode = 'dark' | 'light';

const darkColors = {
  background: '#07111F',
  surface: '#0D1728',
  surfaceHighlight: '#121F35',
  surfaceElevated: '#162032',

  primary: '#6D5CFF',
  primaryLight: '#885CF6',
  primaryDark: '#5A4AD4',
  primaryMuted: 'rgba(109, 92, 255, 0.15)',

  accent: '#36CFFF',
  accentMuted: 'rgba(54, 207, 255, 0.12)',
  accentGreen: '#2BE4B8',
  accentGreenMuted: 'rgba(43, 228, 184, 0.12)',

  text: '#F8FAFC',
  textSecondary: '#8FA3BF',
  textMuted: '#5A7190',

  border: 'rgba(143, 163, 191, 0.15)',
  borderLight: 'rgba(143, 163, 191, 0.08)',

  error: '#EF4444',
  errorMuted: 'rgba(239, 68, 68, 0.12)',
  success: '#22C55E',
  successMuted: 'rgba(34, 197, 94, 0.12)',
  warning: '#F59E0B',
  warningMuted: 'rgba(245, 158, 11, 0.12)',
  info: '#36CFFF',
  infoMuted: 'rgba(54, 207, 255, 0.12)',

  overlay: 'rgba(7, 17, 31, 0.7)',
  card: '#0D1728',
  tabBar: '#0D1728',

  // Aurora gradient tokens
  auroraStart: '#6D5CFF',
  auroraMid: '#885CF6',
  auroraEnd: '#36CFFF',
  auroraTeal: '#2BE4B8',

  // Glass effect tokens
  glassBg: 'rgba(13, 23, 40, 0.6)',
  glassStroke: 'rgba(143, 163, 191, 0.2)',
  glassHighlight: 'rgba(255, 255, 255, 0.05)',

  statusBar: 'light-content' as const,
};

const lightColors = {
  background: '#F8F9FC',
  surface: '#FFFFFF',
  surfaceHighlight: '#EEF4FA',
  surfaceElevated: '#FFFFFF',

  primary: '#5B57FF',
  primaryLight: '#885CF6',
  primaryDark: '#4A46D4',
  primaryMuted: 'rgba(91, 87, 255, 0.08)',

  accent: '#28B7FF',
  accentMuted: 'rgba(40, 183, 255, 0.08)',
  accentGreen: '#14D7B0',
  accentGreenMuted: 'rgba(20, 215, 176, 0.08)',

  text: '#0F172A',
  textSecondary: '#64748B',
  textMuted: '#94A3B8',

  border: '#E2E8F0',
  borderLight: '#F1F5F9',

  error: '#EF4444',
  errorMuted: 'rgba(239, 68, 68, 0.06)',
  success: '#16A34A',
  successMuted: 'rgba(22, 163, 74, 0.08)',
  warning: '#D97706',
  warningMuted: 'rgba(217, 119, 6, 0.08)',
  info: '#28B7FF',
  infoMuted: 'rgba(40, 183, 255, 0.08)',

  overlay: 'rgba(0, 0, 0, 0.3)',
  card: '#FFFFFF',
  tabBar: '#FFFFFF',

  // Aurora gradient tokens
  auroraStart: '#5B57FF',
  auroraMid: '#885CF6',
  auroraEnd: '#28B7FF',
  auroraTeal: '#14D7B0',

  // Glass effect tokens
  glassBg: 'rgba(255, 255, 255, 0.7)',
  glassStroke: 'rgba(226, 232, 240, 0.5)',
  glassHighlight: 'rgba(255, 255, 255, 0.9)',

  statusBar: 'dark-content' as const,
};

export type ThemeColors = Omit<typeof darkColors, 'statusBar'> & {
  statusBar: 'light-content' | 'dark-content';
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const borderRadius = {
  xs: 6,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  round: 9999,
};

export const typography = {
  fontFamily: 'System',
};

/** Get colors for a given theme mode */
export const getColors = (mode: ThemeMode): ThemeColors =>
  mode === 'dark' ? darkColors : lightColors;

/** Default export for backward compat — always dark */
export const theme = {
  colors: darkColors,
  spacing,
  borderRadius,
  typography,
};
