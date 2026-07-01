import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AdminMembersComponent } from './components/admin-members/admin-members';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [
    CommonModule,
    AdminMembersComponent,
  ],
  templateUrl: './admin.html',
  styleUrl: './admin.css',
})
export class AdminPortal implements OnInit {

  constructor() {}

  ngOnInit(): void {}
}
