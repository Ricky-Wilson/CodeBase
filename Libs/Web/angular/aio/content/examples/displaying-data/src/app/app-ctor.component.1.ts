import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  template: `
    <h1>{{title}} [Ctor version]</h1>
    <h2>My favorite hero is: {{myHero}}</h2>
    `
})
// #docregion class
export class AppComponent {
  title: string;
  myHero: string;

  constructor() {
    this.title = 'Tour of Heroes';
    this.myHero = 'Windstorm';
  }
}
