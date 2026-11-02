export interface Page<T> {
  content: T[];
  totalElements: number;
  number: number;
  size: number;
  totalPages: number;
  numberOfElements: number;
  first: boolean;
  last: boolean;
  empty: boolean;
}
