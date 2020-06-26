/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {Component} from '@angular/core';
import {TestBed} from '@angular/core/testing';
import {of} from 'rxjs';

describe('text instructions', () => {
  it('should handle all flavors of interpolated text', () => {
    @Component({
      template: `
        <div>a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g{{seven}}h{{eight}}i{{nine}}j</div>
        <div>a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g{{seven}}h{{eight}}i</div>
        <div>a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g{{seven}}h</div>
        <div>a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g</div>
        <div>a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f</div>
        <div>a{{one}}b{{two}}c{{three}}d{{four}}e</div>
        <div>a{{one}}b{{two}}c{{three}}d</div>
        <div>a{{one}}b{{two}}c</div>
        <div>a{{one}}b</div>
        <div>{{one}}</div>
      `
    })
    class App {
      one = 1;
      two = 2;
      three = 3;
      four = 4;
      five = 5;
      six = 6;
      seven = 7;
      eight = 8;
      nine = 9;
    }

    TestBed.configureTestingModule({declarations: [App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const allTextContent =
        Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('div'))
            .map((div: HTMLDivElement) => div.textContent);

    expect(allTextContent).toEqual([
      'a1b2c3d4e5f6g7h8i9j',
      'a1b2c3d4e5f6g7h8i',
      'a1b2c3d4e5f6g7h',
      'a1b2c3d4e5f6g',
      'a1b2c3d4e5f',
      'a1b2c3d4e',
      'a1b2c3d',
      'a1b2c',
      'a1b',
      '1',
    ]);
  });

  it('should handle piped values in interpolated text', () => {
    @Component({
      template: `
        <p>{{who | async}} sells {{(item | async)?.what}} down by the {{(item | async)?.where}}.</p>
      `
    })
    class App {
      who = of('Sally');
      item = of({
        what: 'seashells',
        where: 'seashore',
      });
    }

    TestBed.configureTestingModule({declarations: [App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const p = fixture.nativeElement.querySelector('p') as HTMLDivElement;
    expect(p.textContent).toBe('Sally sells seashells down by the seashore.');
  });

  it('should not sanitize urls in interpolated text', () => {
    @Component({
      template: '<p>{{thisisfine}}</p>',
    })
    class App {
      thisisfine = 'javascript:alert("image_of_dog_with_coffee_in_burning_building.gif")';
    }

    TestBed.configureTestingModule({declarations: [App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const p = fixture.nativeElement.querySelector('p');

    expect(p.textContent)
        .toBe('javascript:alert("image_of_dog_with_coffee_in_burning_building.gif")');
  });

  it('should not allow writing HTML in interpolated text', () => {
    @Component({
      template: '<div>{{test}}</div>',
    })
    class App {
      test = '<h1>LOL, big text</h1>';
    }

    TestBed.configureTestingModule({declarations: [App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const div = fixture.nativeElement.querySelector('div');

    expect(div.innerHTML).toBe('&lt;h1&gt;LOL, big text&lt;/h1&gt;');
  });

  it('should stringify functions used in bindings', () => {
    @Component({
      template: '<div>{{test}}</div>',
    })
    class App {
      test = function foo() {};
    }

    TestBed.configureTestingModule({declarations: [App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const div = fixture.nativeElement.querySelector('div');

    expect(div.innerHTML).toBe('function foo() { }');
  });
});
