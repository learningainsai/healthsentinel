import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { Auth } from '../../core/auth';

@Component({
  imports: [],
  selector: 'app-nav-bar',
  styleUrl: './nav-bar.scss',
  templateUrl: './nav-bar.html',
})
export class NavBar {
  private readonly auth = inject(Auth);
  private readonly router = inject(Router);

  protected readonly account = this.auth.currentAccount;

  logout(): void {
    this.auth.logout();
    this.router.navigateByUrl('/login');
  }
}
