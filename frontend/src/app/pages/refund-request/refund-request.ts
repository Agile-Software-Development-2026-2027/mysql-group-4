import { Component } from '@angular/core';
import { Topbar } from '../../components/topbar/topbar';

@Component({
  selector: 'app-refund-request',
  standalone: true,
  imports: [Topbar],
  templateUrl: './refund-request.html',
  styleUrl: './refund-request.scss',
})
export class RefundRequestComponent {}
