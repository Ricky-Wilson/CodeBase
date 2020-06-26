/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import * as ts from 'typescript';

import {NgCompiler, NgCompilerHost} from './core';
import {NgCompilerOptions, UnifiedModulesHost} from './core/api';
import {NodeJSFileSystem, setFileSystem} from './file_system';
import {PatchedProgramIncrementalBuildStrategy} from './incremental';
import {NOOP_PERF_RECORDER} from './perf';
import {untagAllTsFiles} from './shims';
import {ReusedProgramStrategy} from './typecheck/src/augmented_program';

// The following is needed to fix a the chicken-and-egg issue where the sync (into g3) script will
// refuse to accept this file unless the following string appears:
// import * as plugin from '@bazel/typescript/internal/tsc_wrapped/plugin_api';

/**
 * A `ts.CompilerHost` which also returns a list of input files, out of which the `ts.Program`
 * should be created.
 *
 * Currently mirrored from @bazel/typescript/internal/tsc_wrapped/plugin_api (with the naming of
 * `fileNameToModuleName` corrected).
 */
interface PluginCompilerHost extends ts.CompilerHost, Partial<UnifiedModulesHost> {
  readonly inputFiles: ReadonlyArray<string>;
}

/**
 * Mirrors the plugin interface from tsc_wrapped which is currently under active development. To
 * enable progress to be made in parallel, the upstream interface isn't implemented directly.
 * Instead, `TscPlugin` here is structurally assignable to what tsc_wrapped expects.
 */
interface TscPlugin {
  readonly name: string;

  wrapHost(
      host: ts.CompilerHost&Partial<UnifiedModulesHost>, inputFiles: ReadonlyArray<string>,
      options: ts.CompilerOptions): PluginCompilerHost;

  setupCompilation(program: ts.Program, oldProgram?: ts.Program): {
    ignoreForDiagnostics: Set<ts.SourceFile>,
    ignoreForEmit: Set<ts.SourceFile>,
  };

  getDiagnostics(file?: ts.SourceFile): ts.Diagnostic[];

  getOptionDiagnostics(): ts.Diagnostic[];

  getNextProgram(): ts.Program;

  createTransformers(): ts.CustomTransformers;
}

/**
 * A plugin for `tsc_wrapped` which allows Angular compilation from a plain `ts_library`.
 */
export class NgTscPlugin implements TscPlugin {
  name = 'ngtsc';

  private options: NgCompilerOptions|null = null;
  private host: NgCompilerHost|null = null;
  private _compiler: NgCompiler|null = null;

  get compiler(): NgCompiler {
    if (this._compiler === null) {
      throw new Error('Lifecycle error: setupCompilation() must be called first.');
    }
    return this._compiler;
  }

  constructor(private ngOptions: {}) {
    setFileSystem(new NodeJSFileSystem());
  }

  wrapHost(
      host: ts.CompilerHost&UnifiedModulesHost, inputFiles: readonly string[],
      options: ts.CompilerOptions): PluginCompilerHost {
    // TODO(alxhub): Eventually the `wrapHost()` API will accept the old `ts.Program` (if one is
    // available). When it does, its `ts.SourceFile`s need to be re-tagged to enable proper
    // incremental compilation.
    this.options = {...this.ngOptions, ...options} as NgCompilerOptions;
    this.host = NgCompilerHost.wrap(host, inputFiles, this.options, /* oldProgram */ null);
    return this.host;
  }

  setupCompilation(program: ts.Program, oldProgram?: ts.Program): {
    ignoreForDiagnostics: Set<ts.SourceFile>,
    ignoreForEmit: Set<ts.SourceFile>,
  } {
    if (this.host === null || this.options === null) {
      throw new Error('Lifecycle error: setupCompilation() before wrapHost().');
    }
    this.host.postProgramCreationCleanup();
    untagAllTsFiles(program);
    const typeCheckStrategy = new ReusedProgramStrategy(
        program, this.host, this.options, this.host.shimExtensionPrefixes);
    this._compiler = new NgCompiler(
        this.host, this.options, program, typeCheckStrategy,
        new PatchedProgramIncrementalBuildStrategy(), oldProgram, NOOP_PERF_RECORDER);
    return {
      ignoreForDiagnostics: this._compiler.ignoreForDiagnostics,
      ignoreForEmit: this._compiler.ignoreForEmit,
    };
  }

  getDiagnostics(file?: ts.SourceFile): ts.Diagnostic[] {
    return this.compiler.getDiagnostics(file);
  }

  getOptionDiagnostics(): ts.Diagnostic[] {
    return this.compiler.getOptionDiagnostics();
  }

  getNextProgram(): ts.Program {
    return this.compiler.getNextProgram();
  }

  createTransformers(): ts.CustomTransformers {
    return this.compiler.prepareEmit().transformers;
  }
}
