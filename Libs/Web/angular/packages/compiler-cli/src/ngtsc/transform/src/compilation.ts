/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {ConstantPool} from '@angular/compiler';
import * as ts from 'typescript';

import {ErrorCode, FatalDiagnosticError} from '../../diagnostics';
import {IncrementalBuild} from '../../incremental/api';
import {IndexingContext} from '../../indexer';
import {PerfRecorder} from '../../perf';
import {ClassDeclaration, Decorator, ReflectionHost} from '../../reflection';
import {ProgramTypeCheckAdapter, TypeCheckContext} from '../../typecheck';
import {getSourceFile, isExported} from '../../util/src/typescript';

import {AnalysisOutput, CompileResult, DecoratorHandler, HandlerFlags, HandlerPrecedence, ResolveResult} from './api';
import {DtsTransformRegistry} from './declaration';
import {PendingTrait, Trait, TraitState} from './trait';


/**
 * Records information about a specific class that has matched traits.
 */
export interface ClassRecord {
  /**
   * The `ClassDeclaration` of the class which has Angular traits applied.
   */
  node: ClassDeclaration;

  /**
   * All traits which matched on the class.
   */
  traits: Trait<unknown, unknown, unknown>[];

  /**
   * Meta-diagnostics about the class, which are usually related to whether certain combinations of
   * Angular decorators are not permitted.
   */
  metaDiagnostics: ts.Diagnostic[]|null;

  // Subsequent fields are "internal" and used during the matching of `DecoratorHandler`s. This is
  // mutable state during the `detect`/`analyze` phases of compilation.

  /**
   * Whether `traits` contains traits matched from `DecoratorHandler`s marked as `WEAK`.
   */
  hasWeakHandlers: boolean;

  /**
   * Whether `traits` contains a trait from a `DecoratorHandler` matched as `PRIMARY`.
   */
  hasPrimaryHandler: boolean;
}

/**
 * The heart of Angular compilation.
 *
 * The `TraitCompiler` is responsible for processing all classes in the program. Any time a
 * `DecoratorHandler` matches a class, a "trait" is created to represent that Angular aspect of the
 * class (such as the class having a component definition).
 *
 * The `TraitCompiler` transitions each trait through the various phases of compilation, culminating
 * in the production of `CompileResult`s instructing the compiler to apply various mutations to the
 * class (like adding fields or type declarations).
 */
export class TraitCompiler implements ProgramTypeCheckAdapter {
  /**
   * Maps class declarations to their `ClassRecord`, which tracks the Ivy traits being applied to
   * those classes.
   */
  private classes = new Map<ClassDeclaration, ClassRecord>();

  /**
   * Maps source files to any class declaration(s) within them which have been discovered to contain
   * Ivy traits.
   */
  protected fileToClasses = new Map<ts.SourceFile, Set<ClassDeclaration>>();

  private reexportMap = new Map<string, Map<string, [string, string]>>();

  private handlersByName = new Map<string, DecoratorHandler<unknown, unknown, unknown>>();

  constructor(
      private handlers: DecoratorHandler<unknown, unknown, unknown>[],
      private reflector: ReflectionHost, private perf: PerfRecorder,
      private incrementalBuild: IncrementalBuild<ClassRecord, unknown>,
      private compileNonExportedClasses: boolean, private dtsTransforms: DtsTransformRegistry) {
    for (const handler of handlers) {
      this.handlersByName.set(handler.name, handler);
    }
  }

  analyzeSync(sf: ts.SourceFile): void {
    this.analyze(sf, false);
  }

  analyzeAsync(sf: ts.SourceFile): Promise<void>|undefined {
    return this.analyze(sf, true);
  }

  private analyze(sf: ts.SourceFile, preanalyze: false): void;
  private analyze(sf: ts.SourceFile, preanalyze: true): Promise<void>|undefined;
  private analyze(sf: ts.SourceFile, preanalyze: boolean): Promise<void>|undefined {
    // We shouldn't analyze declaration files.
    if (sf.isDeclarationFile) {
      return undefined;
    }

    // analyze() really wants to return `Promise<void>|void`, but TypeScript cannot narrow a return
    // type of 'void', so `undefined` is used instead.
    const promises: Promise<void>[] = [];

    const priorWork = this.incrementalBuild.priorWorkFor(sf);
    if (priorWork !== null) {
      for (const priorRecord of priorWork) {
        this.adopt(priorRecord);
      }

      // Skip the rest of analysis, as this file's prior traits are being reused.
      return;
    }

    const visit = (node: ts.Node): void => {
      if (this.reflector.isClass(node)) {
        this.analyzeClass(node, preanalyze ? promises : null);
      }
      ts.forEachChild(node, visit);
    };

    visit(sf);

    if (preanalyze && promises.length > 0) {
      return Promise.all(promises).then(() => undefined as void);
    } else {
      return undefined;
    }
  }

  recordFor(clazz: ClassDeclaration): ClassRecord|null {
    if (this.classes.has(clazz)) {
      return this.classes.get(clazz)!;
    } else {
      return null;
    }
  }

  recordsFor(sf: ts.SourceFile): ClassRecord[]|null {
    if (!this.fileToClasses.has(sf)) {
      return null;
    }
    const records: ClassRecord[] = [];
    for (const clazz of this.fileToClasses.get(sf)!) {
      records.push(this.classes.get(clazz)!);
    }
    return records;
  }

  /**
   * Import a `ClassRecord` from a previous compilation.
   *
   * Traits from the `ClassRecord` have accurate metadata, but the `handler` is from the old program
   * and needs to be updated (matching is done by name). A new pending trait is created and then
   * transitioned to analyzed using the previous analysis. If the trait is in the errored state,
   * instead the errors are copied over.
   */
  private adopt(priorRecord: ClassRecord): void {
    const record: ClassRecord = {
      hasPrimaryHandler: priorRecord.hasPrimaryHandler,
      hasWeakHandlers: priorRecord.hasWeakHandlers,
      metaDiagnostics: priorRecord.metaDiagnostics,
      node: priorRecord.node,
      traits: [],
    };

    for (const priorTrait of priorRecord.traits) {
      const handler = this.handlersByName.get(priorTrait.handler.name)!;
      let trait: Trait<unknown, unknown, unknown> = Trait.pending(handler, priorTrait.detected);

      if (priorTrait.state === TraitState.ANALYZED || priorTrait.state === TraitState.RESOLVED) {
        trait = trait.toAnalyzed(priorTrait.analysis);
        if (trait.handler.register !== undefined) {
          trait.handler.register(record.node, trait.analysis);
        }
      } else if (priorTrait.state === TraitState.SKIPPED) {
        trait = trait.toSkipped();
      } else if (priorTrait.state === TraitState.ERRORED) {
        trait = trait.toErrored(priorTrait.diagnostics);
      }

      record.traits.push(trait);
    }

    this.classes.set(record.node, record);
    const sf = record.node.getSourceFile();
    if (!this.fileToClasses.has(sf)) {
      this.fileToClasses.set(sf, new Set<ClassDeclaration>());
    }
    this.fileToClasses.get(sf)!.add(record.node);
  }

  private scanClassForTraits(clazz: ClassDeclaration):
      PendingTrait<unknown, unknown, unknown>[]|null {
    if (!this.compileNonExportedClasses && !isExported(clazz)) {
      return null;
    }

    const decorators = this.reflector.getDecoratorsOfDeclaration(clazz);

    return this.detectTraits(clazz, decorators);
  }

  protected detectTraits(clazz: ClassDeclaration, decorators: Decorator[]|null):
      PendingTrait<unknown, unknown, unknown>[]|null {
    let record: ClassRecord|null = this.recordFor(clazz);
    let foundTraits: PendingTrait<unknown, unknown, unknown>[] = [];

    for (const handler of this.handlers) {
      const result = handler.detect(clazz, decorators);
      if (result === undefined) {
        continue;
      }

      const isPrimaryHandler = handler.precedence === HandlerPrecedence.PRIMARY;
      const isWeakHandler = handler.precedence === HandlerPrecedence.WEAK;
      const trait = Trait.pending(handler, result);

      foundTraits.push(trait);

      if (record === null) {
        // This is the first handler to match this class. This path is a fast path through which
        // most classes will flow.
        record = {
          node: clazz,
          traits: [trait],
          metaDiagnostics: null,
          hasPrimaryHandler: isPrimaryHandler,
          hasWeakHandlers: isWeakHandler,
        };

        this.classes.set(clazz, record);
        const sf = clazz.getSourceFile();
        if (!this.fileToClasses.has(sf)) {
          this.fileToClasses.set(sf, new Set<ClassDeclaration>());
        }
        this.fileToClasses.get(sf)!.add(clazz);
      } else {
        // This is at least the second handler to match this class. This is a slower path that some
        // classes will go through, which validates that the set of decorators applied to the class
        // is valid.

        // Validate according to rules as follows:
        //
        // * WEAK handlers are removed if a non-WEAK handler matches.
        // * Only one PRIMARY handler can match at a time. Any other PRIMARY handler matching a
        //   class with an existing PRIMARY handler is an error.

        if (!isWeakHandler && record.hasWeakHandlers) {
          // The current handler is not a WEAK handler, but the class has other WEAK handlers.
          // Remove them.
          record.traits =
              record.traits.filter(field => field.handler.precedence !== HandlerPrecedence.WEAK);
          record.hasWeakHandlers = false;
        } else if (isWeakHandler && !record.hasWeakHandlers) {
          // The current handler is a WEAK handler, but the class has non-WEAK handlers already.
          // Drop the current one.
          continue;
        }

        if (isPrimaryHandler && record.hasPrimaryHandler) {
          // The class already has a PRIMARY handler, and another one just matched.
          record.metaDiagnostics = [{
            category: ts.DiagnosticCategory.Error,
            code: Number('-99' + ErrorCode.DECORATOR_COLLISION),
            file: getSourceFile(clazz),
            start: clazz.getStart(undefined, false),
            length: clazz.getWidth(),
            messageText: 'Two incompatible decorators on class',
          }];
          record.traits = foundTraits = [];
          break;
        }

        // Otherwise, it's safe to accept the multiple decorators here. Update some of the metadata
        // regarding this class.
        record.traits.push(trait);
        record.hasPrimaryHandler = record.hasPrimaryHandler || isPrimaryHandler;
      }
    }

    return foundTraits.length > 0 ? foundTraits : null;
  }

  protected analyzeClass(clazz: ClassDeclaration, preanalyzeQueue: Promise<void>[]|null): void {
    const traits = this.scanClassForTraits(clazz);

    if (traits === null) {
      // There are no Ivy traits on the class, so it can safely be skipped.
      return;
    }

    for (const trait of traits) {
      const analyze = () => this.analyzeTrait(clazz, trait);

      let preanalysis: Promise<void>|null = null;
      if (preanalyzeQueue !== null && trait.handler.preanalyze !== undefined) {
        // Attempt to run preanalysis. This could fail with a `FatalDiagnosticError`; catch it if it
        // does.
        try {
          preanalysis = trait.handler.preanalyze(clazz, trait.detected.metadata) || null;
        } catch (err) {
          if (err instanceof FatalDiagnosticError) {
            trait.toErrored([err.toDiagnostic()]);
            return;
          } else {
            throw err;
          }
        }
      }
      if (preanalysis !== null) {
        preanalyzeQueue!.push(preanalysis.then(analyze));
      } else {
        analyze();
      }
    }
  }

  protected analyzeTrait(
      clazz: ClassDeclaration, trait: Trait<unknown, unknown, unknown>,
      flags?: HandlerFlags): void {
    if (trait.state !== TraitState.PENDING) {
      throw new Error(`Attempt to analyze trait of ${clazz.name.text} in state ${
          TraitState[trait.state]} (expected DETECTED)`);
    }

    // Attempt analysis. This could fail with a `FatalDiagnosticError`; catch it if it does.
    let result: AnalysisOutput<unknown>;
    try {
      result = trait.handler.analyze(clazz, trait.detected.metadata, flags);
    } catch (err) {
      if (err instanceof FatalDiagnosticError) {
        trait = trait.toErrored([err.toDiagnostic()]);
        return;
      } else {
        throw err;
      }
    }

    if (result.diagnostics !== undefined) {
      trait = trait.toErrored(result.diagnostics);
    } else if (result.analysis !== undefined) {
      // Analysis was successful. Trigger registration.
      if (trait.handler.register !== undefined) {
        trait.handler.register(clazz, result.analysis);
      }

      // Successfully analyzed and registered.
      trait = trait.toAnalyzed(result.analysis);
    } else {
      trait = trait.toSkipped();
    }
  }

  resolve(): void {
    const classes = Array.from(this.classes.keys());
    for (const clazz of classes) {
      const record = this.classes.get(clazz)!;
      for (let trait of record.traits) {
        const handler = trait.handler;
        switch (trait.state) {
          case TraitState.SKIPPED:
          case TraitState.ERRORED:
            continue;
          case TraitState.PENDING:
            throw new Error(`Resolving a trait that hasn't been analyzed: ${clazz.name.text} / ${
                Object.getPrototypeOf(trait.handler).constructor.name}`);
          case TraitState.RESOLVED:
            throw new Error(`Resolving an already resolved trait`);
        }

        if (handler.resolve === undefined) {
          // No resolution of this trait needed - it's considered successful by default.
          trait = trait.toResolved(null);
          continue;
        }

        let result: ResolveResult<unknown>;
        try {
          result = handler.resolve(clazz, trait.analysis as Readonly<unknown>);
        } catch (err) {
          if (err instanceof FatalDiagnosticError) {
            trait = trait.toErrored([err.toDiagnostic()]);
            continue;
          } else {
            throw err;
          }
        }

        if (result.diagnostics !== undefined && result.diagnostics.length > 0) {
          trait = trait.toErrored(result.diagnostics);
        } else {
          if (result.data !== undefined) {
            trait = trait.toResolved(result.data);
          } else {
            trait = trait.toResolved(null);
          }
        }

        if (result.reexports !== undefined) {
          const fileName = clazz.getSourceFile().fileName;
          if (!this.reexportMap.has(fileName)) {
            this.reexportMap.set(fileName, new Map<string, [string, string]>());
          }
          const fileReexports = this.reexportMap.get(fileName)!;
          for (const reexport of result.reexports) {
            fileReexports.set(reexport.asAlias, [reexport.fromModule, reexport.symbolName]);
          }
        }
      }
    }
  }

  /**
   * Generate type-checking code into the `TypeCheckContext` for any components within the given
   * `ts.SourceFile`.
   */
  typeCheck(sf: ts.SourceFile, ctx: TypeCheckContext): void {
    if (!this.fileToClasses.has(sf)) {
      return;
    }

    for (const clazz of this.fileToClasses.get(sf)!) {
      const record = this.classes.get(clazz)!;
      for (const trait of record.traits) {
        if (trait.state !== TraitState.RESOLVED) {
          continue;
        } else if (trait.handler.typeCheck === undefined) {
          continue;
        }
        trait.handler.typeCheck(ctx, clazz, trait.analysis, trait.resolution);
      }
    }
  }

  index(ctx: IndexingContext): void {
    for (const clazz of this.classes.keys()) {
      const record = this.classes.get(clazz)!;
      for (const trait of record.traits) {
        if (trait.state !== TraitState.RESOLVED) {
          // Skip traits that haven't been resolved successfully.
          continue;
        } else if (trait.handler.index === undefined) {
          // Skip traits that don't affect indexing.
          continue;
        }

        trait.handler.index(ctx, clazz, trait.analysis, trait.resolution);
      }
    }
  }

  compile(clazz: ts.Declaration, constantPool: ConstantPool): CompileResult[]|null {
    const original = ts.getOriginalNode(clazz) as typeof clazz;
    if (!this.reflector.isClass(clazz) || !this.reflector.isClass(original) ||
        !this.classes.has(original)) {
      return null;
    }

    const record = this.classes.get(original)!;

    let res: CompileResult[] = [];

    for (const trait of record.traits) {
      if (trait.state !== TraitState.RESOLVED) {
        continue;
      }

      const compileSpan = this.perf.start('compileClass', original);
      const compileMatchRes =
          trait.handler.compile(clazz, trait.analysis, trait.resolution, constantPool);
      this.perf.stop(compileSpan);
      if (Array.isArray(compileMatchRes)) {
        for (const result of compileMatchRes) {
          if (!res.some(r => r.name === result.name)) {
            res.push(result);
          }
        }
      } else if (!res.some(result => result.name === compileMatchRes.name)) {
        res.push(compileMatchRes);
      }
    }

    // Look up the .d.ts transformer for the input file and record that at least one field was
    // generated, which will allow the .d.ts to be transformed later.
    this.dtsTransforms.getIvyDeclarationTransform(original.getSourceFile())
        .addFields(original, res);

    // Return the instruction to the transformer so the fields will be added.
    return res.length > 0 ? res : null;
  }

  decoratorsFor(node: ts.Declaration): ts.Decorator[] {
    const original = ts.getOriginalNode(node) as typeof node;
    if (!this.reflector.isClass(original) || !this.classes.has(original)) {
      return [];
    }

    const record = this.classes.get(original)!;
    const decorators: ts.Decorator[] = [];

    for (const trait of record.traits) {
      if (trait.state !== TraitState.RESOLVED) {
        continue;
      }

      if (trait.detected.trigger !== null && ts.isDecorator(trait.detected.trigger)) {
        decorators.push(trait.detected.trigger);
      }
    }

    return decorators;
  }

  get diagnostics(): ReadonlyArray<ts.Diagnostic> {
    const diagnostics: ts.Diagnostic[] = [];
    for (const clazz of this.classes.keys()) {
      const record = this.classes.get(clazz)!;
      if (record.metaDiagnostics !== null) {
        diagnostics.push(...record.metaDiagnostics);
      }
      for (const trait of record.traits) {
        if (trait.state === TraitState.ERRORED) {
          diagnostics.push(...trait.diagnostics);
        }
      }
    }
    return diagnostics;
  }

  get exportStatements(): Map<string, Map<string, [string, string]>> {
    return this.reexportMap;
  }
}
