import { Component, inject, signal, OnInit } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Topbar } from '../../components/topbar/topbar';
import { RefundService } from '../../services/refund.service';
import { RefundOverviewDTO, RefundStatus } from '../../core/models';

@Component({
  selector: 'app-refund-overview',
  standalone: true,
  imports: [Topbar, DatePipe, DecimalPipe, RouterLink],
  templateUrl: './refund-overview.html',
  styleUrl: './refund-overview.scss',
})
export class RefundOverview implements OnInit {
  private refundService = inject(RefundService);

  activeSection = 'pending';

  pendingRefunds = signal<RefundOverviewDTO[]>([]);
  approvedRefunds = signal<RefundOverviewDTO[]>([]);

  ngOnInit(): void {
    this.loadRefunds();
  }

  loadRefunds() {
    this.refundService.filterRefunds({ status: RefundStatus.SUBMITTED }).subscribe({
      next: (data) => this.pendingRefunds.set(data),
      error: (err) => console.error('Error loading pending refunds', err)
    });

    this.refundService.filterRefunds({ status: RefundStatus.APPROVED }).subscribe({
      next: (data) => this.approvedRefunds.set(data),
      error: (err) => console.error('Error loading approved refunds', err)
    });
  }

  toggleSection(section: string) {
    this.activeSection = this.activeSection === section ? '' : section;
  }
}
