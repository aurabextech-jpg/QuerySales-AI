/**
 * hooks/useTheme.ts — Convenience hook to get themed colors.
 */

import { useMemo } from 'react';
import { useAppSelector } from '../store/hooks';
import { getColors, spacing, borderRadius, typography } from '../theme';
import type { ThemeColors } from '../theme';

export const useTheme = () => {
  const mode = useAppSelector((s) => s.theme.mode);

  return useMemo(
    () => ({
      mode,
      colors: getColors(mode),
      spacing,
      borderRadius,
      typography,
    }),
    [mode],
  );
};

export type AppTheme = ReturnType<typeof useTheme>;
