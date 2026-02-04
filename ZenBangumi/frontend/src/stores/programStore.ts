import { create } from 'zustand';

interface ProgramState {
  status: 'running' | 'stopped' | 'error';
  lastUpdate: string | null;
  setStatus: (status: 'running' | 'stopped' | 'error') => void;
}

export const useProgramStore = create<ProgramState>((set) => ({
  status: 'running',
  lastUpdate: null,
  setStatus: (status) => set({ status, lastUpdate: new Date().toISOString() }),
}));
