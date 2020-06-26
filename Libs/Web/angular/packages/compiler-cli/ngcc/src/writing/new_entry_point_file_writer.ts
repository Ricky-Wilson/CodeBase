
/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {absoluteFromSourceFile, AbsoluteFsPath, dirname, FileSystem, join, relative} from '../../../src/ngtsc/file_system';
import {Logger} from '../../../src/ngtsc/logging';
import {isDtsPath} from '../../../src/ngtsc/util/src/typescript';
import {EntryPoint, EntryPointJsonProperty} from '../packages/entry_point';
import {EntryPointBundle} from '../packages/entry_point_bundle';
import {FileToWrite} from '../rendering/utils';

import {InPlaceFileWriter} from './in_place_file_writer';
import {PackageJsonUpdater} from './package_json_updater';

export const NGCC_DIRECTORY = '__ivy_ngcc__';
export const NGCC_PROPERTY_EXTENSION = '_ivy_ngcc';

/**
 * This FileWriter creates a copy of the original entry-point, then writes the transformed
 * files onto the files in this copy, and finally updates the package.json with a new
 * entry-point format property that points to this new entry-point.
 *
 * If there are transformed typings files in this bundle, they are updated in-place (see the
 * `InPlaceFileWriter`).
 */
export class NewEntryPointFileWriter extends InPlaceFileWriter {
  constructor(
      fs: FileSystem, logger: Logger, errorOnFailedEntryPoint: boolean,
      private pkgJsonUpdater: PackageJsonUpdater) {
    super(fs, logger, errorOnFailedEntryPoint);
  }

  writeBundle(
      bundle: EntryPointBundle, transformedFiles: FileToWrite[],
      formatProperties: EntryPointJsonProperty[]) {
    // The new folder is at the root of the overall package
    const entryPoint = bundle.entryPoint;
    const ngccFolder = join(entryPoint.packagePath, NGCC_DIRECTORY);
    this.copyBundle(bundle, entryPoint.packagePath, ngccFolder);
    transformedFiles.forEach(file => this.writeFile(file, entryPoint.packagePath, ngccFolder));
    this.updatePackageJson(entryPoint, formatProperties, ngccFolder);
  }

  revertBundle(
      entryPoint: EntryPoint, transformedFilePaths: AbsoluteFsPath[],
      formatProperties: EntryPointJsonProperty[]): void {
    // IMPLEMENTATION NOTE:
    //
    // The changes made by `copyBundle()` are not reverted here. The non-transformed copied files
    // are identical to the original ones and they will be overwritten when re-processing the
    // entry-point anyway.
    //
    // This way, we avoid the overhead of having to inform the master process about all source files
    // being copied in `copyBundle()`.

    // Revert the transformed files.
    for (const filePath of transformedFilePaths) {
      this.revertFile(filePath, entryPoint.packagePath);
    }

    // Revert any changes to `package.json`.
    this.revertPackageJson(entryPoint, formatProperties);
  }

  protected copyBundle(
      bundle: EntryPointBundle, packagePath: AbsoluteFsPath, ngccFolder: AbsoluteFsPath) {
    bundle.src.program.getSourceFiles().forEach(sourceFile => {
      const relativePath = relative(packagePath, absoluteFromSourceFile(sourceFile));
      const isOutsidePackage = relativePath.startsWith('..');
      if (!sourceFile.isDeclarationFile && !isOutsidePackage) {
        const newFilePath = join(ngccFolder, relativePath);
        this.fs.ensureDir(dirname(newFilePath));
        this.fs.copyFile(absoluteFromSourceFile(sourceFile), newFilePath);
      }
    });
  }

  protected writeFile(file: FileToWrite, packagePath: AbsoluteFsPath, ngccFolder: AbsoluteFsPath):
      void {
    if (isDtsPath(file.path.replace(/\.map$/, ''))) {
      // This is either `.d.ts` or `.d.ts.map` file
      super.writeFileAndBackup(file);
    } else {
      const relativePath = relative(packagePath, file.path);
      const newFilePath = join(ngccFolder, relativePath);
      this.fs.ensureDir(dirname(newFilePath));
      this.fs.writeFile(newFilePath, file.contents);
    }
  }

  protected revertFile(filePath: AbsoluteFsPath, packagePath: AbsoluteFsPath): void {
    if (isDtsPath(filePath.replace(/\.map$/, ''))) {
      // This is either `.d.ts` or `.d.ts.map` file
      super.revertFileAndBackup(filePath);
    } else if (this.fs.exists(filePath)) {
      const relativePath = relative(packagePath, filePath);
      const newFilePath = join(packagePath, NGCC_DIRECTORY, relativePath);
      this.fs.removeFile(newFilePath);
    }
  }

  protected updatePackageJson(
      entryPoint: EntryPoint, formatProperties: EntryPointJsonProperty[],
      ngccFolder: AbsoluteFsPath) {
    if (formatProperties.length === 0) {
      // No format properties need updating.
      return;
    }

    const packageJson = entryPoint.packageJson;
    const packageJsonPath = join(entryPoint.path, 'package.json');

    // All format properties point to the same format-path.
    const oldFormatProp = formatProperties[0]!;
    const oldFormatPath = packageJson[oldFormatProp]!;
    const oldAbsFormatPath = join(entryPoint.path, oldFormatPath);
    const newAbsFormatPath = join(ngccFolder, relative(entryPoint.packagePath, oldAbsFormatPath));
    const newFormatPath = relative(entryPoint.path, newAbsFormatPath);

    // Update all properties in `package.json` (both in memory and on disk).
    const update = this.pkgJsonUpdater.createUpdate();

    for (const formatProperty of formatProperties) {
      if (packageJson[formatProperty] !== oldFormatPath) {
        throw new Error(
            `Unable to update '${packageJsonPath}': Format properties ` +
            `(${formatProperties.join(', ')}) map to more than one format-path.`);
      }

      update.addChange(
          [`${formatProperty}${NGCC_PROPERTY_EXTENSION}`], newFormatPath, {before: formatProperty});
    }

    update.writeChanges(packageJsonPath, packageJson);
  }

  protected revertPackageJson(entryPoint: EntryPoint, formatProperties: EntryPointJsonProperty[]) {
    if (formatProperties.length === 0) {
      // No format properties need reverting.
      return;
    }

    const packageJson = entryPoint.packageJson;
    const packageJsonPath = join(entryPoint.path, 'package.json');

    // Revert all properties in `package.json` (both in memory and on disk).
    // Since `updatePackageJson()` only adds properties, it is safe to just remove them (if they
    // exist).
    const update = this.pkgJsonUpdater.createUpdate();

    for (const formatProperty of formatProperties) {
      update.addChange([`${formatProperty}${NGCC_PROPERTY_EXTENSION}`], undefined);
    }

    update.writeChanges(packageJsonPath, packageJson);
  }
}
