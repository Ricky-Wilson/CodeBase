/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
/// <reference types="node" />
import * as fs from 'fs';
import * as fsExtra from 'fs-extra';
import * as p from 'path';
import {absoluteFrom, relativeFrom} from './helpers';
import {AbsoluteFsPath, FileStats, FileSystem, PathSegment, PathString} from './types';

/**
 * A wrapper around the Node.js file-system (i.e the `fs` package).
 */
export class NodeJSFileSystem implements FileSystem {
  private _caseSensitive: boolean|undefined = undefined;
  exists(path: AbsoluteFsPath): boolean {
    return fs.existsSync(path);
  }
  readFile(path: AbsoluteFsPath): string {
    return fs.readFileSync(path, 'utf8');
  }
  readFileBuffer(path: AbsoluteFsPath): Buffer {
    return fs.readFileSync(path);
  }
  writeFile(path: AbsoluteFsPath, data: string|Buffer, exclusive: boolean = false): void {
    fs.writeFileSync(path, data, exclusive ? {flag: 'wx'} : undefined);
  }
  removeFile(path: AbsoluteFsPath): void {
    fs.unlinkSync(path);
  }
  symlink(target: AbsoluteFsPath, path: AbsoluteFsPath): void {
    fs.symlinkSync(target, path);
  }
  readdir(path: AbsoluteFsPath): PathSegment[] {
    return fs.readdirSync(path) as PathSegment[];
  }
  lstat(path: AbsoluteFsPath): FileStats {
    return fs.lstatSync(path);
  }
  stat(path: AbsoluteFsPath): FileStats {
    return fs.statSync(path);
  }
  pwd(): AbsoluteFsPath {
    return this.normalize(process.cwd()) as AbsoluteFsPath;
  }
  chdir(dir: AbsoluteFsPath): void {
    process.chdir(dir);
  }
  copyFile(from: AbsoluteFsPath, to: AbsoluteFsPath): void {
    fs.copyFileSync(from, to);
  }
  moveFile(from: AbsoluteFsPath, to: AbsoluteFsPath): void {
    fs.renameSync(from, to);
  }
  ensureDir(path: AbsoluteFsPath): void {
    const parents: AbsoluteFsPath[] = [];
    while (!this.isRoot(path) && !this.exists(path)) {
      parents.push(path);
      path = this.dirname(path);
    }
    while (parents.length) {
      this.safeMkdir(parents.pop()!);
    }
  }
  removeDeep(path: AbsoluteFsPath): void {
    fsExtra.removeSync(path);
  }
  isCaseSensitive(): boolean {
    if (this._caseSensitive === undefined) {
      // Note the use of the real file-system is intentional:
      // `this.exists()` relies upon `isCaseSensitive()` so that would cause an infinite recursion.
      this._caseSensitive = !fs.existsSync(togglePathCase(__filename));
    }
    return this._caseSensitive;
  }
  resolve(...paths: string[]): AbsoluteFsPath {
    return this.normalize(p.resolve(...paths)) as AbsoluteFsPath;
  }

  dirname<T extends string>(file: T): T {
    return this.normalize(p.dirname(file)) as T;
  }
  join<T extends string>(basePath: T, ...paths: string[]): T {
    return this.normalize(p.join(basePath, ...paths)) as T;
  }
  isRoot(path: AbsoluteFsPath): boolean {
    return this.dirname(path) === this.normalize(path);
  }
  isRooted(path: string): boolean {
    return p.isAbsolute(path);
  }
  relative<T extends PathString>(from: T, to: T): PathSegment {
    return relativeFrom(this.normalize(p.relative(from, to)));
  }
  basename(filePath: string, extension?: string): PathSegment {
    return p.basename(filePath, extension) as PathSegment;
  }
  extname(path: AbsoluteFsPath|PathSegment): string {
    return p.extname(path);
  }
  realpath(path: AbsoluteFsPath): AbsoluteFsPath {
    return this.resolve(fs.realpathSync(path));
  }
  getDefaultLibLocation(): AbsoluteFsPath {
    return this.resolve(require.resolve('typescript'), '..');
  }
  normalize<T extends string>(path: T): T {
    // Convert backslashes to forward slashes
    return path.replace(/\\/g, '/') as T;
  }

  private safeMkdir(path: AbsoluteFsPath): void {
    try {
      fs.mkdirSync(path);
    } catch (err) {
      // Ignore the error, if the path already exists and points to a directory.
      // Re-throw otherwise.
      if (!this.exists(path) || !this.stat(path).isDirectory()) {
        throw err;
      }
    }
  }
}

/**
 * Toggle the case of each character in a file path.
 */
function togglePathCase(str: string): AbsoluteFsPath {
  return absoluteFrom(
      str.replace(/\w/g, ch => ch.toUpperCase() === ch ? ch.toLowerCase() : ch.toUpperCase()));
}
