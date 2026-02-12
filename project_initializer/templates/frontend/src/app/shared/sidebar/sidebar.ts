import { Component, computed, input, output, ChangeDetectionStrategy } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

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
}
