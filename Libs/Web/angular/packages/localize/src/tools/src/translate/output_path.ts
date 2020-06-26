/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {AbsoluteFsPath} from '@angular/compiler-cli/src/ngtsc/file_system';
import {join} from 'path';

/**
 * A function that will return an absolute path to where a file is to be written, given a locale and
 * a relative path.
 */
export interface OutputPathFn {
  (locale: string, relativePath: string): string;
}

/**
 * Create a function that will compute the absolute path to where a translated file should be
 * written.
 *
 * The special `{{LOCALE}}` marker will be replaced with the locale code of the current translation.
 * @param outputFolder An absolute path to the folder containing this set of translations.
 */
export function getOutputPathFn(outputFolder: AbsoluteFsPath): OutputPathFn {
  const [pre, post] = outputFolder.split('{{LOCALE}}');
  return post === undefined ? (_locale, relativePath) => join(pre, relativePath) :
                              (locale, relativePath) => join(pre + locale + post, relativePath);
}
