/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {Type} from '@angular/compiler';
import * as ts from 'typescript';

import {ComponentDecoratorHandler, DirectiveDecoratorHandler, InjectableDecoratorHandler, NgModuleDecoratorHandler, NoopReferencesRegistry, PipeDecoratorHandler, ReferencesRegistry} from '../../annotations';
import {CycleAnalyzer, ImportGraph} from '../../cycles';
import {ErrorCode, ngErrorCode} from '../../diagnostics';
import {checkForPrivateExports, ReferenceGraph} from '../../entry_point';
import {getSourceFileOrError, LogicalFileSystem} from '../../file_system';
import {AbsoluteModuleStrategy, AliasingHost, AliasStrategy, DefaultImportTracker, ImportRewriter, LocalIdentifierStrategy, LogicalProjectStrategy, ModuleResolver, NoopImportRewriter, PrivateExportAliasingHost, R3SymbolsImportRewriter, Reference, ReferenceEmitStrategy, ReferenceEmitter, RelativePathStrategy, UnifiedModulesAliasingHost, UnifiedModulesStrategy} from '../../imports';
import {IncrementalBuildStrategy, IncrementalDriver} from '../../incremental';
import {generateAnalysis, IndexedComponent, IndexingContext} from '../../indexer';
import {CompoundMetadataReader, CompoundMetadataRegistry, DtsMetadataReader, InjectableClassRegistry, LocalMetadataRegistry, MetadataReader} from '../../metadata';
import {ModuleWithProvidersScanner} from '../../modulewithproviders';
import {PartialEvaluator} from '../../partial_evaluator';
import {NOOP_PERF_RECORDER, PerfRecorder} from '../../perf';
import {TypeScriptReflectionHost} from '../../reflection';
import {AdapterResourceLoader} from '../../resource';
import {entryPointKeyFor, NgModuleRouteAnalyzer} from '../../routing';
import {ComponentScopeReader, LocalModuleScopeRegistry, MetadataDtsModuleScopeResolver} from '../../scope';
import {generatedFactoryTransform} from '../../shims';
import {ivySwitchTransform} from '../../switch';
import {aliasTransformFactory, declarationTransformFactory, DecoratorHandler, DtsTransformRegistry, ivyTransformFactory, TraitCompiler} from '../../transform';
import {isTemplateDiagnostic, TemplateTypeChecker, TypeCheckContext, TypeCheckingConfig, TypeCheckingProgramStrategy} from '../../typecheck';
import {getSourceFileOrNull, isDtsPath, resolveModuleName} from '../../util/src/typescript';
import {LazyRoute, NgCompilerAdapter, NgCompilerOptions} from '../api';

/**
 * State information about a compilation which is only generated once some data is requested from
 * the `NgCompiler` (for example, by calling `getDiagnostics`).
 */
interface LazyCompilationState {
  isCore: boolean;
  traitCompiler: TraitCompiler;
  reflector: TypeScriptReflectionHost;
  metaReader: MetadataReader;
  scopeRegistry: LocalModuleScopeRegistry;
  exportReferenceGraph: ReferenceGraph|null;
  routeAnalyzer: NgModuleRouteAnalyzer;
  dtsTransforms: DtsTransformRegistry;
  mwpScanner: ModuleWithProvidersScanner;
  defaultImportTracker: DefaultImportTracker;
  aliasingHost: AliasingHost|null;
  refEmitter: ReferenceEmitter;
  templateTypeChecker: TemplateTypeChecker;
}

/**
 * The heart of the Angular Ivy compiler.
 *
 * The `NgCompiler` provides an API for performing Angular compilation within a custom TypeScript
 * compiler. Each instance of `NgCompiler` supports a single compilation, which might be
 * incremental.
 *
 * `NgCompiler` is lazy, and does not perform any of the work of the compilation until one of its
 * output methods (e.g. `getDiagnostics`) is called.
 *
 * See the README.md for more information.
 */
export class NgCompiler {
  /**
   * Lazily evaluated state of the compilation.
   *
   * This is created on demand by calling `ensureAnalyzed`.
   */
  private compilation: LazyCompilationState|null = null;

  /**
   * Any diagnostics related to the construction of the compilation.
   *
   * These are diagnostics which arose during setup of the host and/or program.
   */
  private constructionDiagnostics: ts.Diagnostic[] = [];

  /**
   * Semantic diagnostics related to the program itself.
   *
   * This is set by (and memoizes) `getDiagnostics`.
   */
  private diagnostics: ts.Diagnostic[]|null = null;

  private closureCompilerEnabled: boolean;
  private nextProgram: ts.Program;
  private entryPoint: ts.SourceFile|null;
  private moduleResolver: ModuleResolver;
  private resourceManager: AdapterResourceLoader;
  private cycleAnalyzer: CycleAnalyzer;
  readonly incrementalDriver: IncrementalDriver;
  readonly ignoreForDiagnostics: Set<ts.SourceFile>;
  readonly ignoreForEmit: Set<ts.SourceFile>;

  constructor(
      private adapter: NgCompilerAdapter, private options: NgCompilerOptions,
      private tsProgram: ts.Program,
      private typeCheckingProgramStrategy: TypeCheckingProgramStrategy,
      private incrementalStrategy: IncrementalBuildStrategy, oldProgram: ts.Program|null = null,
      private perfRecorder: PerfRecorder = NOOP_PERF_RECORDER) {
    this.constructionDiagnostics.push(...this.adapter.constructionDiagnostics);
    const incompatibleTypeCheckOptionsDiagnostic = verifyCompatibleTypeCheckOptions(this.options);
    if (incompatibleTypeCheckOptionsDiagnostic !== null) {
      this.constructionDiagnostics.push(incompatibleTypeCheckOptionsDiagnostic);
    }

    this.nextProgram = tsProgram;
    this.closureCompilerEnabled = !!this.options.annotateForClosureCompiler;

    this.entryPoint =
        adapter.entryPoint !== null ? getSourceFileOrNull(tsProgram, adapter.entryPoint) : null;

    const moduleResolutionCache = ts.createModuleResolutionCache(
        this.adapter.getCurrentDirectory(),
        fileName => this.adapter.getCanonicalFileName(fileName));
    this.moduleResolver =
        new ModuleResolver(tsProgram, this.options, this.adapter, moduleResolutionCache);
    this.resourceManager = new AdapterResourceLoader(adapter, this.options);
    this.cycleAnalyzer = new CycleAnalyzer(new ImportGraph(this.moduleResolver));

    let modifiedResourceFiles: Set<string>|null = null;
    if (this.adapter.getModifiedResourceFiles !== undefined) {
      modifiedResourceFiles = this.adapter.getModifiedResourceFiles() || null;
    }

    if (oldProgram === null) {
      this.incrementalDriver = IncrementalDriver.fresh(tsProgram);
    } else {
      const oldDriver = this.incrementalStrategy.getIncrementalDriver(oldProgram);
      if (oldDriver !== null) {
        this.incrementalDriver =
            IncrementalDriver.reconcile(oldProgram, oldDriver, tsProgram, modifiedResourceFiles);
      } else {
        // A previous ts.Program was used to create the current one, but it wasn't from an
        // `NgCompiler`. That doesn't hurt anything, but the Angular analysis will have to start
        // from a fresh state.
        this.incrementalDriver = IncrementalDriver.fresh(tsProgram);
      }
    }
    this.incrementalStrategy.setIncrementalDriver(this.incrementalDriver, tsProgram);

    this.ignoreForDiagnostics =
        new Set(tsProgram.getSourceFiles().filter(sf => this.adapter.isShim(sf)));

    this.ignoreForEmit = this.adapter.ignoreForEmit;
  }

  /**
   * Get all Angular-related diagnostics for this compilation.
   *
   * If a `ts.SourceFile` is passed, only diagnostics related to that file are returned.
   */
  getDiagnostics(file?: ts.SourceFile): ts.Diagnostic[] {
    if (this.diagnostics === null) {
      const compilation = this.ensureAnalyzed();
      this.diagnostics =
          [...compilation.traitCompiler.diagnostics, ...this.getTemplateDiagnostics()];
      if (this.entryPoint !== null && compilation.exportReferenceGraph !== null) {
        this.diagnostics.push(...checkForPrivateExports(
            this.entryPoint, this.tsProgram.getTypeChecker(), compilation.exportReferenceGraph));
      }
    }

    if (file === undefined) {
      return this.diagnostics;
    } else {
      return this.diagnostics.filter(diag => {
        if (diag.file === file) {
          return true;
        } else if (isTemplateDiagnostic(diag) && diag.componentFile === file) {
          // Template diagnostics are reported when diagnostics for the component file are
          // requested (since no consumer of `getDiagnostics` would ever ask for diagnostics from
          // the fake ts.SourceFile for templates).
          return true;
        } else {
          return false;
        }
      });
    }
  }

  /**
   * Get all setup-related diagnostics for this compilation.
   */
  getOptionDiagnostics(): ts.Diagnostic[] {
    return this.constructionDiagnostics;
  }

  /**
   * Get the `ts.Program` to use as a starting point when spawning a subsequent incremental
   * compilation.
   *
   * The `NgCompiler` spawns an internal incremental TypeScript compilation (inheriting the
   * consumer's `ts.Program` into a new one for the purposes of template type-checking). After this
   * operation, the consumer's `ts.Program` is no longer usable for starting a new incremental
   * compilation. `getNextProgram` retrieves the `ts.Program` which can be used instead.
   */
  getNextProgram(): ts.Program {
    return this.nextProgram;
  }

  /**
   * Perform Angular's analysis step (as a precursor to `getDiagnostics` or `prepareEmit`)
   * asynchronously.
   *
   * Normally, this operation happens lazily whenever `getDiagnostics` or `prepareEmit` are called.
   * However, certain consumers may wish to allow for an asynchronous phase of analysis, where
   * resources such as `styleUrls` are resolved asynchonously. In these cases `analyzeAsync` must be
   * called first, and its `Promise` awaited prior to calling any other APIs of `NgCompiler`.
   */
  async analyzeAsync(): Promise<void> {
    if (this.compilation !== null) {
      return;
    }
    this.compilation = this.makeCompilation();

    const analyzeSpan = this.perfRecorder.start('analyze');
    const promises: Promise<void>[] = [];
    for (const sf of this.tsProgram.getSourceFiles()) {
      if (sf.isDeclarationFile) {
        continue;
      }

      const analyzeFileSpan = this.perfRecorder.start('analyzeFile', sf);
      let analysisPromise = this.compilation.traitCompiler.analyzeAsync(sf);
      this.scanForMwp(sf);
      if (analysisPromise === undefined) {
        this.perfRecorder.stop(analyzeFileSpan);
      } else if (this.perfRecorder.enabled) {
        analysisPromise = analysisPromise.then(() => this.perfRecorder.stop(analyzeFileSpan));
      }
      if (analysisPromise !== undefined) {
        promises.push(analysisPromise);
      }
    }

    await Promise.all(promises);

    this.perfRecorder.stop(analyzeSpan);

    this.resolveCompilation(this.compilation.traitCompiler);
  }

  /**
   * List lazy routes detected during analysis.
   *
   * This can be called for one specific route, or to retrieve all top-level routes.
   */
  listLazyRoutes(entryRoute?: string): LazyRoute[] {
    if (entryRoute) {
      // Note:
      // This resolution step is here to match the implementation of the old `AotCompilerHost` (see
      // https://github.com/angular/angular/blob/50732e156/packages/compiler-cli/src/transformers/compiler_host.ts#L175-L188).
      //
      // `@angular/cli` will always call this API with an absolute path, so the resolution step is
      // not necessary, but keeping it backwards compatible in case someone else is using the API.

      // Relative entry paths are disallowed.
      if (entryRoute.startsWith('.')) {
        throw new Error(`Failed to list lazy routes: Resolution of relative paths (${
            entryRoute}) is not supported.`);
      }

      // Non-relative entry paths fall into one of the following categories:
      // - Absolute system paths (e.g. `/foo/bar/my-project/my-module`), which are unaffected by the
      //   logic below.
      // - Paths to enternal modules (e.g. `some-lib`).
      // - Paths mapped to directories in `tsconfig.json` (e.g. `shared/my-module`).
      //   (See https://www.typescriptlang.org/docs/handbook/module-resolution.html#path-mapping.)
      //
      // In all cases above, the `containingFile` argument is ignored, so we can just take the first
      // of the root files.
      const containingFile = this.tsProgram.getRootFileNames()[0];
      const [entryPath, moduleName] = entryRoute.split('#');
      const resolvedModule =
          resolveModuleName(entryPath, containingFile, this.options, this.adapter, null);

      if (resolvedModule) {
        entryRoute = entryPointKeyFor(resolvedModule.resolvedFileName, moduleName);
      }
    }

    const compilation = this.ensureAnalyzed();
    return compilation.routeAnalyzer.listLazyRoutes(entryRoute);
  }

  /**
   * Fetch transformers and other information which is necessary for a consumer to `emit` the
   * program with Angular-added definitions.
   */
  prepareEmit(): {
    transformers: ts.CustomTransformers,
  } {
    const compilation = this.ensureAnalyzed();

    const coreImportsFrom = compilation.isCore ? getR3SymbolsFile(this.tsProgram) : null;
    let importRewriter: ImportRewriter;
    if (coreImportsFrom !== null) {
      importRewriter = new R3SymbolsImportRewriter(coreImportsFrom.fileName);
    } else {
      importRewriter = new NoopImportRewriter();
    }

    const before = [
      ivyTransformFactory(
          compilation.traitCompiler, compilation.reflector, importRewriter,
          compilation.defaultImportTracker, compilation.isCore, this.closureCompilerEnabled),
      aliasTransformFactory(compilation.traitCompiler.exportStatements),
      compilation.defaultImportTracker.importPreservingTransformer(),
    ];

    const afterDeclarations: ts.TransformerFactory<ts.SourceFile>[] = [];
    if (compilation.dtsTransforms !== null) {
      afterDeclarations.push(
          declarationTransformFactory(compilation.dtsTransforms, importRewriter));
    }

    // Only add aliasing re-exports to the .d.ts output if the `AliasingHost` requests it.
    if (compilation.aliasingHost !== null && compilation.aliasingHost.aliasExportsInDts) {
      afterDeclarations.push(aliasTransformFactory(compilation.traitCompiler.exportStatements));
    }

    if (this.adapter.factoryTracker !== null) {
      before.push(
          generatedFactoryTransform(this.adapter.factoryTracker.sourceInfo, importRewriter));
    }
    before.push(ivySwitchTransform);

    return {transformers: {before, afterDeclarations} as ts.CustomTransformers};
  }

  /**
   * Run the indexing process and return a `Map` of all indexed components.
   *
   * See the `indexing` package for more details.
   */
  getIndexedComponents(): Map<ts.Declaration, IndexedComponent> {
    const compilation = this.ensureAnalyzed();
    const context = new IndexingContext();
    compilation.traitCompiler.index(context);
    return generateAnalysis(context);
  }

  private ensureAnalyzed(this: NgCompiler): LazyCompilationState {
    if (this.compilation === null) {
      this.analyzeSync();
    }
    return this.compilation!;
  }

  private analyzeSync(): void {
    const analyzeSpan = this.perfRecorder.start('analyze');
    this.compilation = this.makeCompilation();
    for (const sf of this.tsProgram.getSourceFiles()) {
      if (sf.isDeclarationFile) {
        continue;
      }
      const analyzeFileSpan = this.perfRecorder.start('analyzeFile', sf);
      this.compilation.traitCompiler.analyzeSync(sf);
      this.scanForMwp(sf);
      this.perfRecorder.stop(analyzeFileSpan);
    }
    this.perfRecorder.stop(analyzeSpan);

    this.resolveCompilation(this.compilation.traitCompiler);
  }

  private resolveCompilation(traitCompiler: TraitCompiler): void {
    traitCompiler.resolve();

    this.recordNgModuleScopeDependencies();

    // At this point, analysis is complete and the compiler can now calculate which files need to
    // be emitted, so do that.
    this.incrementalDriver.recordSuccessfulAnalysis(traitCompiler);
  }

  private get fullTemplateTypeCheck(): boolean {
    // Determine the strictness level of type checking based on compiler options. As
    // `strictTemplates` is a superset of `fullTemplateTypeCheck`, the former implies the latter.
    // Also see `verifyCompatibleTypeCheckOptions` where it is verified that `fullTemplateTypeCheck`
    // is not disabled when `strictTemplates` is enabled.
    const strictTemplates = !!this.options.strictTemplates;
    return strictTemplates || !!this.options.fullTemplateTypeCheck;
  }

  private getTypeCheckingConfig(): TypeCheckingConfig {
    // Determine the strictness level of type checking based on compiler options. As
    // `strictTemplates` is a superset of `fullTemplateTypeCheck`, the former implies the latter.
    // Also see `verifyCompatibleTypeCheckOptions` where it is verified that `fullTemplateTypeCheck`
    // is not disabled when `strictTemplates` is enabled.
    const strictTemplates = !!this.options.strictTemplates;

    // First select a type-checking configuration, based on whether full template type-checking is
    // requested.
    let typeCheckingConfig: TypeCheckingConfig;
    if (this.fullTemplateTypeCheck) {
      typeCheckingConfig = {
        applyTemplateContextGuards: strictTemplates,
        checkQueries: false,
        checkTemplateBodies: true,
        checkTypeOfInputBindings: strictTemplates,
        strictNullInputBindings: strictTemplates,
        checkTypeOfAttributes: strictTemplates,
        // Even in full template type-checking mode, DOM binding checks are not quite ready yet.
        checkTypeOfDomBindings: false,
        checkTypeOfOutputEvents: strictTemplates,
        checkTypeOfAnimationEvents: strictTemplates,
        // Checking of DOM events currently has an adverse effect on developer experience,
        // e.g. for `<input (blur)="update($event.target.value)">` enabling this check results in:
        // - error TS2531: Object is possibly 'null'.
        // - error TS2339: Property 'value' does not exist on type 'EventTarget'.
        checkTypeOfDomEvents: strictTemplates,
        checkTypeOfDomReferences: strictTemplates,
        // Non-DOM references have the correct type in View Engine so there is no strictness flag.
        checkTypeOfNonDomReferences: true,
        // Pipes are checked in View Engine so there is no strictness flag.
        checkTypeOfPipes: true,
        strictSafeNavigationTypes: strictTemplates,
        useContextGenericType: strictTemplates,
        strictLiteralTypes: true,
      };
    } else {
      typeCheckingConfig = {
        applyTemplateContextGuards: false,
        checkQueries: false,
        checkTemplateBodies: false,
        checkTypeOfInputBindings: false,
        strictNullInputBindings: false,
        checkTypeOfAttributes: false,
        checkTypeOfDomBindings: false,
        checkTypeOfOutputEvents: false,
        checkTypeOfAnimationEvents: false,
        checkTypeOfDomEvents: false,
        checkTypeOfDomReferences: false,
        checkTypeOfNonDomReferences: false,
        checkTypeOfPipes: false,
        strictSafeNavigationTypes: false,
        useContextGenericType: false,
        strictLiteralTypes: false,
      };
    }

    // Apply explicitly configured strictness flags on top of the default configuration
    // based on "fullTemplateTypeCheck".
    if (this.options.strictInputTypes !== undefined) {
      typeCheckingConfig.checkTypeOfInputBindings = this.options.strictInputTypes;
      typeCheckingConfig.applyTemplateContextGuards = this.options.strictInputTypes;
    }
    if (this.options.strictNullInputTypes !== undefined) {
      typeCheckingConfig.strictNullInputBindings = this.options.strictNullInputTypes;
    }
    if (this.options.strictOutputEventTypes !== undefined) {
      typeCheckingConfig.checkTypeOfOutputEvents = this.options.strictOutputEventTypes;
      typeCheckingConfig.checkTypeOfAnimationEvents = this.options.strictOutputEventTypes;
    }
    if (this.options.strictDomEventTypes !== undefined) {
      typeCheckingConfig.checkTypeOfDomEvents = this.options.strictDomEventTypes;
    }
    if (this.options.strictSafeNavigationTypes !== undefined) {
      typeCheckingConfig.strictSafeNavigationTypes = this.options.strictSafeNavigationTypes;
    }
    if (this.options.strictDomLocalRefTypes !== undefined) {
      typeCheckingConfig.checkTypeOfDomReferences = this.options.strictDomLocalRefTypes;
    }
    if (this.options.strictAttributeTypes !== undefined) {
      typeCheckingConfig.checkTypeOfAttributes = this.options.strictAttributeTypes;
    }
    if (this.options.strictContextGenerics !== undefined) {
      typeCheckingConfig.useContextGenericType = this.options.strictContextGenerics;
    }
    if (this.options.strictLiteralTypes !== undefined) {
      typeCheckingConfig.strictLiteralTypes = this.options.strictLiteralTypes;
    }

    return typeCheckingConfig;
  }

  private getTemplateDiagnostics(): ReadonlyArray<ts.Diagnostic> {
    // Skip template type-checking if it's disabled.
    if (this.options.ivyTemplateTypeCheck === false && !this.fullTemplateTypeCheck) {
      return [];
    }

    const compilation = this.ensureAnalyzed();

    // Execute the typeCheck phase of each decorator in the program.
    const prepSpan = this.perfRecorder.start('typeCheckPrep');
    const results = compilation.templateTypeChecker.refresh();
    this.incrementalDriver.recordSuccessfulTypeCheck(results.perFileData);
    this.perfRecorder.stop(prepSpan);

    // Get the diagnostics.
    const typeCheckSpan = this.perfRecorder.start('typeCheckDiagnostics');
    const diagnostics: ts.Diagnostic[] = [];
    for (const sf of this.tsProgram.getSourceFiles()) {
      if (sf.isDeclarationFile || this.adapter.isShim(sf)) {
        continue;
      }

      diagnostics.push(...compilation.templateTypeChecker.getDiagnosticsForFile(sf));
    }

    const program = this.typeCheckingProgramStrategy.getProgram();
    this.perfRecorder.stop(typeCheckSpan);
    this.incrementalStrategy.setIncrementalDriver(this.incrementalDriver, program);
    this.nextProgram = program;

    return diagnostics;
  }

  /**
   * Reifies the inter-dependencies of NgModules and the components within their compilation scopes
   * into the `IncrementalDriver`'s dependency graph.
   */
  private recordNgModuleScopeDependencies() {
    const recordSpan = this.perfRecorder.start('recordDependencies');
    const depGraph = this.incrementalDriver.depGraph;

    for (const scope of this.compilation!.scopeRegistry!.getCompilationScopes()) {
      const file = scope.declaration.getSourceFile();
      const ngModuleFile = scope.ngModule.getSourceFile();

      // A change to any dependency of the declaration causes the declaration to be invalidated,
      // which requires the NgModule to be invalidated as well.
      depGraph.addTransitiveDependency(ngModuleFile, file);

      // A change to the NgModule file should cause the declaration itself to be invalidated.
      depGraph.addDependency(file, ngModuleFile);

      const meta =
          this.compilation!.metaReader.getDirectiveMetadata(new Reference(scope.declaration));
      if (meta !== null && meta.isComponent) {
        // If a component's template changes, it might have affected the import graph, and thus the
        // remote scoping feature which is activated in the event of potential import cycles. Thus,
        // the module depends not only on the transitive dependencies of the component, but on its
        // resources as well.
        depGraph.addTransitiveResources(ngModuleFile, file);

        // A change to any directive/pipe in the compilation scope should cause the component to be
        // invalidated.
        for (const directive of scope.directives) {
          // When a directive in scope is updated, the component needs to be recompiled as e.g. a
          // selector may have changed.
          depGraph.addTransitiveDependency(file, directive.ref.node.getSourceFile());
        }
        for (const pipe of scope.pipes) {
          // When a pipe in scope is updated, the component needs to be recompiled as e.g. the
          // pipe's name may have changed.
          depGraph.addTransitiveDependency(file, pipe.ref.node.getSourceFile());
        }

        // Components depend on the entire export scope. In addition to transitive dependencies on
        // all directives/pipes in the export scope, they also depend on every NgModule in the
        // scope, as changes to a module may add new directives/pipes to the scope.
        for (const depModule of scope.ngModules) {
          // There is a correctness issue here. To be correct, this should be a transitive
          // dependency on the depModule file, since the depModule's exports might change via one of
          // its dependencies, even if depModule's file itself doesn't change. However, doing this
          // would also trigger recompilation if a non-exported component or directive changed,
          // which causes performance issues for rebuilds.
          //
          // Given the rebuild issue is an edge case, currently we err on the side of performance
          // instead of correctness. A correct and performant design would distinguish between
          // changes to the depModule which affect its export scope and changes which do not, and
          // only add a dependency for the former. This concept is currently in development.
          //
          // TODO(alxhub): fix correctness issue by understanding the semantics of the dependency.
          depGraph.addDependency(file, depModule.getSourceFile());
        }
      } else {
        // Directives (not components) and pipes only depend on the NgModule which directly declares
        // them.
        depGraph.addDependency(file, ngModuleFile);
      }
    }
    this.perfRecorder.stop(recordSpan);
  }

  private scanForMwp(sf: ts.SourceFile): void {
    this.compilation!.mwpScanner.scan(sf, {
      addTypeReplacement: (node: ts.Declaration, type: Type): void => {
        // Only obtain the return type transform for the source file once there's a type to replace,
        // so that no transform is allocated when there's nothing to do.
        this.compilation!.dtsTransforms!.getReturnTypeTransform(sf).addTypeReplacement(node, type);
      }
    });
  }

  private makeCompilation(): LazyCompilationState {
    const checker = this.tsProgram.getTypeChecker();

    const reflector = new TypeScriptReflectionHost(checker);

    // Construct the ReferenceEmitter.
    let refEmitter: ReferenceEmitter;
    let aliasingHost: AliasingHost|null = null;
    if (this.adapter.unifiedModulesHost === null || !this.options._useHostForImportGeneration) {
      let localImportStrategy: ReferenceEmitStrategy;

      // The strategy used for local, in-project imports depends on whether TS has been configured
      // with rootDirs. If so, then multiple directories may be mapped in the same "module
      // namespace" and the logic of `LogicalProjectStrategy` is required to generate correct
      // imports which may cross these multiple directories. Otherwise, plain relative imports are
      // sufficient.
      if (this.options.rootDir !== undefined ||
          (this.options.rootDirs !== undefined && this.options.rootDirs.length > 0)) {
        // rootDirs logic is in effect - use the `LogicalProjectStrategy` for in-project relative
        // imports.
        localImportStrategy = new LogicalProjectStrategy(
            reflector, new LogicalFileSystem([...this.adapter.rootDirs], this.adapter));
      } else {
        // Plain relative imports are all that's needed.
        localImportStrategy = new RelativePathStrategy(reflector);
      }

      // The CompilerHost doesn't have fileNameToModuleName, so build an NPM-centric reference
      // resolution strategy.
      refEmitter = new ReferenceEmitter([
        // First, try to use local identifiers if available.
        new LocalIdentifierStrategy(),
        // Next, attempt to use an absolute import.
        new AbsoluteModuleStrategy(this.tsProgram, checker, this.moduleResolver, reflector),
        // Finally, check if the reference is being written into a file within the project's .ts
        // sources, and use a relative import if so. If this fails, ReferenceEmitter will throw
        // an error.
        localImportStrategy,
      ]);

      // If an entrypoint is present, then all user imports should be directed through the
      // entrypoint and private exports are not needed. The compiler will validate that all publicly
      // visible directives/pipes are importable via this entrypoint.
      if (this.entryPoint === null && this.options.generateDeepReexports === true) {
        // No entrypoint is present and deep re-exports were requested, so configure the aliasing
        // system to generate them.
        aliasingHost = new PrivateExportAliasingHost(reflector);
      }
    } else {
      // The CompilerHost supports fileNameToModuleName, so use that to emit imports.
      refEmitter = new ReferenceEmitter([
        // First, try to use local identifiers if available.
        new LocalIdentifierStrategy(),
        // Then use aliased references (this is a workaround to StrictDeps checks).
        new AliasStrategy(),
        // Then use fileNameToModuleName to emit imports.
        new UnifiedModulesStrategy(reflector, this.adapter.unifiedModulesHost),
      ]);
      aliasingHost = new UnifiedModulesAliasingHost(this.adapter.unifiedModulesHost);
    }

    const evaluator = new PartialEvaluator(reflector, checker, this.incrementalDriver.depGraph);
    const dtsReader = new DtsMetadataReader(checker, reflector);
    const localMetaRegistry = new LocalMetadataRegistry();
    const localMetaReader: MetadataReader = localMetaRegistry;
    const depScopeReader = new MetadataDtsModuleScopeResolver(dtsReader, aliasingHost);
    const scopeRegistry =
        new LocalModuleScopeRegistry(localMetaReader, depScopeReader, refEmitter, aliasingHost);
    const scopeReader: ComponentScopeReader = scopeRegistry;
    const metaRegistry = new CompoundMetadataRegistry([localMetaRegistry, scopeRegistry]);
    const injectableRegistry = new InjectableClassRegistry(reflector);

    const metaReader = new CompoundMetadataReader([localMetaReader, dtsReader]);


    // If a flat module entrypoint was specified, then track references via a `ReferenceGraph` in
    // order to produce proper diagnostics for incorrectly exported directives/pipes/etc. If there
    // is no flat module entrypoint then don't pay the cost of tracking references.
    let referencesRegistry: ReferencesRegistry;
    let exportReferenceGraph: ReferenceGraph|null = null;
    if (this.entryPoint !== null) {
      exportReferenceGraph = new ReferenceGraph();
      referencesRegistry = new ReferenceGraphAdapter(exportReferenceGraph);
    } else {
      referencesRegistry = new NoopReferencesRegistry();
    }

    const routeAnalyzer = new NgModuleRouteAnalyzer(this.moduleResolver, evaluator);

    const dtsTransforms = new DtsTransformRegistry();

    const mwpScanner = new ModuleWithProvidersScanner(reflector, evaluator, refEmitter);

    const isCore = isAngularCorePackage(this.tsProgram);

    const defaultImportTracker = new DefaultImportTracker();

    // Set up the IvyCompilation, which manages state for the Ivy transformer.
    const handlers: DecoratorHandler<unknown, unknown, unknown>[] = [
      new ComponentDecoratorHandler(
          reflector, evaluator, metaRegistry, metaReader, scopeReader, scopeRegistry, isCore,
          this.resourceManager, this.adapter.rootDirs, this.options.preserveWhitespaces || false,
          this.options.i18nUseExternalIds !== false,
          this.options.enableI18nLegacyMessageIdFormat !== false,
          this.options.i18nNormalizeLineEndingsInICUs, this.moduleResolver, this.cycleAnalyzer,
          refEmitter, defaultImportTracker, this.incrementalDriver.depGraph, injectableRegistry,
          this.closureCompilerEnabled),
      // TODO(alxhub): understand why the cast here is necessary (something to do with `null`
      // not being assignable to `unknown` when wrapped in `Readonly`).
      // clang-format off
        new DirectiveDecoratorHandler(
            reflector, evaluator, metaRegistry, scopeRegistry, metaReader,
            defaultImportTracker, injectableRegistry, isCore, this.closureCompilerEnabled,
            // In ngtsc we no longer want to compile undecorated classes with Angular features.
            // Migrations for these patterns ran as part of `ng update` and we want to ensure
            // that projects do not regress. See https://hackmd.io/@alx/ryfYYuvzH for more details.
            /* compileUndecoratedClassesWithAngularFeatures */ false
        ) as Readonly<DecoratorHandler<unknown, unknown, unknown>>,
      // clang-format on
      // Pipe handler must be before injectable handler in list so pipe factories are printed
      // before injectable factories (so injectable factories can delegate to them)
      new PipeDecoratorHandler(
          reflector, evaluator, metaRegistry, scopeRegistry, defaultImportTracker,
          injectableRegistry, isCore),
      new InjectableDecoratorHandler(
          reflector, defaultImportTracker, isCore, this.options.strictInjectionParameters || false,
          injectableRegistry),
      new NgModuleDecoratorHandler(
          reflector, evaluator, metaReader, metaRegistry, scopeRegistry, referencesRegistry, isCore,
          routeAnalyzer, refEmitter, this.adapter.factoryTracker, defaultImportTracker,
          this.closureCompilerEnabled, injectableRegistry, this.options.i18nInLocale),
    ];

    const traitCompiler = new TraitCompiler(
        handlers, reflector, this.perfRecorder, this.incrementalDriver,
        this.options.compileNonExportedClasses !== false, dtsTransforms);

    const templateTypeChecker = new TemplateTypeChecker(
        this.tsProgram, this.typeCheckingProgramStrategy, traitCompiler,
        this.getTypeCheckingConfig(), refEmitter, reflector, this.adapter, this.incrementalDriver);

    return {
      isCore,
      traitCompiler,
      reflector,
      scopeRegistry,
      dtsTransforms,
      exportReferenceGraph,
      routeAnalyzer,
      mwpScanner,
      metaReader,
      defaultImportTracker,
      aliasingHost,
      refEmitter,
      templateTypeChecker,
    };
  }
}

/**
 * Determine if the given `Program` is @angular/core.
 */
export function isAngularCorePackage(program: ts.Program): boolean {
  // Look for its_just_angular.ts somewhere in the program.
  const r3Symbols = getR3SymbolsFile(program);
  if (r3Symbols === null) {
    return false;
  }

  // Look for the constant ITS_JUST_ANGULAR in that file.
  return r3Symbols.statements.some(stmt => {
    // The statement must be a variable declaration statement.
    if (!ts.isVariableStatement(stmt)) {
      return false;
    }
    // It must be exported.
    if (stmt.modifiers === undefined ||
        !stmt.modifiers.some(mod => mod.kind === ts.SyntaxKind.ExportKeyword)) {
      return false;
    }
    // It must declare ITS_JUST_ANGULAR.
    return stmt.declarationList.declarations.some(decl => {
      // The declaration must match the name.
      if (!ts.isIdentifier(decl.name) || decl.name.text !== 'ITS_JUST_ANGULAR') {
        return false;
      }
      // It must initialize the variable to true.
      if (decl.initializer === undefined || decl.initializer.kind !== ts.SyntaxKind.TrueKeyword) {
        return false;
      }
      // This definition matches.
      return true;
    });
  });
}

/**
 * Find the 'r3_symbols.ts' file in the given `Program`, or return `null` if it wasn't there.
 */
function getR3SymbolsFile(program: ts.Program): ts.SourceFile|null {
  return program.getSourceFiles().find(file => file.fileName.indexOf('r3_symbols.ts') >= 0) || null;
}

/**
 * Since "strictTemplates" is a true superset of type checking capabilities compared to
 * "strictTemplateTypeCheck", it is required that the latter is not explicitly disabled if the
 * former is enabled.
 */
function verifyCompatibleTypeCheckOptions(options: NgCompilerOptions): ts.Diagnostic|null {
  if (options.fullTemplateTypeCheck === false && options.strictTemplates === true) {
    return {
      category: ts.DiagnosticCategory.Error,
      code: ngErrorCode(ErrorCode.CONFIG_STRICT_TEMPLATES_IMPLIES_FULL_TEMPLATE_TYPECHECK),
      file: undefined,
      start: undefined,
      length: undefined,
      messageText:
          `Angular compiler option "strictTemplates" is enabled, however "fullTemplateTypeCheck" is disabled.

Having the "strictTemplates" flag enabled implies that "fullTemplateTypeCheck" is also enabled, so
the latter can not be explicitly disabled.

One of the following actions is required:
1. Remove the "fullTemplateTypeCheck" option.
2. Remove "strictTemplates" or set it to 'false'.

More information about the template type checking compiler options can be found in the documentation:
https://v9.angular.io/guide/template-typecheck#template-type-checking`,
    };
  }

  return null;
}

class ReferenceGraphAdapter implements ReferencesRegistry {
  constructor(private graph: ReferenceGraph) {}

  add(source: ts.Declaration, ...references: Reference<ts.Declaration>[]): void {
    for (const {node} of references) {
      let sourceFile = node.getSourceFile();
      if (sourceFile === undefined) {
        sourceFile = ts.getOriginalNode(node).getSourceFile();
      }

      // Only record local references (not references into .d.ts files).
      if (sourceFile === undefined || !isDtsPath(sourceFile.fileName)) {
        this.graph.add(source, node);
      }
    }
  }
}
