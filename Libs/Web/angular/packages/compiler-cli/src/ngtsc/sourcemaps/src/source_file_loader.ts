/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {commentRegex, fromComment, mapFileCommentRegex} from 'convert-source-map';

import {absoluteFrom, AbsoluteFsPath, FileSystem} from '../../file_system';
import {Logger} from '../../logging';

import {RawSourceMap} from './raw_source_map';
import {SourceFile} from './source_file';

const SCHEME_MATCHER = /^([a-z][a-z0-9.-]*):\/\//i;

/**
 * This class can be used to load a source file, its associated source map and any upstream sources.
 *
 * Since a source file might reference (or include) a source map, this class can load those too.
 * Since a source map might reference other source files, these are also loaded as needed.
 *
 * This is done recursively. The result is a "tree" of `SourceFile` objects, each containing
 * mappings to other `SourceFile` objects as necessary.
 */
export class SourceFileLoader {
  private currentPaths: AbsoluteFsPath[] = [];

  constructor(
      private fs: FileSystem, private logger: Logger,
      /** A map of URL schemes to base paths. The scheme name should be lowercase. */
      private schemeMap: Record<string, AbsoluteFsPath>) {}

  /**
   * Load a source file, compute its source map, and recursively load any referenced source files.
   *
   * @param sourcePath The path to the source file to load.
   * @param contents The contents of the source file to load.
   * @param mapAndPath The raw source-map and the path to the source-map file.
   * @returns a SourceFile object created from the `contents` and provided source-map info.
   */
  loadSourceFile(sourcePath: AbsoluteFsPath, contents: string, mapAndPath: MapAndPath): SourceFile;
  /**
   * The overload used internally to load source files referenced in a source-map.
   *
   * In this case there is no guarantee that it will return a non-null SourceMap.
   *
   * @param sourcePath The path to the source file to load.
   * @param contents The contents of the source file to load, if provided inline.
   * If it is not known the contents will be read from the file at the `sourcePath`.
   * @param mapAndPath The raw source-map and the path to the source-map file.
   *
   * @returns a SourceFile if the content for one was provided or able to be loaded from disk,
   * `null` otherwise.
   */
  loadSourceFile(sourcePath: AbsoluteFsPath, contents?: string|null, mapAndPath?: null): SourceFile
      |null;
  loadSourceFile(
      sourcePath: AbsoluteFsPath, contents: string|null = null,
      mapAndPath: MapAndPath|null = null): SourceFile|null {
    const previousPaths = this.currentPaths.slice();
    try {
      if (contents === null) {
        if (!this.fs.exists(sourcePath)) {
          return null;
        }
        contents = this.readSourceFile(sourcePath);
      }

      // If not provided try to load the source map based on the source itself
      if (mapAndPath === null) {
        mapAndPath = this.loadSourceMap(sourcePath, contents);
      }

      let map: RawSourceMap|null = null;
      let inline = true;
      let sources: (SourceFile|null)[] = [];
      if (mapAndPath !== null) {
        const basePath = mapAndPath.mapPath || sourcePath;
        sources = this.processSources(basePath, mapAndPath.map);
        map = mapAndPath.map;
        inline = mapAndPath.mapPath === null;
      }

      return new SourceFile(sourcePath, contents, map, inline, sources);
    } catch (e) {
      this.logger.warn(
          `Unable to fully load ${sourcePath} for source-map flattening: ${e.message}`);
      return null;
    } finally {
      // We are finished with this recursion so revert the paths being tracked
      this.currentPaths = previousPaths;
    }
  }

  /**
   * Find the source map associated with the source file whose `sourcePath` and `contents` are
   * provided.
   *
   * Source maps can be inline, as part of a base64 encoded comment, or external as a separate file
   * whose path is indicated in a comment or implied from the name of the source file itself.
   */
  private loadSourceMap(sourcePath: AbsoluteFsPath, contents: string): MapAndPath|null {
    // Only consider a source-map comment from the last non-empty line of the file, in case there
    // are embedded source-map comments elsewhere in the file (as can be the case with bundlers like
    // webpack).
    const lastLine = this.getLastNonEmptyLine(contents);
    const inline = commentRegex.exec(lastLine);
    if (inline !== null) {
      return {map: fromComment(inline.pop()!).sourcemap, mapPath: null};
    }

    const external = mapFileCommentRegex.exec(lastLine);
    if (external) {
      try {
        const fileName = external[1] || external[2];
        const externalMapPath = this.fs.resolve(this.fs.dirname(sourcePath), fileName);
        return {map: this.readRawSourceMap(externalMapPath), mapPath: externalMapPath};
      } catch (e) {
        this.logger.warn(
            `Unable to fully load ${sourcePath} for source-map flattening: ${e.message}`);
        return null;
      }
    }

    const impliedMapPath = absoluteFrom(sourcePath + '.map');
    if (this.fs.exists(impliedMapPath)) {
      return {map: this.readRawSourceMap(impliedMapPath), mapPath: impliedMapPath};
    }

    return null;
  }

  /**
   * Iterate over each of the "sources" for this source file's source map, recursively loading each
   * source file and its associated source map.
   */
  private processSources(basePath: AbsoluteFsPath, map: RawSourceMap): (SourceFile|null)[] {
    const sourceRoot = this.fs.resolve(
        this.fs.dirname(basePath), this.replaceSchemeWithPath(map.sourceRoot || ''));
    return map.sources.map((source, index) => {
      const path = this.fs.resolve(sourceRoot, this.replaceSchemeWithPath(source));
      const content = map.sourcesContent && map.sourcesContent[index] || null;
      return this.loadSourceFile(path, content, null);
    });
  }

  /**
   * Load the contents of the source file from disk.
   *
   * @param sourcePath The path to the source file.
   */
  private readSourceFile(sourcePath: AbsoluteFsPath): string {
    this.trackPath(sourcePath);
    return this.fs.readFile(sourcePath);
  }

  /**
   * Load the source map from the file at `mapPath`, parsing its JSON contents into a `RawSourceMap`
   * object.
   *
   * @param mapPath The path to the source-map file.
   */
  private readRawSourceMap(mapPath: AbsoluteFsPath): RawSourceMap {
    this.trackPath(mapPath);
    return JSON.parse(this.fs.readFile(mapPath));
  }

  /**
   * Track source file paths if we have loaded them from disk so that we don't get into an infinite
   * recursion.
   */
  private trackPath(path: AbsoluteFsPath): void {
    if (this.currentPaths.includes(path)) {
      throw new Error(
          `Circular source file mapping dependency: ${this.currentPaths.join(' -> ')} -> ${path}`);
    }
    this.currentPaths.push(path);
  }

  private getLastNonEmptyLine(contents: string): string {
    let trailingWhitespaceIndex = contents.length - 1;
    while (trailingWhitespaceIndex > 0 &&
           (contents[trailingWhitespaceIndex] === '\n' ||
            contents[trailingWhitespaceIndex] === '\r')) {
      trailingWhitespaceIndex--;
    }
    let lastRealLineIndex = contents.lastIndexOf('\n', trailingWhitespaceIndex - 1);
    if (lastRealLineIndex === -1) {
      lastRealLineIndex = 0;
    }
    return contents.substr(lastRealLineIndex + 1);
  }

  /**
   * Replace any matched URL schemes with their corresponding path held in the schemeMap.
   *
   * Some build tools replace real file paths with scheme prefixed paths - e.g. `webpack://`.
   * We use the `schemeMap` passed to this class to convert such paths to "real" file paths.
   * In some cases, this is not possible, since the file was actually synthesized by the build tool.
   * But the end result is better than prefixing the sourceRoot in front of the scheme.
   */
  private replaceSchemeWithPath(path: string): string {
    return path.replace(
        SCHEME_MATCHER, (_: string, scheme: string) => this.schemeMap[scheme.toLowerCase()] || '');
  }
}

/** A small helper structure that is returned from `loadSourceMap()`. */
interface MapAndPath {
  /** The path to the source map if it was external or `null` if it was inline. */
  mapPath: AbsoluteFsPath|null;
  /** The raw source map itself. */
  map: RawSourceMap;
}
