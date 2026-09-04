/**
 * store/slices/themeSlice.ts — Dark/Light mode state.
 */

import { createSlice } from '@reduxjs/toolkit';
import type { ThemeMode } from '../../theme';

type ThemeState = {
  mode: ThemeMode;
};

const initialState: ThemeState = {
  mode: 'dark',
};

const themeSlice = createSlice({
  name: 'theme',
  initialState,
  reducers: {
    toggleTheme(state) {
      state.mode = state.mode === 'dark' ? 'light' : 'dark';
    },
    setTheme(state, action: { payload: ThemeMode }) {
      state.mode = action.payload;
    },
  },
});

export const { toggleTheme, setTheme } = themeSlice.actions;
export default themeSlice.reducer;
