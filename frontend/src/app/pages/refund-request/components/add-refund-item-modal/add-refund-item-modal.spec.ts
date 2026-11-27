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
});
