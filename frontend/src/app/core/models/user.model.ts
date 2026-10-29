export enum EmploymentLevel {
  RICERCATORE = 'ricercatore',
  PROFESSORE_ORDINARIO = 'professore_ordinario',
  PROFESSORE_ASSOCIATO = 'professore_associato',
}

export interface User {
  id: string;
  email: string;
  name: string;
  surname: string;
  fiscalCode: string;
  department: string;
  employmentLevel: EmploymentLevel;
  isActive?: boolean;
  isSuperuser?: boolean;
  isVerified?: boolean;
}

export interface UserCreate {
  email: string;
  password: string;
  name: string;
  surname: string;
  fiscalCode: string;
  department: string;
  employmentLevel: EmploymentLevel | string;
}
