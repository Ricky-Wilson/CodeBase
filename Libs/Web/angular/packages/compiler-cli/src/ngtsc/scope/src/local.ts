/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {ExternalExpr, SchemaMetadata} from '@angular/compiler';
import * as ts from 'typescript';

import {ErrorCode, makeDiagnostic, makeRelatedInformation} from '../../diagnostics';
import {AliasingHost, Reexport, Reference, ReferenceEmitter} from '../../imports';
import {DirectiveMeta, MetadataReader, MetadataRegistry, NgModuleMeta, PipeMeta} from '../../metadata';
import {ClassDeclaration} from '../../reflection';
import {identifierOfNode, nodeNameForError} from '../../util/src/typescript';

import {ExportScope, ScopeData} from './api';
import {ComponentScopeReader} from './component_scope';
import {DtsModuleScopeResolver} from './dependency';

export interface LocalNgModuleData {
  declarations: Reference<ClassDeclaration>[];
  imports: Reference<ClassDeclaration>[];
  exports: Reference<ClassDeclaration>[];
}

export interface LocalModuleScope extends ExportScope {
  compilation: ScopeData;
  reexports: Reexport[]|null;
  schemas: SchemaMetadata[];
}

/**
 * Information about the compilation scope of a registered declaration.
 */
export interface CompilationScope extends ScopeData {
  /** The declaration whose compilation scope is described here. */
  declaration: ClassDeclaration;
  /** The declaration of the NgModule that declares this `declaration`. */
  ngModule: ClassDeclaration;
}

/**
 * A registry which collects information about NgModules, Directives, Components, and Pipes which
 * are local (declared in the ts.Program being compiled), and can produce `LocalModuleScope`s
 * which summarize the compilation scope of a component.
 *
 * This class implements the logic of NgModule declarations, imports, and exports and can produce,
 * for a given component, the set of directives and pipes which are "visible" in that component's
 * template.
 *
 * The `LocalModuleScopeRegistry` has two "modes" of operation. During analysis, data for each
 * individual NgModule, Directive, Component, and Pipe is added to the registry. No attempt is made
 * to traverse or validate the NgModule graph (imports, exports, etc). After analysis, one of
 * `getScopeOfModule` or `getScopeForComponent` can be called, which traverses the NgModule graph
 * and applies the NgModule logic to generate a `LocalModuleScope`, the full scope for the given
 * module or component.
 *
 * The `LocalModuleScopeRegistry` is also capable of producing `ts.Diagnostic` errors when Angular
 * semantics are violated.
 */
export class LocalModuleScopeRegistry implements MetadataRegistry, ComponentScopeReader {
  /**
   * Tracks whether the registry has been asked to produce scopes for a module or component. Once
   * this is true, the registry cannot accept registrations of new directives/pipes/modules as it
   * would invalidate the cached scope data.
   */
  private sealed = false;

  /**
   * A map of components from the current compilation unit to the NgModule which declared them.
   *
   * As components and directives are not distinguished at the NgModule level, this map may also
   * contain directives. This doesn't cause any problems but isn't useful as there is no concept of
   * a directive's compilation scope.
   */
  private declarationToModule = new Map<ClassDeclaration, DeclarationData>();

  /**
   * This maps from the directive/pipe class to a map of data for each NgModule that declares the
   * directive/pipe. This data is needed to produce an error for the given class.
   */
  private duplicateDeclarations =
      new Map<ClassDeclaration, Map<ClassDeclaration, DeclarationData>>();

  private moduleToRef = new Map<ClassDeclaration, Reference<ClassDeclaration>>();

  /**
   * A cache of calculated `LocalModuleScope`s for each NgModule declared in the current program.
   *
   * A value of `undefined` indicates the scope was invalid and produced errors (therefore,
   * diagnostics should exist in the `scopeErrors` map).
   */
  private cache = new Map<ClassDeclaration, LocalModuleScope|undefined|null>();

  /**
   * Tracks whether a given component requires "remote scoping".
   *
   * Remote scoping is when the set of directives which apply to a given component is set in the
   * NgModule's file instead of directly on the component def (which is sometimes needed to get
   * around cyclic import issues). This is not used in calculation of `LocalModuleScope`s, but is
   * tracked here for convenience.
   */
  private remoteScoping = new Set<ClassDeclaration>();

  /**
   * Tracks errors accumulated in the processing of scopes for each module declaration.
   */
  private scopeErrors = new Map<ClassDeclaration, ts.Diagnostic[]>();

  /**
   * Tracks which NgModules are unreliable due to errors within their declarations.
   *
   * This provides a unified view of which modules have errors, across all of the different
   * diagnostic categories that can be produced. Theoretically this can be inferred from the other
   * properties of this class, but is tracked explicitly to simplify the logic.
   */
  private taintedModules = new Set<ClassDeclaration>();

  constructor(
      private localReader: MetadataReader, private dependencyScopeReader: DtsModuleScopeResolver,
      private refEmitter: ReferenceEmitter, private aliasingHost: AliasingHost|null) {}

  /**
   * Add an NgModule's data to the registry.
   */
  registerNgModuleMetadata(data: NgModuleMeta): void {
    this.assertCollecting();
    const ngModule = data.ref.node;
    this.moduleToRef.set(data.ref.node, data.ref);
    // Iterate over the module's declarations, and add them to declarationToModule. If duplicates
    // are found, they're instead tracked in duplicateDeclarations.
    for (const decl of data.declarations) {
      this.registerDeclarationOfModule(ngModule, decl, data.rawDeclarations);
    }
  }

  registerDirectiveMetadata(directive: DirectiveMeta): void {}

  registerPipeMetadata(pipe: PipeMeta): void {}

  getScopeForComponent(clazz: ClassDeclaration): LocalModuleScope|null|'error' {
    const scope = !this.declarationToModule.has(clazz) ?
        null :
        this.getScopeOfModule(this.declarationToModule.get(clazz)!.ngModule);
    return scope;
  }

  /**
   * If `node` is declared in more than one NgModule (duplicate declaration), then get the
   * `DeclarationData` for each offending declaration.
   *
   * Ordinarily a class is only declared in one NgModule, in which case this function returns
   * `null`.
   */
  getDuplicateDeclarations(node: ClassDeclaration): DeclarationData[]|null {
    if (!this.duplicateDeclarations.has(node)) {
      return null;
    }

    return Array.from(this.duplicateDeclarations.get(node)!.values());
  }

  /**
   * Collects registered data for a module and its directives/pipes and convert it into a full
   * `LocalModuleScope`.
   *
   * This method implements the logic of NgModule imports and exports. It returns the
   * `LocalModuleScope` for the given NgModule if one can be produced, `null` if no scope was ever
   * defined, or the string `'error'` if the scope contained errors.
   */
  getScopeOfModule(clazz: ClassDeclaration): LocalModuleScope|'error'|null {
    const scope = this.moduleToRef.has(clazz) ?
        this.getScopeOfModuleReference(this.moduleToRef.get(clazz)!) :
        null;
    // If the NgModule class is marked as tainted, consider it an error.
    if (this.taintedModules.has(clazz)) {
      return 'error';
    }

    // Translate undefined -> 'error'.
    return scope !== undefined ? scope : 'error';
  }

  /**
   * Retrieves any `ts.Diagnostic`s produced during the calculation of the `LocalModuleScope` for
   * the given NgModule, or `null` if no errors were present.
   */
  getDiagnosticsOfModule(clazz: ClassDeclaration): ts.Diagnostic[]|null {
    // Required to ensure the errors are populated for the given class. If it has been processed
    // before, this will be a no-op due to the scope cache.
    this.getScopeOfModule(clazz);

    if (this.scopeErrors.has(clazz)) {
      return this.scopeErrors.get(clazz)!;
    } else {
      return null;
    }
  }

  /**
   * Returns a collection of the compilation scope for each registered declaration.
   */
  getCompilationScopes(): CompilationScope[] {
    const scopes: CompilationScope[] = [];
    this.declarationToModule.forEach((declData, declaration) => {
      const scope = this.getScopeOfModule(declData.ngModule);
      if (scope !== null && scope !== 'error') {
        scopes.push({declaration, ngModule: declData.ngModule, ...scope.compilation});
      }
    });
    return scopes;
  }

  private registerDeclarationOfModule(
      ngModule: ClassDeclaration, decl: Reference<ClassDeclaration>,
      rawDeclarations: ts.Expression|null): void {
    const declData: DeclarationData = {
      ngModule,
      ref: decl,
      rawDeclarations,
    };

    // First, check for duplicate declarations of the same directive/pipe.
    if (this.duplicateDeclarations.has(decl.node)) {
      // This directive/pipe has already been identified as being duplicated. Add this module to the
      // map of modules for which a duplicate declaration exists.
      this.duplicateDeclarations.get(decl.node)!.set(ngModule, declData);
    } else if (
        this.declarationToModule.has(decl.node) &&
        this.declarationToModule.get(decl.node)!.ngModule !== ngModule) {
      // This directive/pipe is already registered as declared in another module. Mark it as a
      // duplicate instead.
      const duplicateDeclMap = new Map<ClassDeclaration, DeclarationData>();
      const firstDeclData = this.declarationToModule.get(decl.node)!;

      // Mark both modules as tainted, since their declarations are missing a component.
      this.taintedModules.add(firstDeclData.ngModule);
      this.taintedModules.add(ngModule);

      // Being detected as a duplicate means there are two NgModules (for now) which declare this
      // directive/pipe. Add both of them to the duplicate tracking map.
      duplicateDeclMap.set(firstDeclData.ngModule, firstDeclData);
      duplicateDeclMap.set(ngModule, declData);
      this.duplicateDeclarations.set(decl.node, duplicateDeclMap);

      // Remove the directive/pipe from `declarationToModule` as it's a duplicate declaration, and
      // therefore not valid.
      this.declarationToModule.delete(decl.node);
    } else {
      // This is the first declaration of this directive/pipe, so map it.
      this.declarationToModule.set(decl.node, declData);
    }
  }

  /**
   * Implementation of `getScopeOfModule` which accepts a reference to a class and differentiates
   * between:
   *
   * * no scope being available (returns `null`)
   * * a scope being produced with errors (returns `undefined`).
   */
  private getScopeOfModuleReference(ref: Reference<ClassDeclaration>): LocalModuleScope|null
      |undefined {
    if (this.cache.has(ref.node)) {
      return this.cache.get(ref.node);
    }

    // Seal the registry to protect the integrity of the `LocalModuleScope` cache.
    this.sealed = true;

    // `ref` should be an NgModule previously added to the registry. If not, a scope for it
    // cannot be produced.
    const ngModule = this.localReader.getNgModuleMetadata(ref);
    if (ngModule === null) {
      this.cache.set(ref.node, null);
      return null;
    }

    // Modules which contributed to the compilation scope of this module.
    const compilationModules = new Set<ClassDeclaration>([ngModule.ref.node]);
    // Modules which contributed to the export scope of this module.
    const exportedModules = new Set<ClassDeclaration>([ngModule.ref.node]);

    // Errors produced during computation of the scope are recorded here. At the end, if this array
    // isn't empty then `undefined` will be cached and returned to indicate this scope is invalid.
    const diagnostics: ts.Diagnostic[] = [];

    // At this point, the goal is to produce two distinct transitive sets:
    // - the directives and pipes which are visible to components declared in the NgModule.
    // - the directives and pipes which are exported to any NgModules which import this one.

    // Directives and pipes in the compilation scope.
    const compilationDirectives = new Map<ts.Declaration, DirectiveMeta>();
    const compilationPipes = new Map<ts.Declaration, PipeMeta>();

    const declared = new Set<ts.Declaration>();

    // Directives and pipes exported to any importing NgModules.
    const exportDirectives = new Map<ts.Declaration, DirectiveMeta>();
    const exportPipes = new Map<ts.Declaration, PipeMeta>();

    // The algorithm is as follows:
    // 1) Add all of the directives/pipes from each NgModule imported into the current one to the
    //    compilation scope.
    // 2) Add directives/pipes declared in the NgModule to the compilation scope. At this point, the
    //    compilation scope is complete.
    // 3) For each entry in the NgModule's exports:
    //    a) Attempt to resolve it as an NgModule with its own exported directives/pipes. If it is
    //       one, add them to the export scope of this NgModule.
    //    b) Otherwise, it should be a class in the compilation scope of this NgModule. If it is,
    //       add it to the export scope.
    //    c) If it's neither an NgModule nor a directive/pipe in the compilation scope, then this
    //       is an error.

    // 1) process imports.
    for (const decl of ngModule.imports) {
      const importScope = this.getExportedScope(decl, diagnostics, ref.node, 'import');
      if (importScope === null) {
        // An import wasn't an NgModule, so record an error.
        diagnostics.push(invalidRef(ref.node, decl, 'import'));
        continue;
      } else if (importScope === undefined) {
        // An import was an NgModule but contained errors of its own. Record this as an error too,
        // because this scope is always going to be incorrect if one of its imports could not be
        // read.
        diagnostics.push(invalidTransitiveNgModuleRef(ref.node, decl, 'import'));
        continue;
      }
      for (const directive of importScope.exported.directives) {
        compilationDirectives.set(directive.ref.node, directive);
      }
      for (const pipe of importScope.exported.pipes) {
        compilationPipes.set(pipe.ref.node, pipe);
      }
      for (const importedModule of importScope.exported.ngModules) {
        compilationModules.add(importedModule);
      }
    }

    // 2) add declarations.
    for (const decl of ngModule.declarations) {
      const directive = this.localReader.getDirectiveMetadata(decl);
      const pipe = this.localReader.getPipeMetadata(decl);
      if (directive !== null) {
        compilationDirectives.set(decl.node, {...directive, ref: decl});
      } else if (pipe !== null) {
        compilationPipes.set(decl.node, {...pipe, ref: decl});
      } else {
        this.taintedModules.add(ngModule.ref.node);

        const errorNode = decl.getOriginForDiagnostics(ngModule.rawDeclarations!);
        diagnostics.push(makeDiagnostic(
            ErrorCode.NGMODULE_INVALID_DECLARATION, errorNode,
            `The class '${decl.node.name.text}' is listed in the declarations ` +
                `of the NgModule '${
                    ngModule.ref.node.name
                        .text}', but is not a directive, a component, or a pipe. ` +
                `Either remove it from the NgModule's declarations, or add an appropriate Angular decorator.`,
            [makeRelatedInformation(
                decl.node.name, `'${decl.node.name.text}' is declared here.`)]));
        continue;
      }

      declared.add(decl.node);
    }

    // 3) process exports.
    // Exports can contain modules, components, or directives. They're processed differently.
    // Modules are straightforward. Directives and pipes from exported modules are added to the
    // export maps. Directives/pipes are different - they might be exports of declared types or
    // imported types.
    for (const decl of ngModule.exports) {
      // Attempt to resolve decl as an NgModule.
      const importScope = this.getExportedScope(decl, diagnostics, ref.node, 'export');
      if (importScope === undefined) {
        // An export was an NgModule but contained errors of its own. Record this as an error too,
        // because this scope is always going to be incorrect if one of its exports could not be
        // read.
        diagnostics.push(invalidTransitiveNgModuleRef(ref.node, decl, 'export'));
        continue;
      } else if (importScope !== null) {
        // decl is an NgModule.
        for (const directive of importScope.exported.directives) {
          exportDirectives.set(directive.ref.node, directive);
        }
        for (const pipe of importScope.exported.pipes) {
          exportPipes.set(pipe.ref.node, pipe);
        }
        for (const exportedModule of importScope.exported.ngModules) {
          exportedModules.add(exportedModule);
        }
      } else if (compilationDirectives.has(decl.node)) {
        // decl is a directive or component in the compilation scope of this NgModule.
        const directive = compilationDirectives.get(decl.node)!;
        exportDirectives.set(decl.node, directive);
      } else if (compilationPipes.has(decl.node)) {
        // decl is a pipe in the compilation scope of this NgModule.
        const pipe = compilationPipes.get(decl.node)!;
        exportPipes.set(decl.node, pipe);
      } else {
        // decl is an unknown export.
        if (this.localReader.getDirectiveMetadata(decl) !== null ||
            this.localReader.getPipeMetadata(decl) !== null) {
          diagnostics.push(invalidReexport(ref.node, decl));
        } else {
          diagnostics.push(invalidRef(ref.node, decl, 'export'));
        }
        continue;
      }
    }

    const exported = {
      directives: Array.from(exportDirectives.values()),
      pipes: Array.from(exportPipes.values()),
      ngModules: Array.from(exportedModules),
    };

    const reexports = this.getReexports(ngModule, ref, declared, exported, diagnostics);

    // Check if this scope had any errors during production.
    if (diagnostics.length > 0) {
      // Cache undefined, to mark the fact that the scope is invalid.
      this.cache.set(ref.node, undefined);

      // Save the errors for retrieval.
      this.scopeErrors.set(ref.node, diagnostics);

      // Mark this module as being tainted.
      this.taintedModules.add(ref.node);
      return undefined;
    }

    // Finally, produce the `LocalModuleScope` with both the compilation and export scopes.
    const scope = {
      compilation: {
        directives: Array.from(compilationDirectives.values()),
        pipes: Array.from(compilationPipes.values()),
        ngModules: Array.from(compilationModules),
      },
      exported,
      reexports,
      schemas: ngModule.schemas,
    };
    this.cache.set(ref.node, scope);
    return scope;
  }

  /**
   * Check whether a component requires remote scoping.
   */
  getRequiresRemoteScope(node: ClassDeclaration): boolean {
    return this.remoteScoping.has(node);
  }

  /**
   * Set a component as requiring remote scoping.
   */
  setComponentAsRequiringRemoteScoping(node: ClassDeclaration): void {
    this.remoteScoping.add(node);
  }

  /**
   * Look up the `ExportScope` of a given `Reference` to an NgModule.
   *
   * The NgModule in question may be declared locally in the current ts.Program, or it may be
   * declared in a .d.ts file.
   *
   * @returns `null` if no scope could be found, or `undefined` if an invalid scope
   * was found.
   *
   * May also contribute diagnostics of its own by adding to the given `diagnostics`
   * array parameter.
   */
  private getExportedScope(
      ref: Reference<ClassDeclaration>, diagnostics: ts.Diagnostic[],
      ownerForErrors: ts.Declaration, type: 'import'|'export'): ExportScope|null|undefined {
    if (ref.node.getSourceFile().isDeclarationFile) {
      // The NgModule is declared in a .d.ts file. Resolve it with the `DependencyScopeReader`.
      if (!ts.isClassDeclaration(ref.node)) {
        // The NgModule is in a .d.ts file but is not declared as a ts.ClassDeclaration. This is an
        // error in the .d.ts metadata.
        const code = type === 'import' ? ErrorCode.NGMODULE_INVALID_IMPORT :
                                         ErrorCode.NGMODULE_INVALID_EXPORT;
        diagnostics.push(makeDiagnostic(
            code, identifierOfNode(ref.node) || ref.node,
            `Appears in the NgModule.${type}s of ${
                nodeNameForError(ownerForErrors)}, but could not be resolved to an NgModule`));
        return undefined;
      }
      return this.dependencyScopeReader.resolve(ref);
    } else {
      // The NgModule is declared locally in the current program. Resolve it from the registry.
      return this.getScopeOfModuleReference(ref);
    }
  }

  private getReexports(
      ngModule: NgModuleMeta, ref: Reference<ClassDeclaration>, declared: Set<ts.Declaration>,
      exported: {directives: DirectiveMeta[], pipes: PipeMeta[]},
      diagnostics: ts.Diagnostic[]): Reexport[]|null {
    let reexports: Reexport[]|null = null;
    const sourceFile = ref.node.getSourceFile();
    if (this.aliasingHost === null) {
      return null;
    }
    reexports = [];
    // Track re-exports by symbol name, to produce diagnostics if two alias re-exports would share
    // the same name.
    const reexportMap = new Map<string, Reference<ClassDeclaration>>();
    // Alias ngModuleRef added for readability below.
    const ngModuleRef = ref;
    const addReexport = (exportRef: Reference<ClassDeclaration>) => {
      if (exportRef.node.getSourceFile() === sourceFile) {
        return;
      }
      const isReExport = !declared.has(exportRef.node);
      const exportName = this.aliasingHost!.maybeAliasSymbolAs(
          exportRef, sourceFile, ngModule.ref.node.name.text, isReExport);
      if (exportName === null) {
        return;
      }
      if (!reexportMap.has(exportName)) {
        if (exportRef.alias && exportRef.alias instanceof ExternalExpr) {
          reexports!.push({
            fromModule: exportRef.alias.value.moduleName!,
            symbolName: exportRef.alias.value.name!,
            asAlias: exportName,
          });
        } else {
          const expr = this.refEmitter.emit(exportRef.cloneWithNoIdentifiers(), sourceFile);
          if (!(expr instanceof ExternalExpr) || expr.value.moduleName === null ||
              expr.value.name === null) {
            throw new Error('Expected ExternalExpr');
          }
          reexports!.push({
            fromModule: expr.value.moduleName,
            symbolName: expr.value.name,
            asAlias: exportName,
          });
        }
        reexportMap.set(exportName, exportRef);
      } else {
        // Another re-export already used this name. Produce a diagnostic.
        const prevRef = reexportMap.get(exportName)!;
        diagnostics.push(reexportCollision(ngModuleRef.node, prevRef, exportRef));
      }
    };
    for (const {ref} of exported.directives) {
      addReexport(ref);
    }
    for (const {ref} of exported.pipes) {
      addReexport(ref);
    }
    return reexports;
  }

  private assertCollecting(): void {
    if (this.sealed) {
      throw new Error(`Assertion: LocalModuleScopeRegistry is not COLLECTING`);
    }
  }
}

/**
 * Produce a `ts.Diagnostic` for an invalid import or export from an NgModule.
 */
function invalidRef(
    clazz: ts.Declaration, decl: Reference<ts.Declaration>,
    type: 'import'|'export'): ts.Diagnostic {
  const code =
      type === 'import' ? ErrorCode.NGMODULE_INVALID_IMPORT : ErrorCode.NGMODULE_INVALID_EXPORT;
  const resolveTarget = type === 'import' ? 'NgModule' : 'NgModule, Component, Directive, or Pipe';
  let message =
      `Appears in the NgModule.${type}s of ${
          nodeNameForError(clazz)}, but could not be resolved to an ${resolveTarget} class.` +
      '\n\n';
  const library = decl.ownedByModuleGuess !== null ? ` (${decl.ownedByModuleGuess})` : '';
  const sf = decl.node.getSourceFile();

  // Provide extra context to the error for the user.
  if (!sf.isDeclarationFile) {
    // This is a file in the user's program.
    const annotationType = type === 'import' ? '@NgModule' : 'Angular';
    message += `Is it missing an ${annotationType} annotation?`;
  } else if (sf.fileName.indexOf('node_modules') !== -1) {
    // This file comes from a third-party library in node_modules.
    message +=
        `This likely means that the library${library} which declares ${decl.debugName} has not ` +
        'been processed correctly by ngcc, or is not compatible with Angular Ivy. Check if a ' +
        'newer version of the library is available, and update if so. Also consider checking ' +
        'with the library\'s authors to see if the library is expected to be compatible with Ivy.';
  } else {
    // This is a monorepo style local dependency. Unfortunately these are too different to really
    // offer much more advice than this.
    message += `This likely means that the dependency${library} which declares ${
        decl.debugName} has not been processed correctly by ngcc.`;
  }

  return makeDiagnostic(code, identifierOfNode(decl.node) || decl.node, message);
}

/**
 * Produce a `ts.Diagnostic` for an import or export which itself has errors.
 */
function invalidTransitiveNgModuleRef(
    clazz: ts.Declaration, decl: Reference<ts.Declaration>,
    type: 'import'|'export'): ts.Diagnostic {
  const code =
      type === 'import' ? ErrorCode.NGMODULE_INVALID_IMPORT : ErrorCode.NGMODULE_INVALID_EXPORT;
  return makeDiagnostic(
      code, identifierOfNode(decl.node) || decl.node,
      `Appears in the NgModule.${type}s of ${nodeNameForError(clazz)}, but itself has errors`);
}

/**
 * Produce a `ts.Diagnostic` for an exported directive or pipe which was not declared or imported
 * by the NgModule in question.
 */
function invalidReexport(clazz: ts.Declaration, decl: Reference<ts.Declaration>): ts.Diagnostic {
  return makeDiagnostic(
      ErrorCode.NGMODULE_INVALID_REEXPORT, identifierOfNode(decl.node) || decl.node,
      `Present in the NgModule.exports of ${
          nodeNameForError(clazz)} but neither declared nor imported`);
}

/**
 * Produce a `ts.Diagnostic` for a collision in re-export names between two directives/pipes.
 */
function reexportCollision(
    module: ClassDeclaration, refA: Reference<ClassDeclaration>,
    refB: Reference<ClassDeclaration>): ts.Diagnostic {
  const childMessageText = `This directive/pipe is part of the exports of '${
      module.name.text}' and shares the same name as another exported directive/pipe.`;
  return makeDiagnostic(
      ErrorCode.NGMODULE_REEXPORT_NAME_COLLISION, module.name,
      `
    There was a name collision between two classes named '${
          refA.node.name.text}', which are both part of the exports of '${module.name.text}'.

    Angular generates re-exports of an NgModule's exported directives/pipes from the module's source file in certain cases, using the declared name of the class. If two classes of the same name are exported, this automatic naming does not work.

    To fix this problem please re-export one or both classes directly from this file.
  `.trim(),
      [
        makeRelatedInformation(refA.node.name, childMessageText),
        makeRelatedInformation(refB.node.name, childMessageText),
      ]);
}

export interface DeclarationData {
  ngModule: ClassDeclaration;
  ref: Reference;
  rawDeclarations: ts.Expression|null;
}
