import { moduleFor, RenderingTestCase, strip, equalTokens, runTask } from 'internal-test-helpers';
import { Component } from '@ember/-internals/glimmer';
import { set } from '@ember/-internals/metal';
import { EMBER_GLIMMER_IN_ELEMENT } from '@ember/canary-features';

const deprecationMessage = /The use of the private `{{-in-element}}` is deprecated, please refactor to the public `{{in-element}}`/;

moduleFor(
  '{{-in-element}}',
  class extends RenderingTestCase {
    ['@feature(!EMBER_GLIMMER_IN_ELEMENT) using {{#in-element whatever}} asserts']() {
      // the in-element keyword is not yet public API this test should be removed
      // once https://github.com/emberjs/rfcs/pull/287 lands and is enabled

      let el = document.createElement('div');
      expectAssertion(() => {
        this.render(strip`{{#in-element el}}{{/in-element}}`, { el });
      }, /The {{in-element}} helper cannot be used. \('-top-level' @ L1:C0\)/);
    }

    ['@test allows rendering into an external element']() {
      if (EMBER_GLIMMER_IN_ELEMENT) {
        expectDeprecation(deprecationMessage);
      }

      let someElement = document.createElement('div');

      this.render(
        strip`
          {{#-in-element someElement}}
            {{text}}
          {{/-in-element}}
        `,
        {
          someElement,
          text: 'Whoop!',
        }
      );

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'Whoop!');

      this.assertStableRerender();

      runTask(() => set(this.context, 'text', 'Huzzah!!'));

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'Huzzah!!');

      runTask(() => set(this.context, 'text', 'Whoop!'));

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'Whoop!');
    }

    ['@test it appends to the external element by default']() {
      if (EMBER_GLIMMER_IN_ELEMENT) {
        expectDeprecation(deprecationMessage);
      }

      let someElement = document.createElement('div');
      someElement.appendChild(document.createTextNode('foo '));

      this.render(
        strip`
          {{#-in-element someElement}}
            {{text}}
          {{/-in-element}}
        `,
        {
          someElement,
          text: 'bar',
        }
      );

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'foo bar');

      this.assertStableRerender();

      runTask(() => set(this.context, 'text', 'bar!!'));

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'foo bar!!');

      runTask(() => set(this.context, 'text', 'bar'));

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'foo bar');
    }

    ['@test allows appending to the external element with insertBefore=null']() {
      if (EMBER_GLIMMER_IN_ELEMENT) {
        expectDeprecation(deprecationMessage);
      }

      let someElement = document.createElement('div');
      someElement.appendChild(document.createTextNode('foo '));

      this.render(
        strip`
          {{#-in-element someElement insertBefore=null}}
            {{text}}
          {{/-in-element}}
        `,
        {
          someElement,
          text: 'bar',
        }
      );

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'foo bar');

      this.assertStableRerender();

      runTask(() => set(this.context, 'text', 'bar!!'));

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'foo bar!!');

      runTask(() => set(this.context, 'text', 'bar'));

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'foo bar');
    }

    ['@test allows clearing the external element with insertBefore=undefined']() {
      if (EMBER_GLIMMER_IN_ELEMENT) {
        expectDeprecation(deprecationMessage);
      }

      let someElement = document.createElement('div');
      someElement.appendChild(document.createTextNode('foo '));

      this.render(
        strip`
          {{#-in-element someElement insertBefore=undefined}}
            {{text}}
          {{/-in-element}}
        `,
        {
          someElement,
          text: 'bar',
        }
      );

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'bar');

      this.assertStableRerender();

      runTask(() => set(this.context, 'text', 'bar!!'));

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'bar!!');

      runTask(() => set(this.context, 'text', 'bar'));

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, 'bar');
    }

    ['@test does not allow insertBefore=non-null-value']() {
      if (EMBER_GLIMMER_IN_ELEMENT) {
        expectDeprecation(deprecationMessage);
      }

      let someElement = document.createElement('div');

      expectAssertion(() => {
        this.render(
          strip`
            {{#-in-element someElement insertBefore=".foo"}}
              {{text}}
            {{/-in-element}}
          `,
          {
            someElement,
            text: 'Whoop!',
          }
        );
      }, /Can only pass a null or undefined literals to insertBefore in -in-element, received:/);
    }

    ['@test components are cleaned up properly'](assert) {
      if (EMBER_GLIMMER_IN_ELEMENT) {
        expectDeprecation(deprecationMessage);
      }

      let hooks = [];

      let someElement = document.createElement('div');

      this.registerComponent('modal-display', {
        ComponentClass: Component.extend({
          didInsertElement() {
            hooks.push('didInsertElement');
          },

          willDestroyElement() {
            hooks.push('willDestroyElement');
          },
        }),

        template: `{{text}}`,
      });

      this.render(
        strip`
          {{#if showModal}}
            {{#-in-element someElement}}
              {{modal-display text=text}}
            {{/-in-element}}
          {{/if}}
        `,
        {
          someElement,
          text: 'Whoop!',
          showModal: false,
        }
      );

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, '');

      this.assertStableRerender();

      runTask(() => set(this.context, 'showModal', true));

      equalTokens(this.element, '<!---->');
      this.assertComponentElement(someElement.firstChild, {
        content: 'Whoop!',
      });

      runTask(() => set(this.context, 'text', 'Huzzah!'));

      equalTokens(this.element, '<!---->');
      this.assertComponentElement(someElement.firstChild, {
        content: 'Huzzah!',
      });

      runTask(() => set(this.context, 'text', 'Whoop!'));

      equalTokens(this.element, '<!---->');
      this.assertComponentElement(someElement.firstChild, {
        content: 'Whoop!',
      });

      runTask(() => set(this.context, 'showModal', false));

      equalTokens(this.element, '<!---->');
      equalTokens(someElement, '');

      assert.deepEqual(hooks, ['didInsertElement', 'willDestroyElement']);
    }

    ['@test appending to the root element should not cause double clearing']() {
      if (EMBER_GLIMMER_IN_ELEMENT) {
        expectDeprecation(deprecationMessage);
      }

      this.render(
        strip`
          Before
          {{#-in-element this.rootElement insertBefore=null}}
            {{this.text}}
          {{/-in-element}}
          After
        `,
        {
          rootElement: this.element,
          text: 'Whoop!',
        }
      );

      equalTokens(this.element, 'BeforeWhoop!<!---->After');

      this.assertStableRerender();

      runTask(() => set(this.context, 'text', 'Huzzah!'));

      equalTokens(this.element, 'BeforeHuzzah!<!---->After');

      // teardown happens in afterEach and should not cause double-clearing error
    }
  }
);
