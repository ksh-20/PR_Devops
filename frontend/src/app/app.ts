import { Component, signal } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';

import { Navbar } from './components/navbar/navbar';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, Navbar],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {

  protected readonly title = signal('project1');

  constructor(public router: Router) { }

}