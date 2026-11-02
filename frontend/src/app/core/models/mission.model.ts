export enum MissionType {
  RESEARCH = 'RESEARCH',
  TRAINING = 'TRAINING',
  TEACHING = 'TEACHING',
}

export enum MissionStatus {
  PENDING = 'PENDING',
  ACCEPTED = 'ACCEPTED',
  APPROVED = 'ACCEPTED',
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
  missionType: MissionType | string;
  status: MissionStatus;
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
