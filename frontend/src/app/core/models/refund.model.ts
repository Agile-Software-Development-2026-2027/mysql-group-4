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
  needsReview?: boolean;
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
  issuedDate?: string | null;
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

export interface RefundItemFilterPayload {
  categories?: ExpenseCategory[] | null;
  sortByAmount?: 'asc' | 'desc' | null;
}

export interface RefundItemUpdatePayload {
  category?: ExpenseCategory;
  subtype?: ExpenseSubtype | null;
  itineraryFrom?: string | null;
  itineraryTo?: string | null;
  startsAt?: string;
  endsAt?: string | null;
  requestedAmount?: number;
  currency?: string;
  isTraceable?: boolean;
  receiptFilePath?: string | null;
  receiptOriginalFilename?: string | null;
  description?: string;
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

export interface CurrencyConversionDTO {
  originalCurrency: string;
  originalAmount: number;
  convertedAmount: number;
  rate: number;
}

export interface MissionCurrencyProfileDTO {
  destination?: string | null;
  defaultCurrency: string;
}

export interface ReceiptAutocompleteDTO {
  category?: ExpenseCategory | null;
  subtype?: ExpenseSubtype | null;
  amount?: number | null;
  currency?: string | null;
  convertedAmountEur?: number | null;
  exchangeRate?: number | null;
  startsAt?: string | null;
  endsAt?: string | null;
  issuedDate?: string | null;
  merchant?: string | null;
  description?: string | null;
  itineraryFrom?: string | null;
  itineraryTo?: string | null;
  rawText: string;
  confidence?: number | null;
  ocrEngine: string;
  llmModel: string;
  warnings: string[];
}

export interface BoundingBoxDTO {
  x: number;
  y: number;
  width: number;
  height: number;
  page?: number;
}

export interface ReceiptPageDTO {
  page: number;
  imageWidth: number;
  imageHeight: number;
  imageDataUrl: string;
}

export interface ReceiptDetectionResponseDTO {
  imageWidth: number;
  imageHeight: number;
  boxes: BoundingBoxDTO[];
  pages?: ReceiptPageDTO[];
}
