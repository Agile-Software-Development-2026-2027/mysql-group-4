export interface FundCreatePayload {
  name: string;
  description?: string | null;
  amount: number;
}

import { MissionStatus } from './mission.model';
import { RefundStatus } from './refund.model';

export interface FundMissionDTO {
  id: string;
  subject: string;
  status: MissionStatus;
  estimatedCost: number | string;
  requesterName: string;
  requestedAt: string;
  refundStatus?: RefundStatus | null;
  refundAmount?: number | string | null;
}

export interface FundDTO {
  id: string;
  name: string;
  description?: string | null;
  amount: number | string;
  responsibleFc: string;
  committedAmount: number | string;
  remainingAmount: number | string;
  missions: FundMissionDTO[];
}
