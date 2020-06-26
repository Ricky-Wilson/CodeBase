/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {join} from 'path';
import * as ts from 'typescript/lib/tsserverlibrary';

const logger: ts.server.Logger = {
  close(): void{},
  hasLevel(level: ts.server.LogLevel): boolean {
    return false;
  },
  loggingEnabled(): boolean {
    return false;
  },
  perftrc(s: string): void{},
  info(s: string): void{},
  startGroup(): void{},
  endGroup(): void{},
  msg(s: string, type?: ts.server.Msg): void{},
  getLogFileName(): string |
      undefined {
        return;
      },
};

export const TEST_SRCDIR = process.env.TEST_SRCDIR!;
export const PROJECT_DIR =
    join(TEST_SRCDIR, 'angular', 'packages', 'language-service', 'test', 'project');
export const TSCONFIG = join(PROJECT_DIR, 'tsconfig.json');
export const APP_COMPONENT = join(PROJECT_DIR, 'app', 'app.component.ts');
export const APP_MAIN = join(PROJECT_DIR, 'app', 'main.ts');
export const PARSING_CASES = join(PROJECT_DIR, 'app', 'parsing-cases.ts');
export const TEST_TEMPLATE = join(PROJECT_DIR, 'app', 'test.ng');

const NOOP_FILE_WATCHER: ts.FileWatcher = {
  close() {}
};

export const host: ts.server.ServerHost = {
  ...ts.sys,
  readFile(absPath: string, encoding?: string): string |
      undefined {
        const content = ts.sys.readFile(absPath, encoding);
        if (content === undefined) {
          return undefined;
        }
        if (absPath === APP_COMPONENT || absPath === PARSING_CASES || absPath === TEST_TEMPLATE) {
          return removeReferenceMarkers(removeLocationMarkers(content));
        }
        return content;
      },
  watchFile(path: string, callback: ts.FileWatcherCallback): ts.FileWatcher {
    return NOOP_FILE_WATCHER;
  },
  watchDirectory(path: string, callback: ts.DirectoryWatcherCallback): ts.FileWatcher {
    return NOOP_FILE_WATCHER;
  },
  setTimeout() {
    throw new Error('setTimeout is not implemented');
  },
  clearTimeout() {
    throw new Error('clearTimeout is not implemented');
  },
  setImmediate() {
    throw new Error('setImmediate is not implemented');
  },
  clearImmediate() {
    throw new Error('clearImmediate is not implemented');
  },
};

/**
 * Create a ConfiguredProject and an actual program for the test project located
 * in packages/language-service/test/project. Project creation exercises the
 * actual code path, but a mock host is used for the filesystem to intercept
 * and modify test files.
 */
export function setup() {
  const projectService = new ts.server.ProjectService({
    host,
    logger,
    cancellationToken: ts.server.nullCancellationToken,
    useSingleInferredProject: true,
    useInferredProjectPerProjectRoot: true,
    typingsInstaller: ts.server.nullTypingsInstaller,
  });
  // Opening APP_COMPONENT forces a new ConfiguredProject to be created based
  // on the tsconfig.json in the test project.
  projectService.openClientFile(APP_COMPONENT);
  const project = projectService.findProject(TSCONFIG);
  if (!project) {
    throw new Error(`Failed to create project for ${TSCONFIG}`);
  }
  // The following operation forces a ts.Program to be created.
  const tsLS = project.getLanguageService();
  return {
    service: new MockService(project, projectService),
    project,
    tsLS,
  };
}

class MockService {
  private readonly overwritten = new Set<ts.server.NormalizedPath>();

  constructor(
      private readonly project: ts.server.Project,
      private readonly ps: ts.server.ProjectService,
  ) {}

  overwrite(fileName: string, newText: string): string {
    const scriptInfo = this.getScriptInfo(fileName);
    this.overwriteScriptInfo(scriptInfo, preprocess(newText));
    return newText;
  }

  overwriteInlineTemplate(fileName: string, newTemplate: string): string {
    const scriptInfo = this.getScriptInfo(fileName);
    const snapshot = scriptInfo.getSnapshot();
    const originalContent = snapshot.getText(0, snapshot.getLength());
    const newContent =
        originalContent.replace(/template: `([\s\S]+)`/, `template: \`${newTemplate}\``);
    this.overwriteScriptInfo(scriptInfo, preprocess(newContent));
    return newContent;
  }

  reset() {
    if (this.overwritten.size === 0) {
      return;
    }
    for (const fileName of this.overwritten) {
      const scriptInfo = this.getScriptInfo(fileName);
      const reloaded = scriptInfo.reloadFromFile();
      if (!reloaded) {
        throw new Error(`Failed to reload ${scriptInfo.fileName}`);
      }
    }
    this.overwritten.clear();
  }

  getScriptInfo(fileName: string): ts.server.ScriptInfo {
    const scriptInfo = this.ps.getScriptInfo(fileName);
    if (!scriptInfo) {
      throw new Error(`No existing script info for ${fileName}`);
    }
    return scriptInfo;
  }

  private overwriteScriptInfo(scriptInfo: ts.server.ScriptInfo, newText: string) {
    const snapshot = scriptInfo.getSnapshot();
    scriptInfo.editContent(0, snapshot.getLength(), newText);
    this.overwritten.add(scriptInfo.fileName);
  }
}

const REGEX_CURSOR = /¦/g;
function preprocess(text: string): string {
  return text.replace(REGEX_CURSOR, '');
}

const REF_MARKER = /«(((\w|\-)+)|([^ᐱ]*ᐱ(\w+)ᐱ.[^»]*))»/g;
const LOC_MARKER = /\~\{(\w+(-\w+)*)\}/g;

function removeReferenceMarkers(value: string): string {
  return value.replace(REF_MARKER, '');
}

function removeLocationMarkers(value: string): string {
  return value.replace(LOC_MARKER, '');
}
