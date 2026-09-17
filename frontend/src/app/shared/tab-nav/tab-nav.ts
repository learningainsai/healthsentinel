import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

interface Tab {
  path: string;
  label: string;
  icon: string;
}

// Primary navigation for the authenticated app shell. Rendered twice by the
// template: as a horizontal tab strip in the header (desktop) and as a fixed
// bottom bar (mobile) — same tab list, same active-state logic, two layouts.
const TABS: Tab[] = [
  { path: '/dashboard', label: 'Dashboard', icon: '🏠' },
  { path: '/log', label: 'Log Data', icon: '📥' },
  { path: '/analysis', label: 'Run Analysis', icon: '📈' },
  { path: '/ask', label: 'Ask Sentinel', icon: '💬' },
  { path: '/about', label: 'About App', icon: 'ℹ️' },
];

@Component({
  imports: [RouterLink, RouterLinkActive],
  selector: 'app-tab-nav',
  templateUrl: './tab-nav.html',
})
export class TabNav {
  protected readonly tabs = TABS;
}
