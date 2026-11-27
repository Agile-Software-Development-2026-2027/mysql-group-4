import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AddRefundItemModal } from './add-refund-item-modal';
import { RefundService } from '../../../../services/refund.service';
import { MissionService } from '../../../../services/mission.service';
import { ToastService } from '../../../../services/toast.service';

describe('AddRefundItemModal', () => {
  let component: AddRefundItemModal;
  let fixture: ComponentFixture<AddRefundItemModal>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AddRefundItemModal],
      providers: [
        { provide: RefundService, useValue: {} },
        { provide: MissionService, useValue: {} },
        { provide: ToastService, useValue: {} },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AddRefundItemModal);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('requires a new conversion when the issued date changes', () => {
    const issuedDate = component.form.get('issuedDate')!;
    issuedDate.setValue('2026-11-25');
    component.conversionInfo.set({
      originalCurrency: 'USD',
      originalAmount: 10,
      convertedAmount: 9,
      rate: 0.9,
    });
    component.euroEquivalent.set(9);

    issuedDate.setValue('2026-11-26');

    expect(component.conversionInfo()).toBeNull();
    expect(component.euroEquivalent()).toBeNull();
  });

  it('keeps the conversion when the issued date is set to the same value', () => {
    const issuedDate = component.form.get('issuedDate')!;
    issuedDate.setValue('2026-11-25');
    component.conversionInfo.set({
      originalCurrency: 'USD',
      originalAmount: 10,
      convertedAmount: 9,
      rate: 0.9,
    });
    component.euroEquivalent.set(9);

    issuedDate.setValue('2026-11-25');

    expect(component.conversionInfo()).toEqual({
      originalCurrency: 'USD',
      originalAmount: 10,
      convertedAmount: 9,
      rate: 0.9,
    });
    expect(component.euroEquivalent()).toBe(9);
  });
});
