export enum MissionType {
  RESEARCH = 'RESEARCH',
  TRAINING = 'TRAINING',
  TEACHING = 'TEACHING',
}

export enum MissionStatus {
  PENDING = 'PENDING',
  APPROVED = 'APPROVED',
  REJECTED = 'REJECTED',
  CANCELLED = 'CANCELLED',
}

export interface MissionCreatePayload {
  missionType: MissionType | string;
  subject: string;
  destination: string;
  estimatedCost: number;
  startsAt: string; // Naive ISO datetime string: YYYY-MM-DDTHH:MM:SS
  endsAt: string;   // Naive ISO datetime string: YYYY-MM-DDTHH:MM:SS
  fundManagerId: string;
}

export interface MissionDTO {
  id: string;
  missionType: MissionType;
  status: MissionStatus;
  subject: string;
  destination: string;
  estimatedCost: number;
  startsAt: string;
  endsAt: string;
  requesterId: string;
  fundManagerId: string;
  createdAt: string;
  updatedAt: string;
  createdBy?: string | null;
  updatedBy?: string | null;
}
