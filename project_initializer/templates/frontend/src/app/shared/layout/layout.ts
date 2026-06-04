import {
  Component,
  signal,
  computed,
  inject,
  OnInit,
  OnDestroy,
  ChangeDetectionStrategy,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { Title } from '@angular/platform-browser';
import { LucideAngularModule } from 'lucide-angular';
import { filter, map } from 'rxjs/operators';

import { SidebarComponent } from '../sidebar/sidebar';
import { BottomTabBarComponent } from '../bottom-tab-bar/bottom-tab-bar';

@Component({
  selector: 'app-layout',
  imports: [RouterOutlet, SidebarComponent, BottomTabBarComponent, LucideAngularModule],
  templateUrl: './layout.html',
  styleUrl: './layout.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LayoutComponent implements OnInit, OnDestroy {
  private readonly router = inject(Router);
  private readonly title = inject(Title);

  isSidebarOpen = signal(false);
  isMobile = signal(false);

  showOverlay = computed(() => this.isSidebarOpen() && this.isMobile());

  readonly announced = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map(() => this.title.getTitle()),
    ),
    { initialValue: '' },
  );

  private resizeObserver?: ResizeObserver;

  ngOnInit() {
    this.checkScreenSize();
    this.initializeResizeObserver();
  }

  ngOnDestroy() {
    this.resizeObserver?.disconnect();
  }

  toggleSidebar() {
    this.isSidebarOpen.update((v) => !v);
  }

  closeSidebar() {
    this.isSidebarOpen.set(false);
  }

  private checkScreenSize() {
    if (typeof window !== 'undefined') {
      const mobile = window.innerWidth < 768;
      this.isMobile.set(mobile);
      if (mobile) this.isSidebarOpen.set(false);
    }
  }

  private initializeResizeObserver() {
    if (typeof window === 'undefined' || !('ResizeObserver' in window)) return;

    this.resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const mobile = entry.contentRect.width < 768;
        this.isMobile.set(mobile);
        if (mobile && this.isSidebarOpen()) {
          this.isSidebarOpen.set(false);
        }
      }
    });
    this.resizeObserver.observe(document.body);
  }
}
