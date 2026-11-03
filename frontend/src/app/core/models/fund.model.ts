export interface FundCreatePayload {
  name: string;
  description?: string | null;
  amount: number;
}

export interface FundDTO {
  id: string;
  name: string;
  description?: string | null;
  amount: number | string;
  responsibleFc: string;
  lockedByMissionId?: string | null;
  missionSubject?: string | null;
  requestedAmount?: number | string | null;
  requesterName?: string | null;
}
