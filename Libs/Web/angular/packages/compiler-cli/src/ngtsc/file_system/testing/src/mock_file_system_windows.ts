/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
/// <reference types="node" />
import * as p from 'path';

import {AbsoluteFsPath, PathSegment, PathString} from '../../src/types';
import {MockFileSystem} from './mock_file_system';

export class MockFileSystemWindows extends MockFileSystem {
  resolve(...paths: string[]): AbsoluteFsPath {
    const resolved = p.win32.resolve(this.pwd(), ...paths);
    return this.normalize(resolved as AbsoluteFsPath);
  }

  dirname<T extends string>(path: T): T {
    return this.normalize(p.win32.dirname(path) as T);
  }

  join<T extends string>(basePath: T, ...paths: string[]): T {
    return this.normalize(p.win32.join(basePath, ...paths)) as T;
  }

  relative<T extends PathString>(from: T, to: T): PathSegment {
    return this.normalize(p.win32.relative(from, to)) as PathSegment;
  }

  basename(filePath: string, extension?: string): PathSegment {
    return p.win32.basename(filePath, extension) as PathSegment;
  }

  isRooted(path: string): boolean {
    return /^([A-Z]:)?([\\\/]|$)/i.test(path);
  }

  protected splitPath<T extends PathString>(path: T): string[] {
    return path.split(/[\\\/]/);
  }

  normalize<T extends PathString>(path: T): T {
    return path.replace(/^[\/\\]/i, 'c:/').replace(/\\/g, '/') as T;
  }
}
