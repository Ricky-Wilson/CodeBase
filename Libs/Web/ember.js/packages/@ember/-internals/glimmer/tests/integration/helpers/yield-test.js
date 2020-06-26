import { RenderingTestCase, moduleFor, runTask } from 'internal-test-helpers';

import { set } from '@ember/-internals/metal';

import { Component } from '../../utils/helpers';

moduleFor(
  'Helpers test: {{yield}} helper',
  class extends RenderingTestCase {
    ['@test can yield to a default block']() {
      this.registerComponent('yield-comp', {
        template: '[In layout:] {{yield}}',
      });

      this.render('{{#yield-comp}}[In Block:] {{object.title}}{{/yield-comp}}', {
        object: { title: 'Seattle' },
      });
      this.assertText('[In layout:] [In Block:] Seattle');

      this.assertStableRerender();

      runTask(() => set(this.context, 'object.title', 'Vancouver'));
      this.assertText('[In layout:] [In Block:] Vancouver');

      runTask(() => set(this.context, 'object', { title: 'Seattle' }));
      this.assertText('[In layout:] [In Block:] Seattle');
    }

    ['@feature(EMBER_NAMED_BLOCKS) can yield to a named block']() {
      // This test fails when the default Ember component backing class is used:
      this.registerComponent('yield-comp', {
        template: '[In layout:] {{yield to="block"}}',

        // It passes with no backing class:
        // ComponentClass: null,

        // And it passes using `GlimmerishComponent`:
        // ComponentClass: require('../../utils/glimmerish-component').default,
      });

      this.render('<YieldComp><:block>[In block:] {{object.title}}</:block></YieldComp>', {
        object: { title: 'Seattle' },
      });

      this.assertText('[In layout:] [In block:] Seattle');

      this.assertStableRerender();

      runTask(() => set(this.context, 'object.title', 'Vancouver'));
      this.assertText('[In layout:] [In block:] Vancouver');

      runTask(() => set(this.context, 'object', { title: 'Seattle' }));
      this.assertText('[In layout:] [In block:] Seattle');
    }

    ['@test templates should yield to block inside a nested component']() {
      this.registerComponent('outer-comp', {
        template: '<div>[In layout:] {{yield}}</div>',
      });
      this.registerComponent('inner-comp', {
        template: '{{#outer-comp}}[In Block:] {{object.title}}{{/outer-comp}}',
      });

      this.render('{{inner-comp object=object}}', {
        object: { title: 'Seattle' },
      });
      this.assertText('[In layout:] [In Block:] Seattle');

      this.assertStableRerender();

      runTask(() => set(this.context, 'object.title', 'Vancouver'));
      this.assertText('[In layout:] [In Block:] Vancouver');

      runTask(() => set(this.context, 'object', { title: 'Seattle' }));
      this.assertText('[In layout:] [In Block:] Seattle');
    }

    ['@test templates should yield to block, when the yield is embedded in a each helper']() {
      let list = [1, 2, 3];

      this.registerComponent('outer-comp', {
        template: '{{#each list as |item|}}{{yield}}{{/each}}',
      });

      this.render('{{#outer-comp list=list}}Hello{{/outer-comp}}', {
        list: list,
      });
      this.assertText('HelloHelloHello');

      this.assertStableRerender();

      runTask(() => set(this.context, 'list', [4, 5]));
      this.assertText('HelloHello');

      runTask(() => set(this.context, 'list', list));
      this.assertText('HelloHelloHello');
    }

    ['@test templates should yield to block, when the yield is embedded in a if helper']() {
      this.registerComponent('outer-comp', {
        template: '{{#if boolean}}{{yield}}{{/if}}',
      });

      this.render('{{#outer-comp boolean=boolean}}Hello{{/outer-comp}}', {
        boolean: true,
      });
      this.assertText('Hello');

      this.assertStableRerender();

      runTask(() => set(this.context, 'boolean', false));
      this.assertText('');

      runTask(() => set(this.context, 'boolean', true));
      this.assertText('Hello');
    }

    ['@test simple curlies inside of a yielded block should work when the yield is nested inside of another view']() {
      this.registerComponent('kiwi-comp', {
        template: '{{#if falsy}}{{else}}{{yield}}{{/if}}',
      });

      this.render('{{#kiwi-comp}}{{text}}{{/kiwi-comp}}', { text: 'ohai' });
      this.assertText('ohai');

      this.assertStableRerender();

      runTask(() => set(this.context, 'text', 'portland'));
      this.assertText('portland');

      runTask(() => set(this.context, 'text', 'ohai'));
      this.assertText('ohai');
    }

    ['@test nested simple curlies inside of a yielded block should work when the yield is nested inside of another view']() {
      this.registerComponent('parent-comp', {
        template: '{{#if falsy}}{{else}}{{yield}}{{/if}}',
      });
      this.registerComponent('child-comp', {
        template: '{{#if falsy}}{{else}}{{text}}{{/if}}',
      });

      this.render('{{#parent-comp}}{{child-comp text=text}}{{/parent-comp}}', {
        text: 'ohai',
      });
      this.assertText('ohai');

      this.assertStableRerender();

      runTask(() => set(this.context, 'text', 'portland'));
      this.assertText('portland');

      runTask(() => set(this.context, 'text', 'ohai'));
      this.assertText('ohai');
    }

    ['@test yielding to a non-existent block is not an error']() {
      this.registerComponent('yielding-comp', { template: 'Hello:{{yield}}' });
      this.registerComponent('outer-comp', {
        template: '{{yielding-comp}} {{title}}',
      });

      this.render('{{outer-comp title=title}}', { title: 'Mr. Selden' });

      this.assertText('Hello: Mr. Selden');

      this.assertStableRerender();

      runTask(() => set(this.context, 'title', 'Mr. Chag'));
      this.assertText('Hello: Mr. Chag');

      runTask(() => set(this.context, 'title', 'Mr. Selden'));
      this.assertText('Hello: Mr. Selden');
    }

    ['@test yield uses the original context']() {
      let KiwiCompComponent = Component.extend({ boundText: 'Inner' });

      this.registerComponent('kiwi-comp', {
        ComponentClass: KiwiCompComponent,
        template: '<p>{{boundText}}</p><p>{{yield}}</p>',
      });

      this.render('{{#kiwi-comp}}{{boundText}}{{/kiwi-comp}}', {
        boundText: 'Original',
      });
      this.assertText('InnerOriginal');

      this.assertStableRerender();

      runTask(() => set(this.context, 'boundText', 'Otherworld'));
      this.assertText('InnerOtherworld');

      runTask(() => set(this.context, 'boundText', 'Original'));
      this.assertText('InnerOriginal');
    }

    ["@test outer block param doesn't mask inner component property"]() {
      let KiwiCompComponent = Component.extend({ boundText: 'Inner' });

      this.registerComponent('kiwi-comp', {
        ComponentClass: KiwiCompComponent,
        template: '<p>{{boundText}}</p><p>{{yield}}</p>',
      });

      this.render('{{#with boundText as |item|}}{{#kiwi-comp}}{{item}}{{/kiwi-comp}}{{/with}}', {
        boundText: 'Outer',
      });
      this.assertText('InnerOuter');

      this.assertStableRerender();

      runTask(() => set(this.context, 'boundText', 'Otherworld'));
      this.assertText('InnerOtherworld');

      runTask(() => set(this.context, 'boundText', 'Outer'));
      this.assertText('InnerOuter');
    }

    ["@test inner block param doesn't mask yield property"]() {
      let KiwiCompComponent = Component.extend({ boundText: 'Inner' });

      this.registerComponent('kiwi-comp', {
        ComponentClass: KiwiCompComponent,
        template: '{{#with boundText as |item|}}<p>{{item}}</p><p>{{yield}}</p>{{/with}}',
      });

      this.render('{{#kiwi-comp}}{{item}}{{/kiwi-comp}}', { item: 'Outer' });
      this.assertText('InnerOuter');

      this.assertStableRerender();

      runTask(() => set(this.context, 'item', 'Otherworld'));
      this.assertText('InnerOtherworld');

      runTask(() => set(this.context, 'item', 'Outer'));
      this.assertText('InnerOuter');
    }

    ['@test can bind a block param to a component and use it in yield']() {
      this.registerComponent('kiwi-comp', {
        template: '<p>{{content}}</p><p>{{yield}}</p>',
      });

      this.render(
        '{{#with boundText as |item|}}{{#kiwi-comp content=item}}{{item}}{{/kiwi-comp}}{{/with}}',
        { boundText: 'Outer' }
      );
      this.assertText('OuterOuter');

      this.assertStableRerender();

      runTask(() => set(this.context, 'boundText', 'Update'));
      this.assertText('UpdateUpdate');

      runTask(() => set(this.context, 'boundText', 'Outer'));
      this.assertText('OuterOuter');
    }

    // INUR not need with no data update
    ['@test yield should not introduce a view'](assert) {
      let ParentCompComponent = Component.extend({ isParentComponent: true });

      let ChildCompComponent = Component.extend({
        didReceiveAttrs() {
          this._super();
          let parentView = this.get('parentView');

          assert.ok(parentView.get('isParentComponent'));
        },
      });

      this.registerComponent('parent-comp', {
        ComponentClass: ParentCompComponent,
        template: '{{yield}}',
      });
      this.registerComponent('child-comp', {
        ComponentClass: ChildCompComponent,
      });

      this.render('{{#parent-comp}}{{child-comp}}{{/parent-comp}}');
    }

    ['@test yield with nested components (#3220)']() {
      this.registerComponent('inner-component', { template: '{{yield}}' });
      this.registerComponent('outer-component', {
        template: '{{#inner-component}}<span>{{yield}}</span>{{/inner-component}}',
      });

      this.render('{{#outer-component}}Hello {{boundText}}{{/outer-component}}', {
        boundText: 'world',
      });
      this.assertText('Hello world');

      this.assertStableRerender();

      runTask(() => set(this.context, 'boundText', 'update'));
      this.assertText('Hello update');

      runTask(() => set(this.context, 'boundText', 'world'));
      this.assertText('Hello world');
    }
  }
);
