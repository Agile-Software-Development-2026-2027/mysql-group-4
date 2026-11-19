export enum RefundStatus {
  DRAFT = 'DRAFT',
  SUBMITTED = 'SUBMITTED',
  APPROVED = 'APPROVED',
}

export enum ExpenseCategory {
  TRANSPORT = 'TRANSPORT',
  ACCOMMODATION = 'ACCOMMODATION',
  MEALS = 'MEALS',
  OTHER = 'OTHER',
}

export enum ExpenseSubtype {
  TRAIN = 'TRAIN',
  PLANE = 'PLANE',
  SHIP = 'SHIP',
  PUBLIC_TRANSPORT = 'PUBLIC_TRANSPORT',
  TAXI_RENTAL = 'TAXI_RENTAL',
  OWN_VEHICLE = 'OWN_VEHICLE',
  ACCOMMODATION_EXPENSE = 'ACCOMMODATION_EXPENSE',
  OTHER_ACCOMMODATION_EXPENSE = 'OTHER_ACCOMMODATION_EXPENSE',
  MEALS_EXPENSE = 'MEALS_EXPENSE',
  OTHER_MEALS_EXPENSE = 'OTHER_MEALS_EXPENSE',
}

export interface RefundItemDTO {
  id: string;
  refundRequestId: string;
  category: ExpenseCategory;
  subtype?: ExpenseSubtype | null;
  itineraryFrom?: string | null;
  itineraryTo?: string | null;
  startsAt: string;
  endsAt?: string | null;
  requestedAmount: number | string;
  reimbursedAmount?: number | string | null;
  currency: string;
  isTraceable: boolean;
  receiptFilePath: string;
  receiptOriginalFilename: string;
  description: string;
  adminNotes?: string | null;
  createdAt: string;
  updatedAt: string;
  createdBy?: string | null;
  updatedBy?: string | null;
}

export interface RefundRequestDTO {
  id: string;
  missionId: string;
  status: RefundStatus;
  totalRequestedAmount: number | string;
  totalReimbursedAmount: number | string;
  submittedAt?: string | null;
  approvedAt?: string | null;
  createdAt: string;
  updatedAt: string;
  createdBy?: string | null;
  updatedBy?: string | null;
  items: RefundItemDTO[];
}

export interface RefundRequestCreatePayload {
  missionId: string;
}

export interface RefundRequesterDTO {
  id: string;
  name: string;
  surname: string;
  department: string;
}

export interface RefundMissionDTO {
  id: string;
  subject: string;
  destination: string;
  startsAt: string;
  endsAt: string;
  estimatedCost: number | string;
  requester: RefundRequesterDTO;
}

export interface RefundReviewDTO extends RefundRequestDTO {
  mission: RefundMissionDTO;
}

export interface RefundItemDecision {
  itemId: string;
  reimbursedAmount: string;
  adminNotes: string | null;
}

export interface RefundApprovePayload {
  items: RefundItemDecision[];
}

export interface RefundReceiptUploadDTO {
  receiptFilePath: string;
  receiptOriginalFilename: string;
}

export interface RefundItemCreatePayload {
  category: ExpenseCategory;
  subtype?: ExpenseSubtype | null;
  itineraryFrom?: string | null;
  itineraryTo?: string | null;
  startsAt: string;
  endsAt?: string | null;
  requestedAmount: number;
  currency?: string;
  isTraceable?: boolean;
  receiptFilePath: string;
  receiptOriginalFilename: string;
  description: string;
}

export interface RefundFilterPayload {
  status?: RefundStatus | null;
}

export interface RefundOverviewDTO {
  id: string;
  status: RefundStatus;
  requesterName: string;
  requesterSurname: string;
  subject: string;
  totalRequested: number | string;
  totalReimbursed: number | string;
  submittedAt?: string | null;
  approvedAt?: string | null;
}
