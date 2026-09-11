export interface RpcEndpointStatus {
  url: string;
  dnsResolved: boolean;
  connected: boolean;
  latencyMs: number;
  chainName: string;
  peers: number;
  nodeVersion: string;
  blockNumber?: number;
  error?: string;
}

export type MiningMode = 'eco' | 'daily' | 'performance';

export interface ParticipationRecord {
  id: string;
  timestamp: string;
  qblockId: string;
  status: 'verified' | 'unverified' | 'pending';
  win: boolean;
  source: string;
}

export interface NodeMetrics {
  cpuUsage: number;
  memoryUsage: number;
  memoryUsedMb: number;
  memoryTotalMb: number;
  deviceTemp: string;
  batteryStatus: string;
  runtimeMinutes: number;
}
