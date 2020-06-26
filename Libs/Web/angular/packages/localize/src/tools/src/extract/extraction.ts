/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {AbsoluteFsPath, FileSystem, PathSegment} from '@angular/compiler-cli/src/ngtsc/file_system';
import {Logger} from '@angular/compiler-cli/src/ngtsc/logging';
import {SourceFile, SourceFileLoader} from '@angular/compiler-cli/src/ngtsc/sourcemaps';
import {ɵParsedMessage, ɵSourceLocation} from '@angular/localize';
import {transformSync} from '@babel/core';

import {makeEs2015ExtractPlugin} from './source_files/es2015_extract_plugin';
import {makeEs5ExtractPlugin} from './source_files/es5_extract_plugin';

export interface ExtractionOptions {
  basePath: AbsoluteFsPath;
  useSourceMaps?: boolean;
  localizeName?: string;
}

/**
 * Extracts parsed messages from file contents, by parsing the contents as JavaScript
 * and looking for occurrences of `$localize` in the source code.
 */
export class MessageExtractor {
  private basePath: AbsoluteFsPath;
  private useSourceMaps: boolean;
  private localizeName: string;
  private loader: SourceFileLoader;

  constructor(
      private fs: FileSystem, private logger: Logger,
      {basePath, useSourceMaps = true, localizeName = '$localize'}: ExtractionOptions) {
    this.basePath = basePath;
    this.useSourceMaps = useSourceMaps;
    this.localizeName = localizeName;
    this.loader = new SourceFileLoader(this.fs, this.logger, {webpack: basePath});
  }

  extractMessages(
      filename: string,
      ): ɵParsedMessage[] {
    const messages: ɵParsedMessage[] = [];
    const sourceCode = this.fs.readFile(this.fs.resolve(this.basePath, filename));
    if (sourceCode.includes(this.localizeName)) {
      // Only bother to parse the file if it contains a reference to `$localize`.
      transformSync(sourceCode, {
        sourceRoot: this.basePath,
        filename,
        plugins: [
          makeEs2015ExtractPlugin(messages, this.localizeName),
          makeEs5ExtractPlugin(messages, this.localizeName),
        ],
        code: false,
        ast: false
      });
    }
    if (this.useSourceMaps) {
      this.updateSourceLocations(filename, sourceCode, messages);
    }
    return messages;
  }

  /**
   * Update the location of each message to point to the source-mapped original source location, if
   * available.
   */
  private updateSourceLocations(filename: string, contents: string, messages: ɵParsedMessage[]):
      void {
    const sourceFile =
        this.loader.loadSourceFile(this.fs.resolve(this.basePath, filename), contents);
    if (sourceFile === null) {
      return;
    }
    for (const message of messages) {
      if (message.location !== undefined) {
        message.location = this.getOriginalLocation(sourceFile, message.location);
      }
    }
  }

  /**
   * Find the original location using source-maps if available.
   *
   * @param sourceFile The generated `sourceFile` that contains the `location`.
   * @param location The location within the generated `sourceFile` that needs mapping.
   *
   * @returns A new location that refers to the original source location mapped from the given
   *     `location` in the generated `sourceFile`.
   */
  private getOriginalLocation(sourceFile: SourceFile, location: ɵSourceLocation): ɵSourceLocation {
    const originalStart =
        sourceFile.getOriginalLocation(location.start.line, location.start.column);
    if (originalStart === null) {
      return location;
    }
    const originalEnd = sourceFile.getOriginalLocation(location.end.line, location.end.column);
    const start = {line: originalStart.line, column: originalStart.column};
    // We check whether the files are the same, since the returned location can only have a single
    // `file` and it would not make sense to store the end position from a different source file.
    const end = (originalEnd !== null && originalEnd.file === originalStart.file) ?
        {line: originalEnd.line, column: originalEnd.column} :
        start;
    return {file: originalStart.file, start, end};
  }
}
