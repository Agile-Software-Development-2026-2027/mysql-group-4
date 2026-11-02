import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Topbar } from '../../components/topbar/topbar';

@Component({
  selector: 'app-homepage',
  imports: [RouterLink, Topbar],
  templateUrl: './homepage.html',
  styleUrl: './homepage.scss',
})
export class Homepage {
  siteName = 'MYSOL';
}
