import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type { Job } from '../types';

interface WorkflowContextType {
  selectedJob: Job | null;
  setSelectedJob: (job: Job | null) => void;
  pipelineStage: string | null;
  setPipelineStage: (stage: string | null) => void;
  filterType: string | null;
  setFilterType: (filter: string | null) => void;
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  refreshTrigger: number;
  triggerRefresh: () => void;
}

const WorkflowContext = createContext<WorkflowContextType | undefined>(undefined);

export const useWorkflow = () => {
  const context = useContext(WorkflowContext);
  if (!context) {
    throw new Error('useWorkflow must be used within a WorkflowProvider');
  }
  return context;
};

interface WorkflowProviderProps {
  children: ReactNode;
}

export const WorkflowProvider: React.FC<WorkflowProviderProps> = ({ children }) => {
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [pipelineStage, setPipelineStage] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  const triggerRefresh = useCallback(() => {
    setRefreshTrigger(prev => prev + 1);
  }, []);

  const value: WorkflowContextType = {
    selectedJob,
    setSelectedJob,
    pipelineStage,
    setPipelineStage,
    filterType,
    setFilterType,
    searchTerm,
    setSearchTerm,
    refreshTrigger,
    triggerRefresh,
  };

  return (
    <WorkflowContext.Provider value={value}>
      {children}
    </WorkflowContext.Provider>
  );
};

