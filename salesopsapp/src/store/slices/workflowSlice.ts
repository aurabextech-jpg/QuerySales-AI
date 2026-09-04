/**
 * store/slices/workflowSlice.ts
 *
 * Manages state for the SalesOps Agent workflows.
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface TraceLog {
  id: string;
  timestamp: string;
  agent: string;
  action: string;
  details: string;
  status: 'pending' | 'success' | 'failed';
}

interface WorkflowState {
  isSimulationMode: boolean;
  activeRunId: string | null;
  logs: TraceLog[];
  metrics: {
    leadsFound: number;
    duplicatesPrevented: number;
    meetingsScheduled: number;
    todosCreated: number;
  };
}

const initialState: WorkflowState = {
  isSimulationMode: true, // Default to true as per hackathon plan
  activeRunId: null,
  logs: [],
  metrics: {
    leadsFound: 0,
    duplicatesPrevented: 0,
    meetingsScheduled: 0,
    todosCreated: 0,
  },
};

const workflowSlice = createSlice({
  name: 'workflow',
  initialState,
  reducers: {
    setSimulationMode: (state, action: PayloadAction<boolean>) => {
      state.isSimulationMode = action.payload;
    },
    setActiveRunId: (state, action: PayloadAction<string | null>) => {
      state.activeRunId = action.payload;
    },
    addTraceLog: (state, action: PayloadAction<TraceLog>) => {
      state.logs.unshift(action.payload); // Prepend so newest is first
    },
    updateMetrics: (state, action: PayloadAction<Partial<WorkflowState['metrics']>>) => {
      state.metrics = { ...state.metrics, ...action.payload };
    },
    clearWorkflowState: (state) => {
      state.activeRunId = null;
      state.logs = [];
      state.metrics = initialState.metrics;
    },
  },
});

export const {
  setSimulationMode,
  setActiveRunId,
  addTraceLog,
  updateMetrics,
  clearWorkflowState,
} = workflowSlice.actions;

export default workflowSlice.reducer;
