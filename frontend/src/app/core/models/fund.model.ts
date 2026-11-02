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
  createdAt: string;
  updatedAt: string;
  createdBy?: string | null;
  updatedBy?: string | null;
}
