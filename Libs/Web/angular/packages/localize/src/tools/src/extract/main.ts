#!/usr/bin/env node
/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {getFileSystem, setFileSystem, NodeJSFileSystem, AbsoluteFsPath} from '@angular/compiler-cli/src/ngtsc/file_system';
import {ConsoleLogger, Logger, LogLevel} from '@angular/compiler-cli/src/ngtsc/logging';
import {ɵParsedMessage} from '@angular/localize';
import * as glob from 'glob';
import * as yargs from 'yargs';
import {MessageExtractor} from './extraction';
import {TranslationSerializer} from './translation_files/translation_serializer';
import {SimpleJsonTranslationSerializer} from './translation_files/json_translation_serializer';
import {Xliff1TranslationSerializer} from './translation_files/xliff1_translation_serializer';
import {Xliff2TranslationSerializer} from './translation_files/xliff2_translation_serializer';
import {XmbTranslationSerializer} from './translation_files/xmb_translation_serializer';

if (require.main === module) {
  const args = process.argv.slice(2);
  const options =
      yargs
          .option('l', {
            alias: 'locale',
            describe: 'The locale of the source being processed',
            default: 'en',
          })
          .option('r', {
            alias: 'root',
            default: '.',
            describe: 'The root path for other paths provided in these options.\n' +
                'This should either be absolute or relative to the current working directory.'
          })
          .option('s', {
            alias: 'source',
            required: true,
            describe:
                'A glob pattern indicating what files to search for translations, e.g. `./dist/**/*.js`.\n' +
                'This should be relative to the root path.',
          })
          .option('f', {
            alias: 'format',
            required: true,
            choices: ['xmb', 'xlf', 'xlif', 'xliff', 'xlf2', 'xlif2', 'xliff2', 'json'],
            describe: 'The format of the translation file.',
          })
          .option('o', {
            alias: 'outputPath',
            required: true,
            describe:
                'A path to where the translation file will be written. This should be relative to the root path.'
          })
          .option('loglevel', {
            describe: 'The lowest severity logging message that should be output.',
            choices: ['debug', 'info', 'warn', 'error'],
          })
          .option('useSourceMaps', {
            type: 'boolean',
            default: true,
            describe:
                'Whether to generate source information in the output files by following source-map mappings found in the source files'
          })
          .option('useLegacyIds', {
            type: 'boolean',
            default: true,
            describe:
                'Whether to use the legacy id format for messages that were extracted from Angular templates.'
          })
          .strict()
          .help()
          .parse(args);

  const fs = new NodeJSFileSystem();
  setFileSystem(fs);

  const rootPath = options['root'];
  const sourceFilePaths = glob.sync(options['source'], {cwd: rootPath, nodir: true});
  const logLevel = options['loglevel'] as (keyof typeof LogLevel) | undefined;
  const logger = new ConsoleLogger(logLevel ? LogLevel[logLevel] : LogLevel.warn);


  extractTranslations({
    rootPath,
    sourceFilePaths,
    sourceLocale: options['locale'],
    format: options['format'],
    outputPath: options['outputPath'],
    logger,
    useSourceMaps: options['useSourceMaps'],
    useLegacyIds: options['useLegacyIds'],
  });
}

export interface ExtractTranslationsOptions {
  /**
   * The locale of the source being processed.
   */
  sourceLocale: string;
  /**
   * The base path for other paths provided in these options.
   * This should either be absolute or relative to the current working directory.
   */
  rootPath: string;
  /**
   * An array of paths to files to search for translations. These should be relative to the
   * rootPath.
   */
  sourceFilePaths: string[];
  /**
   * The format of the translation file.
   */
  format: string;
  /**
   * A path to where the translation file will be written. This should be relative to the rootPath.
   */
  outputPath: string;
  /**
   * The logger to use for diagnostic messages.
   */
  logger: Logger;
  /**
   * Whether to generate source information in the output files by following source-map mappings
   * found in the source file.
   */
  useSourceMaps: boolean;
  /**
   * Whether to use the legacy id format for messages that were extracted from Angular templates
   */
  useLegacyIds: boolean;
}

export function extractTranslations({
  rootPath,
  sourceFilePaths,
  sourceLocale,
  format,
  outputPath: output,
  logger,
  useSourceMaps,
  useLegacyIds
}: ExtractTranslationsOptions) {
  const fs = getFileSystem();
  const extractor =
      new MessageExtractor(fs, logger, {basePath: fs.resolve(rootPath), useSourceMaps});

  const messages: ɵParsedMessage[] = [];
  for (const file of sourceFilePaths) {
    messages.push(...extractor.extractMessages(file));
  }

  const outputPath = fs.resolve(rootPath, output);
  const serializer = getSerializer(format, sourceLocale, fs.dirname(outputPath), useLegacyIds);
  const translationFile = serializer.serialize(messages);
  fs.ensureDir(fs.dirname(outputPath));
  fs.writeFile(outputPath, translationFile);
}

export function getSerializer(
    format: string, sourceLocale: string, rootPath: AbsoluteFsPath,
    useLegacyIds: boolean): TranslationSerializer {
  switch (format) {
    case 'xlf':
    case 'xlif':
    case 'xliff':
      return new Xliff1TranslationSerializer(sourceLocale, rootPath, useLegacyIds);
    case 'xlf2':
    case 'xlif2':
    case 'xliff2':
      return new Xliff2TranslationSerializer(sourceLocale, rootPath, useLegacyIds);
    case 'xmb':
      return new XmbTranslationSerializer(rootPath, useLegacyIds);
    case 'json':
      return new SimpleJsonTranslationSerializer(sourceLocale);
  }
  throw new Error(`No translation serializer can handle the provided format: ${format}`);
}