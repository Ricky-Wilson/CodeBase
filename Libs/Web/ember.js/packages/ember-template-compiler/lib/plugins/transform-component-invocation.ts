import { StaticTemplateMeta } from '@ember/-internals/views';
import { AST, ASTPlugin, ASTPluginEnvironment } from '@glimmer/syntax';
import calculateLocationDisplay from '../system/calculate-location-display';
import { Builders } from '../types';
import { isPath, trackLocals } from './utils';

/**
  Transforms unambigious invocations of closure components to be wrapped with
  the component helper. Once these syntaxes are fully supported by Glimmer VM
  natively, this transform can be removed.

  ```handlebars
  {{!-- this.foo is not a legal helper/component name --}}
  {{this.foo "with" some="args"}}
  ```

  with

  ```handlebars
  {{component this.foo "with" some="args"}}
  ```

  and

  ```handlebars
  {{!-- this.foo is not a legal helper/component name --}}
  {{#this.foo}}...{{/this.foo}}
  ```

  with

  ```handlebars
  {{#component this.foo}}...{{/component}}
  ```

  and

  ```handlebars
  {{!-- foo.bar is not a legal helper/component name --}}
  {{foo.bar "with" some="args"}}
  ```

  with

  ```handlebars
  {{component foo.bar "with" some="args"}}
  ```

  and

  ```handlebars
  {{!-- foo.bar is not a legal helper/component name --}}
  {{#foo.bar}}...{{/foo.bar}}
  ```

  with

  ```handlebars
  {{#component foo.bar}}...{{/component}}
  ```

  and

  ```handlebars
  {{!-- @foo is not a legal helper/component name --}}
  {{@foo "with" some="args"}}
  ```

  with

  ```handlebars
  {{component @foo "with" some="args"}}
  ```

  and

  ```handlebars
  {{!-- @foo is not a legal helper/component name --}}
  {{#@foo}}...{{/@foo}}
  ```

  with

  ```handlebars
  {{#component @foo}}...{{/component}}
  ```

  and

  ```handlebars
  {{#let ... as |foo|}}
    {{!-- foo is a local variable --}}
    {{foo "with" some="args"}}
  {{/let}}
  ```

  with

  ```handlebars
  {{#let ... as |foo|}}
    {{component foo "with" some="args"}}
  {{/let}}
  ```

  and

  ```handlebars
  {{#let ... as |foo|}}
    {{!-- foo is a local variable --}}
    {{#foo}}...{{/foo}}
  {{/let}}
  ```

  with

  ```handlebars
  {{#let ... as |foo|}}
    {{#component foo}}...{{/component}}
  {{/let}}
  ```

  @private
  @class TransFormComponentInvocation
*/
export default function transformComponentInvocation(env: ASTPluginEnvironment): ASTPlugin {
  let { moduleName } = env.meta as StaticTemplateMeta;
  let { builders: b } = env.syntax;

  let { hasLocal, node } = trackLocals();

  let isAttrs = false;

  return {
    name: 'transform-component-invocation',

    visitor: {
      Program: node,

      ElementNode: {
        keys: {
          attributes: {
            enter() {
              isAttrs = true;
            },

            exit() {
              isAttrs = false;
            },
          },

          children: node,
        },
      },

      BlockStatement(node: AST.BlockStatement) {
        if (isBlockInvocation(node, hasLocal)) {
          wrapInComponent(moduleName, node, b);
        }
      },

      MustacheStatement(node: AST.MustacheStatement): AST.Node | void {
        if (!isAttrs && isInlineInvocation(node, hasLocal)) {
          wrapInComponent(moduleName, node, b);
        }
      },
    },
  };
}

function isInlineInvocation(
  node: AST.MustacheStatement,
  hasLocal: (k: string) => boolean
): boolean {
  let { path } = node;
  return isPath(path) && isIllegalName(path, hasLocal) && hasArguments(node);
}

function isIllegalName(node: AST.PathExpression, hasLocal: (k: string) => boolean): boolean {
  return isThisPath(node) || isDotPath(node) || isNamedArg(node) || isLocalVariable(node, hasLocal);
}

function isThisPath(node: AST.PathExpression): boolean {
  return node.this === true;
}

function isDotPath(node: AST.PathExpression): boolean {
  return node.parts.length > 1;
}

function isNamedArg(node: AST.PathExpression): boolean {
  return node.data === true;
}

function isLocalVariable(node: AST.PathExpression, hasLocal: (k: string) => boolean): boolean {
  return !node.this && hasLocal(node.parts[0]);
}

function hasArguments(node: AST.MustacheStatement): boolean {
  return node.params.length > 0 || node.hash.pairs.length > 0;
}

function isBlockInvocation(node: AST.BlockStatement, hasLocal: (k: string) => boolean): boolean {
  return isPath(node.path) && isIllegalName(node.path, hasLocal);
}

function wrapInAssertion(moduleName: string, node: AST.PathExpression, b: Builders) {
  let error = b.string(
    `expected \`${
      node.original
    }\` to be a contextual component but found a string. Did you mean \`(component ${
      node.original
    })\`? ${calculateLocationDisplay(moduleName, node.loc)}`
  );

  return b.sexpr(
    b.path('-assert-implicit-component-helper-argument'),
    [node, error],
    b.hash(),
    node.loc
  );
}

function wrapInComponent(
  moduleName: string,
  node: AST.MustacheStatement | AST.BlockStatement,
  b: Builders
) {
  let component = wrapInAssertion(moduleName, node.path as AST.PathExpression, b);
  node.path = b.path('component');
  node.params.unshift(component);
}
