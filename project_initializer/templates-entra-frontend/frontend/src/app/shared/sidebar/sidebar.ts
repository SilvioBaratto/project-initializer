import { Component, computed, input, output, inject, ChangeDetectionStrategy } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

interface NavItem {
  name: string;
  route: string;
  icon: 'chat';
}

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SidebarComponent {
  private readonly authService = inject(AuthService);

  isOpen = input<boolean>(false);
  isMobile = input<boolean>(false);

  closeSidebar = output<void>();

  navItems: NavItem[] = [
    { name: 'Chatbot', route: '/', icon: 'chat' },
  ];

  showSidebar = computed(() => !this.isMobile() || this.isOpen());

  onNavClick() {
    this.closeSidebar.emit();
  }

  onLogout() {
    // MSAL logoutRedirect navigates the browser to Microsoft's logout endpoint;
    // a subsequent router.navigate would never execute, so we omit it.
    this.authService.logout();
  }
}
