/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {CompilePipeMetadata, identifierName} from '../compile_metadata';
import {CompileReflector} from '../compile_reflector';
import {DefinitionKind} from '../constant_pool';
import * as o from '../output/output_ast';
import {error, OutputContext} from '../util';

import {compileFactoryFunction, dependenciesFromGlobalMetadata, R3DependencyMetadata, R3FactoryTarget} from './r3_factory';
import {Identifiers as R3} from './r3_identifiers';
import {R3Reference, typeWithParameters, wrapReference} from './util';

export interface R3PipeMetadata {
  /**
   * Name of the pipe type.
   */
  name: string;

  /**
   * An expression representing a reference to the pipe itself.
   */
  type: R3Reference;

  /**
   * An expression representing the pipe being compiled, intended for use within a class definition
   * itself.
   *
   * This can differ from the outer `type` if the class is being compiled by ngcc and is inside an
   * IIFE structure that uses a different name internally.
   */
  internalType: o.Expression;

  /**
   * Number of generic type parameters of the type itself.
   */
  typeArgumentCount: number;

  /**
   * Name of the pipe.
   */
  pipeName: string;

  /**
   * Dependencies of the pipe's constructor.
   */
  deps: R3DependencyMetadata[]|null;

  /**
   * Whether the pipe is marked as pure.
   */
  pure: boolean;
}

export function compilePipeFromMetadata(metadata: R3PipeMetadata) {
  const definitionMapValues: {key: string, quoted: boolean, value: o.Expression}[] = [];

  // e.g. `name: 'myPipe'`
  definitionMapValues.push({key: 'name', value: o.literal(metadata.pipeName), quoted: false});

  // e.g. `type: MyPipe`
  definitionMapValues.push({key: 'type', value: metadata.type.value, quoted: false});

  // e.g. `pure: true`
  definitionMapValues.push({key: 'pure', value: o.literal(metadata.pure), quoted: false});

  const expression = o.importExpr(R3.definePipe).callFn([o.literalMap(definitionMapValues)]);
  const type = new o.ExpressionType(o.importExpr(R3.PipeDefWithMeta, [
    typeWithParameters(metadata.type.type, metadata.typeArgumentCount),
    new o.ExpressionType(new o.LiteralExpr(metadata.pipeName)),
  ]));

  return {expression, type};
}

/**
 * Write a pipe definition to the output context.
 */
export function compilePipeFromRender2(
    outputCtx: OutputContext, pipe: CompilePipeMetadata, reflector: CompileReflector) {
  const name = identifierName(pipe.type);

  if (!name) {
    return error(`Cannot resolve the name of ${pipe.type}`);
  }

  const type = outputCtx.importExpr(pipe.type.reference);
  const metadata: R3PipeMetadata = {
    name,
    type: wrapReference(type),
    internalType: type,
    pipeName: pipe.name,
    typeArgumentCount: 0,
    deps: dependenciesFromGlobalMetadata(pipe.type, outputCtx, reflector),
    pure: pipe.pure,
  };
  const res = compilePipeFromMetadata(metadata);
  const factoryRes = compileFactoryFunction(
      {...metadata, injectFn: R3.directiveInject, target: R3FactoryTarget.Pipe});
  const definitionField = outputCtx.constantPool.propertyNameOf(DefinitionKind.Pipe);
  const ngFactoryDefStatement = new o.ClassStmt(
      /* name */ name,
      /* parent */ null,
      /* fields */
      [new o.ClassField(
          /* name */ 'ɵfac',
          /* type */ o.INFERRED_TYPE,
          /* modifiers */[o.StmtModifier.Static],
          /* initializer */ factoryRes.factory)],
      /* getters */[],
      /* constructorMethod */ new o.ClassMethod(null, [], []),
      /* methods */[]);
  const pipeDefStatement = new o.ClassStmt(
      /* name */ name,
      /* parent */ null,
      /* fields */[new o.ClassField(
          /* name */ definitionField,
          /* type */ o.INFERRED_TYPE,
          /* modifiers */[o.StmtModifier.Static],
          /* initializer */ res.expression)],
      /* getters */[],
      /* constructorMethod */ new o.ClassMethod(null, [], []),
      /* methods */[]);

  outputCtx.statements.push(ngFactoryDefStatement, pipeDefStatement);
}
