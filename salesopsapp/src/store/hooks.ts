/**
 * store/hooks.ts
 *
 * Typed Redux hooks for use throughout the app.
 * Always use these instead of plain `useDispatch` and `useSelector`.
 */

import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from './index';

export const useAppDispatch = useDispatch.withTypes<AppDispatch>();
export const useAppSelector = useSelector.withTypes<RootState>();
