/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {Component, destroyPlatform, DoBootstrap, EventEmitter, Injector, Input, NgModule, Output} from '@angular/core';
import {BrowserModule} from '@angular/platform-browser';
import {platformBrowserDynamic} from '@angular/platform-browser-dynamic';
import {browserDetection} from '@angular/platform-browser/testing/src/browser_util';
import {Subject} from 'rxjs';

import {createCustomElement, NgElementConstructor} from '../src/create-custom-element';
import {NgElementStrategy, NgElementStrategyEvent, NgElementStrategyFactory} from '../src/element-strategy';

type WithFooBar = {
  fooFoo: string,
  barBar: string
};

if (browserDetection.supportsCustomElements) {
  describe('createCustomElement', () => {
    let selectorUid = 0;
    let testContainer: HTMLDivElement;
    let NgElementCtor: NgElementConstructor<WithFooBar>;
    let strategy: TestStrategy;
    let strategyFactory: TestStrategyFactory;
    let injector: Injector;

    beforeAll(done => {
      testContainer = document.createElement('div');
      document.body.appendChild(testContainer);
      destroyPlatform();
      platformBrowserDynamic()
          .bootstrapModule(TestModule)
          .then(ref => {
            injector = ref.injector;
            strategyFactory = new TestStrategyFactory();
            strategy = strategyFactory.testStrategy;

            const {selector, ElementCtor} = createTestCustomElement();
            NgElementCtor = ElementCtor;

            // The `@webcomponents/custom-elements/src/native-shim.js` polyfill allows us to create
            // new instances of the NgElement which extends HTMLElement, as long as we define it.
            customElements.define(selector, NgElementCtor);
          })
          .then(done, done.fail);
    });

    afterEach(() => strategy.reset());

    afterAll(() => {
      destroyPlatform();
      document.body.removeChild(testContainer);
      (testContainer as any) = null;
    });

    it('should use a default strategy for converting component inputs', () => {
      expect(NgElementCtor.observedAttributes).toEqual(['foo-foo', 'barbar']);
    });

    it('should send input values from attributes when connected', () => {
      const element = new NgElementCtor(injector);
      element.setAttribute('foo-foo', 'value-foo-foo');
      element.setAttribute('barbar', 'value-barbar');
      element.connectedCallback();
      expect(strategy.connectedElement).toBe(element);

      expect(strategy.getInputValue('fooFoo')).toBe('value-foo-foo');
      expect(strategy.getInputValue('barBar')).toBe('value-barbar');
    });

    it('should work even if when the constructor is not called (due to polyfill)', () => {
      // Some polyfills (e.g. `document-register-element`) do not call the constructor of custom
      // elements. Currently, all the constructor does is initialize the `injector` property. This
      // test simulates not having called the constructor by "unsetting" the property.
      //
      // NOTE:
      // If the constructor implementation changes in the future, this test needs to be adjusted
      // accordingly.
      const element = new NgElementCtor(injector);
      delete (element as any).injector;

      element.setAttribute('foo-foo', 'value-foo-foo');
      element.setAttribute('barbar', 'value-barbar');
      element.connectedCallback();

      expect(strategy.connectedElement).toBe(element);
      expect(strategy.getInputValue('fooFoo')).toBe('value-foo-foo');
      expect(strategy.getInputValue('barBar')).toBe('value-barbar');
    });

    it('should listen to output events after connected', () => {
      const element = new NgElementCtor(injector);
      element.connectedCallback();

      let eventValue: any = null;
      element.addEventListener('some-event', (e: Event) => eventValue = (e as CustomEvent).detail);
      strategy.events.next({name: 'some-event', value: 'event-value'});

      expect(eventValue).toEqual('event-value');
    });

    it('should not listen to output events after disconnected', () => {
      const element = new NgElementCtor(injector);
      element.connectedCallback();
      element.disconnectedCallback();
      expect(strategy.disconnectCalled).toBe(true);

      let eventValue: any = null;
      element.addEventListener('some-event', (e: Event) => eventValue = (e as CustomEvent).detail);
      strategy.events.next({name: 'some-event', value: 'event-value'});

      expect(eventValue).toEqual(null);
    });

    it('should properly set getters/setters on the element', () => {
      const element = new NgElementCtor(injector);
      element.fooFoo = 'foo-foo-value';
      element.barBar = 'barBar-value';

      expect(strategy.inputs.get('fooFoo')).toBe('foo-foo-value');
      expect(strategy.inputs.get('barBar')).toBe('barBar-value');
    });

    it('should properly handle getting/setting properties on the element even if the constructor is not called',
       () => {
         // Create a custom element while ensuring that the `NgElementStrategy` is not created
         // inside the constructor. This is done to emulate the behavior of some polyfills that do
         // not call the constructor.
         strategyFactory.create = () => undefined as unknown as NgElementStrategy;
         const element = new NgElementCtor(injector);
         strategyFactory.create = TestStrategyFactory.prototype.create;

         element.fooFoo = 'foo-foo-value';
         element.barBar = 'barBar-value';

         expect(strategy.inputs.get('fooFoo')).toBe('foo-foo-value');
         expect(strategy.inputs.get('barBar')).toBe('barBar-value');
       });

    it('should capture properties set before upgrading the element', () => {
      // Create a regular element and set properties on it.
      const {selector, ElementCtor} = createTestCustomElement();
      const element = Object.assign(document.createElement(selector), {
        fooFoo: 'foo-prop-value',
        barBar: 'bar-prop-value',
      });
      expect(element.fooFoo).toBe('foo-prop-value');
      expect(element.barBar).toBe('bar-prop-value');

      // Upgrade the element to a Custom Element and insert it into the DOM.
      customElements.define(selector, ElementCtor);
      testContainer.appendChild(element);
      expect(element.fooFoo).toBe('foo-prop-value');
      expect(element.barBar).toBe('bar-prop-value');

      expect(strategy.inputs.get('fooFoo')).toBe('foo-prop-value');
      expect(strategy.inputs.get('barBar')).toBe('bar-prop-value');
    });

    it('should capture properties set after upgrading the element but before inserting it into the DOM',
       () => {
         // Create a regular element and set properties on it.
         const {selector, ElementCtor} = createTestCustomElement();
         const element = Object.assign(document.createElement(selector), {
           fooFoo: 'foo-prop-value',
           barBar: 'bar-prop-value',
         });
         expect(element.fooFoo).toBe('foo-prop-value');
         expect(element.barBar).toBe('bar-prop-value');

         // Upgrade the element to a Custom Element (without inserting it into the DOM) and update a
         // property.
         customElements.define(selector, ElementCtor);
         customElements.upgrade(element);
         element.barBar = 'bar-prop-value-2';
         expect(element.fooFoo).toBe('foo-prop-value');
         expect(element.barBar).toBe('bar-prop-value-2');

         // Insert the element into the DOM.
         testContainer.appendChild(element);
         expect(element.fooFoo).toBe('foo-prop-value');
         expect(element.barBar).toBe('bar-prop-value-2');

         expect(strategy.inputs.get('fooFoo')).toBe('foo-prop-value');
         expect(strategy.inputs.get('barBar')).toBe('bar-prop-value-2');
       });

    it('should allow overwriting properties with attributes after upgrading the element but before inserting it into the DOM',
       () => {
         // Create a regular element and set properties on it.
         const {selector, ElementCtor} = createTestCustomElement();
         const element = Object.assign(document.createElement(selector), {
           fooFoo: 'foo-prop-value',
           barBar: 'bar-prop-value',
         });
         expect(element.fooFoo).toBe('foo-prop-value');
         expect(element.barBar).toBe('bar-prop-value');

         // Upgrade the element to a Custom Element (without inserting it into the DOM) and set an
         // attribute.
         customElements.define(selector, ElementCtor);
         customElements.upgrade(element);
         element.setAttribute('barbar', 'bar-attr-value');
         expect(element.fooFoo).toBe('foo-prop-value');
         expect(element.barBar).toBe('bar-attr-value');

         // Insert the element into the DOM.
         testContainer.appendChild(element);
         expect(element.fooFoo).toBe('foo-prop-value');
         expect(element.barBar).toBe('bar-attr-value');

         expect(strategy.inputs.get('fooFoo')).toBe('foo-prop-value');
         expect(strategy.inputs.get('barBar')).toBe('bar-attr-value');
       });

    // Helpers
    function createTestCustomElement() {
      return {
        selector: `test-element-${++selectorUid}`,
        ElementCtor: createCustomElement<WithFooBar>(TestComponent, {injector, strategyFactory}),
      };
    }

    @Component({
      selector: 'test-component',
      template: 'TestComponent|foo({{ fooFoo }})|bar({{ barBar }})',
    })
    class TestComponent {
      @Input() fooFoo: string = 'foo';
      // TODO(issue/24571): remove '!'.
      @Input('barbar') barBar!: string;

      @Output() bazBaz = new EventEmitter<boolean>();
      @Output('quxqux') quxQux = new EventEmitter<Object>();
    }
    @NgModule({
      imports: [BrowserModule],
      declarations: [TestComponent],
      entryComponents: [TestComponent],
    })
    class TestModule implements DoBootstrap {
      ngDoBootstrap() {}
    }

    class TestStrategy implements NgElementStrategy {
      connectedElement: HTMLElement|null = null;
      disconnectCalled = false;
      inputs = new Map<string, any>();

      events = new Subject<NgElementStrategyEvent>();

      connect(element: HTMLElement): void {
        this.connectedElement = element;
      }

      disconnect(): void {
        this.disconnectCalled = true;
      }

      getInputValue(propName: string): any {
        return this.inputs.get(propName);
      }

      setInputValue(propName: string, value: string): void {
        this.inputs.set(propName, value);
      }

      reset(): void {
        this.connectedElement = null;
        this.disconnectCalled = false;
        this.inputs.clear();
      }
    }

    class TestStrategyFactory implements NgElementStrategyFactory {
      testStrategy = new TestStrategy();

      create(injector: Injector): NgElementStrategy {
        // Although not used by the `TestStrategy`, verify that the injector is provided.
        if (!injector) {
          throw new Error(
              'Expected injector to be passed to `TestStrategyFactory#create()`, but received ' +
              `value of type ${typeof injector}: ${injector}`);
        }

        return this.testStrategy;
      }
    }
  });
}
