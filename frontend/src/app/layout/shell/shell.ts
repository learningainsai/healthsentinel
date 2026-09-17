import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavBar } from '../../shared/nav-bar/nav-bar';
import { TabNav } from '../../shared/tab-nav/tab-nav';

@Component({
  imports: [RouterOutlet, NavBar, TabNav],
  selector: 'app-shell',
  templateUrl: './shell.html',
})
export class Shell {}
