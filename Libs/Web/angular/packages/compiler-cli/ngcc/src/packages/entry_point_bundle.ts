/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import * as ts from 'typescript';
import {AbsoluteFsPath, FileSystem, NgtscCompilerHost} from '../../../src/ngtsc/file_system';
import {PathMappings} from '../path_mappings';
import {BundleProgram, makeBundleProgram} from './bundle_program';
import {EntryPoint, EntryPointFormat} from './entry_point';
import {NgccSourcesCompilerHost} from './ngcc_compiler_host';

/**
 * A bundle of files and paths (and TS programs) that correspond to a particular
 * format of a package entry-point.
 */
export interface EntryPointBundle {
  entryPoint: EntryPoint;
  format: EntryPointFormat;
  isCore: boolean;
  isFlatCore: boolean;
  rootDirs: AbsoluteFsPath[];
  src: BundleProgram;
  dts: BundleProgram|null;
  enableI18nLegacyMessageIdFormat: boolean;
}

/**
 * Get an object that describes a formatted bundle for an entry-point.
 * @param fs The current file-system being used.
 * @param entryPoint The entry-point that contains the bundle.
 * @param formatPath The path to the source files for this bundle.
 * @param isCore This entry point is the Angular core package.
 * @param format The underlying format of the bundle.
 * @param transformDts Whether to transform the typings along with this bundle.
 * @param pathMappings An optional set of mappings to use when compiling files.
 * @param mirrorDtsFromSrc If true then the `dts` program will contain additional files that
 * were guessed by mapping the `src` files to `dts` files.
 * @param enableI18nLegacyMessageIdFormat Whether to render legacy message ids for i18n messages in
 * component templates.
 */
export function makeEntryPointBundle(
    fs: FileSystem, entryPoint: EntryPoint, formatPath: string, isCore: boolean,
    format: EntryPointFormat, transformDts: boolean, pathMappings?: PathMappings,
    mirrorDtsFromSrc: boolean = false,
    enableI18nLegacyMessageIdFormat: boolean = true): EntryPointBundle {
  // Create the TS program and necessary helpers.
  const rootDir = entryPoint.packagePath;
  const options: ts
      .CompilerOptions = {allowJs: true, maxNodeModuleJsDepth: Infinity, rootDir, ...pathMappings};
  const srcHost = new NgccSourcesCompilerHost(fs, options, entryPoint.path);
  const dtsHost = new NgtscCompilerHost(fs, options);

  // Create the bundle programs, as necessary.
  const absFormatPath = fs.resolve(entryPoint.path, formatPath);
  const typingsPath = fs.resolve(entryPoint.path, entryPoint.typings);
  const src = makeBundleProgram(
      fs, isCore, entryPoint.packagePath, absFormatPath, 'r3_symbols.js', options, srcHost);
  const additionalDtsFiles = transformDts && mirrorDtsFromSrc ?
      computePotentialDtsFilesFromJsFiles(fs, src.program, absFormatPath, typingsPath) :
      [];
  const dts = transformDts ? makeBundleProgram(
                                 fs, isCore, entryPoint.packagePath, typingsPath, 'r3_symbols.d.ts',
                                 options, dtsHost, additionalDtsFiles) :
                             null;
  const isFlatCore = isCore && src.r3SymbolsFile === null;

  return {
    entryPoint,
    format,
    rootDirs: [rootDir],
    isCore,
    isFlatCore,
    src,
    dts,
    enableI18nLegacyMessageIdFormat
  };
}

function computePotentialDtsFilesFromJsFiles(
    fs: FileSystem, srcProgram: ts.Program, formatPath: AbsoluteFsPath,
    typingsPath: AbsoluteFsPath) {
  const formatRoot = fs.dirname(formatPath);
  const typingsRoot = fs.dirname(typingsPath);
  const additionalFiles: AbsoluteFsPath[] = [];
  for (const sf of srcProgram.getSourceFiles()) {
    if (!sf.fileName.endsWith('.js')) {
      continue;
    }

    // Given a source file at e.g. `esm2015/src/some/nested/index.js`, try to resolve the
    // declaration file under the typings root in `src/some/nested/index.d.ts`.
    const mirroredDtsPath =
        fs.resolve(typingsRoot, fs.relative(formatRoot, sf.fileName.replace(/\.js$/, '.d.ts')));
    if (fs.exists(mirroredDtsPath)) {
      additionalFiles.push(mirroredDtsPath);
    }
  }
  return additionalFiles;
}
