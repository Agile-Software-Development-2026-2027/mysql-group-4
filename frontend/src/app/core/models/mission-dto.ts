export enum MissionStatus {
  PENDING = 'PENDING',
  ACCEPTED = 'ACCEPTED',
  REJECTED = 'REJECTED'
}

export interface MissionDTO {
  id: string;
  status: MissionStatus;
  missionType: string;
  subject: string;
  destination: string;
  estimatedCost: number | string;
  startsAt: string;
  endsAt: string;
  response?: string | null;
  requesterId: string;
  fundManagerId: string;
  createdAt: string;
  updatedAt: string;
  createdBy?: string | null;
  updatedBy?: string | null;
}
