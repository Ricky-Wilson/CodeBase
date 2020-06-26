/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {compileInjectable as compileIvyInjectable, Expression, Identifiers, LiteralExpr, R3DependencyMetadata, R3FactoryTarget, R3InjectableMetadata, R3ResolvedDependencyType, Statement, WrappedNodeExpr} from '@angular/compiler';
import * as ts from 'typescript';

import {ErrorCode, FatalDiagnosticError} from '../../diagnostics';
import {DefaultImportRecorder} from '../../imports';
import {InjectableClassRegistry} from '../../metadata';
import {ClassDeclaration, Decorator, ReflectionHost, reflectObjectLiteral} from '../../reflection';
import {AnalysisOutput, CompileResult, DecoratorHandler, DetectResult, HandlerPrecedence} from '../../transform';

import {compileNgFactoryDefField} from './factory';
import {generateSetClassMetadataCall} from './metadata';
import {findAngularDecorator, getConstructorDependencies, getValidConstructorDependencies, isAngularCore, unwrapConstructorDependencies, unwrapForwardRef, validateConstructorDependencies, wrapTypeReference} from './util';

export interface InjectableHandlerData {
  meta: R3InjectableMetadata;
  metadataStmt: Statement|null;
  ctorDeps: R3DependencyMetadata[]|'invalid'|null;
  needsFactory: boolean;
}

/**
 * Adapts the `compileIvyInjectable` compiler for `@Injectable` decorators to the Ivy compiler.
 */
export class InjectableDecoratorHandler implements
    DecoratorHandler<Decorator, InjectableHandlerData, unknown> {
  constructor(
      private reflector: ReflectionHost, private defaultImportRecorder: DefaultImportRecorder,
      private isCore: boolean, private strictCtorDeps: boolean,
      private injectableRegistry: InjectableClassRegistry,
      /**
       * What to do if the injectable already contains a ɵprov property.
       *
       * If true then an error diagnostic is reported.
       * If false then there is no error and a new ɵprov property is not added.
       */
      private errorOnDuplicateProv = true) {}

  readonly precedence = HandlerPrecedence.SHARED;
  readonly name = InjectableDecoratorHandler.name;

  detect(node: ClassDeclaration, decorators: Decorator[]|null): DetectResult<Decorator>|undefined {
    if (!decorators) {
      return undefined;
    }
    const decorator = findAngularDecorator(decorators, 'Injectable', this.isCore);
    if (decorator !== undefined) {
      return {
        trigger: decorator.node,
        decorator: decorator,
        metadata: decorator,
      };
    } else {
      return undefined;
    }
  }

  analyze(node: ClassDeclaration, decorator: Readonly<Decorator>):
      AnalysisOutput<InjectableHandlerData> {
    const meta = extractInjectableMetadata(node, decorator, this.reflector);
    const decorators = this.reflector.getDecoratorsOfDeclaration(node);

    return {
      analysis: {
        meta,
        ctorDeps: extractInjectableCtorDeps(
            node, meta, decorator, this.reflector, this.defaultImportRecorder, this.isCore,
            this.strictCtorDeps),
        metadataStmt: generateSetClassMetadataCall(
            node, this.reflector, this.defaultImportRecorder, this.isCore),
        // Avoid generating multiple factories if a class has
        // more Angular decorators, apart from Injectable.
        needsFactory: !decorators ||
            decorators.every(current => !isAngularCore(current) || current.name === 'Injectable')
      },
    };
  }

  register(node: ClassDeclaration): void {
    this.injectableRegistry.registerInjectable(node);
  }

  compile(node: ClassDeclaration, analysis: Readonly<InjectableHandlerData>): CompileResult[] {
    const res = compileIvyInjectable(analysis.meta);
    const statements = res.statements;
    const results: CompileResult[] = [];

    if (analysis.needsFactory) {
      const meta = analysis.meta;
      const factoryRes = compileNgFactoryDefField({
        name: meta.name,
        type: meta.type,
        internalType: meta.internalType,
        typeArgumentCount: meta.typeArgumentCount,
        deps: analysis.ctorDeps,
        injectFn: Identifiers.inject,
        target: R3FactoryTarget.Injectable,
      });
      if (analysis.metadataStmt !== null) {
        factoryRes.statements.push(analysis.metadataStmt);
      }
      results.push(factoryRes);
    }

    const ɵprov = this.reflector.getMembersOfClass(node).find(member => member.name === 'ɵprov');
    if (ɵprov !== undefined && this.errorOnDuplicateProv) {
      throw new FatalDiagnosticError(
          ErrorCode.INJECTABLE_DUPLICATE_PROV, ɵprov.nameNode || ɵprov.node || node,
          'Injectables cannot contain a static ɵprov property, because the compiler is going to generate one.');
    }

    if (ɵprov === undefined) {
      // Only add a new ɵprov if there is not one already
      results.push({name: 'ɵprov', initializer: res.expression, statements, type: res.type});
    }


    return results;
  }
}

/**
 * Read metadata from the `@Injectable` decorator and produce the `IvyInjectableMetadata`, the
 * input metadata needed to run `compileIvyInjectable`.
 *
 * A `null` return value indicates this is @Injectable has invalid data.
 */
function extractInjectableMetadata(
    clazz: ClassDeclaration, decorator: Decorator,
    reflector: ReflectionHost): R3InjectableMetadata {
  const name = clazz.name.text;
  const type = wrapTypeReference(reflector, clazz);
  const internalType = new WrappedNodeExpr(reflector.getInternalNameOfClass(clazz));
  const typeArgumentCount = reflector.getGenericArityOfClass(clazz) || 0;
  if (decorator.args === null) {
    throw new FatalDiagnosticError(
        ErrorCode.DECORATOR_NOT_CALLED, Decorator.nodeForError(decorator),
        '@Injectable must be called');
  }
  if (decorator.args.length === 0) {
    return {
      name,
      type,
      typeArgumentCount,
      internalType,
      providedIn: new LiteralExpr(null),
    };
  } else if (decorator.args.length === 1) {
    const metaNode = decorator.args[0];
    // Firstly make sure the decorator argument is an inline literal - if not, it's illegal to
    // transport references from one location to another. This is the problem that lowering
    // used to solve - if this restriction proves too undesirable we can re-implement lowering.
    if (!ts.isObjectLiteralExpression(metaNode)) {
      throw new FatalDiagnosticError(
          ErrorCode.DECORATOR_ARG_NOT_LITERAL, metaNode,
          `@Injectable argument must be an object literal`);
    }

    // Resolve the fields of the literal into a map of field name to expression.
    const meta = reflectObjectLiteral(metaNode);
    let providedIn: Expression = new LiteralExpr(null);
    if (meta.has('providedIn')) {
      providedIn = new WrappedNodeExpr(meta.get('providedIn')!);
    }

    let userDeps: R3DependencyMetadata[]|undefined = undefined;
    if ((meta.has('useClass') || meta.has('useFactory')) && meta.has('deps')) {
      const depsExpr = meta.get('deps')!;
      if (!ts.isArrayLiteralExpression(depsExpr)) {
        throw new FatalDiagnosticError(
            ErrorCode.VALUE_NOT_LITERAL, depsExpr,
            `@Injectable deps metadata must be an inline array`);
      }
      userDeps = depsExpr.elements.map(dep => getDep(dep, reflector));
    }

    if (meta.has('useValue')) {
      return {
        name,
        type,
        typeArgumentCount,
        internalType,
        providedIn,
        useValue: new WrappedNodeExpr(unwrapForwardRef(meta.get('useValue')!, reflector)),
      };
    } else if (meta.has('useExisting')) {
      return {
        name,
        type,
        typeArgumentCount,
        internalType,
        providedIn,
        useExisting: new WrappedNodeExpr(unwrapForwardRef(meta.get('useExisting')!, reflector)),
      };
    } else if (meta.has('useClass')) {
      return {
        name,
        type,
        typeArgumentCount,
        internalType,
        providedIn,
        useClass: new WrappedNodeExpr(unwrapForwardRef(meta.get('useClass')!, reflector)),
        userDeps,
      };
    } else if (meta.has('useFactory')) {
      // useFactory is special - the 'deps' property must be analyzed.
      const factory = new WrappedNodeExpr(meta.get('useFactory')!);
      return {
        name,
        type,
        typeArgumentCount,
        internalType,
        providedIn,
        useFactory: factory,
        userDeps,
      };
    } else {
      return {name, type, typeArgumentCount, internalType, providedIn};
    }
  } else {
    throw new FatalDiagnosticError(
        ErrorCode.DECORATOR_ARITY_WRONG, decorator.args[2], 'Too many arguments to @Injectable');
  }
}

function extractInjectableCtorDeps(
    clazz: ClassDeclaration, meta: R3InjectableMetadata, decorator: Decorator,
    reflector: ReflectionHost, defaultImportRecorder: DefaultImportRecorder, isCore: boolean,
    strictCtorDeps: boolean) {
  if (decorator.args === null) {
    throw new FatalDiagnosticError(
        ErrorCode.DECORATOR_NOT_CALLED, Decorator.nodeForError(decorator),
        '@Injectable must be called');
  }

  let ctorDeps: R3DependencyMetadata[]|'invalid'|null = null;

  if (decorator.args.length === 0) {
    // Ideally, using @Injectable() would have the same effect as using @Injectable({...}), and be
    // subject to the same validation. However, existing Angular code abuses @Injectable, applying
    // it to things like abstract classes with constructors that were never meant for use with
    // Angular's DI.
    //
    // To deal with this, @Injectable() without an argument is more lenient, and if the
    // constructor signature does not work for DI then a factory definition (ɵfac) that throws is
    // generated.
    if (strictCtorDeps) {
      ctorDeps = getValidConstructorDependencies(clazz, reflector, defaultImportRecorder, isCore);
    } else {
      ctorDeps = unwrapConstructorDependencies(
          getConstructorDependencies(clazz, reflector, defaultImportRecorder, isCore));
    }

    return ctorDeps;
  } else if (decorator.args.length === 1) {
    const rawCtorDeps = getConstructorDependencies(clazz, reflector, defaultImportRecorder, isCore);

    if (strictCtorDeps && meta.useValue === undefined && meta.useExisting === undefined &&
        meta.useClass === undefined && meta.useFactory === undefined) {
      // Since use* was not provided, validate the deps according to strictCtorDeps.
      ctorDeps = validateConstructorDependencies(clazz, rawCtorDeps);
    } else {
      ctorDeps = unwrapConstructorDependencies(rawCtorDeps);
    }
  }

  return ctorDeps;
}

function getDep(dep: ts.Expression, reflector: ReflectionHost): R3DependencyMetadata {
  const meta: R3DependencyMetadata = {
    token: new WrappedNodeExpr(dep),
    attribute: null,
    host: false,
    resolved: R3ResolvedDependencyType.Token,
    optional: false,
    self: false,
    skipSelf: false,
  };

  function maybeUpdateDecorator(
      dec: ts.Identifier, reflector: ReflectionHost, token?: ts.Expression): void {
    const source = reflector.getImportOfIdentifier(dec);
    if (source === null || source.from !== '@angular/core') {
      return;
    }
    switch (source.name) {
      case 'Inject':
        if (token !== undefined) {
          meta.token = new WrappedNodeExpr(token);
        }
        break;
      case 'Optional':
        meta.optional = true;
        break;
      case 'SkipSelf':
        meta.skipSelf = true;
        break;
      case 'Self':
        meta.self = true;
        break;
    }
  }

  if (ts.isArrayLiteralExpression(dep)) {
    dep.elements.forEach(el => {
      if (ts.isIdentifier(el)) {
        maybeUpdateDecorator(el, reflector);
      } else if (ts.isNewExpression(el) && ts.isIdentifier(el.expression)) {
        const token = el.arguments && el.arguments.length > 0 && el.arguments[0] || undefined;
        maybeUpdateDecorator(el.expression, reflector, token);
      }
    });
  }
  return meta;
}
