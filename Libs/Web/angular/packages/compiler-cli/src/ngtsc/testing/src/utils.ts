/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

///<reference types="jasmine"/>

import * as ts from 'typescript';

import {AbsoluteFsPath, dirname, getFileSystem, getSourceFileOrError, NgtscCompilerHost} from '../../file_system';

export function makeProgram(
    files: {name: AbsoluteFsPath, contents: string, isRoot?: boolean}[],
    options?: ts.CompilerOptions, host?: ts.CompilerHost, checkForErrors: boolean = true):
    {program: ts.Program, host: ts.CompilerHost, options: ts.CompilerOptions} {
  const fs = getFileSystem();
  files.forEach(file => {
    fs.ensureDir(dirname(file.name));
    fs.writeFile(file.name, file.contents);
  });

  const compilerOptions = {
    noLib: true,
    experimentalDecorators: true,
    moduleResolution: ts.ModuleResolutionKind.NodeJs,
    ...options
  };
  const compilerHost = new NgtscCompilerHost(fs, compilerOptions);
  const rootNames = files.filter(file => file.isRoot !== false)
                        .map(file => compilerHost.getCanonicalFileName(file.name));
  const program = ts.createProgram(rootNames, compilerOptions, compilerHost);
  if (checkForErrors) {
    const diags = [...program.getSyntacticDiagnostics(), ...program.getSemanticDiagnostics()];
    if (diags.length > 0) {
      const errors = diags.map(diagnostic => {
        let message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n');
        if (diagnostic.file) {
          const {line, character} =
              diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start!);
          message = `${diagnostic.file.fileName} (${line + 1},${character + 1}): ${message}`;
        }
        return `Error: ${message}`;
      });
      throw new Error(`Typescript diagnostics failed! ${errors.join(', ')}`);
    }
  }
  return {program, host: compilerHost, options: compilerOptions};
}

export function getDeclaration<T extends ts.Declaration>(
    program: ts.Program, fileName: AbsoluteFsPath, name: string,
    assert: (value: any) => value is T): T {
  const sf = getSourceFileOrError(program, fileName);
  const chosenDecl = walkForDeclaration(name, sf);

  if (chosenDecl === null) {
    throw new Error(`No such symbol: ${name} in ${fileName}`);
  }
  if (!assert(chosenDecl)) {
    throw new Error(`Symbol ${name} from ${fileName} is a ${ts.SyntaxKind[chosenDecl.kind]}`);
  }
  return chosenDecl;
}

// We walk the AST tree looking for a declaration that matches
export function walkForDeclaration(name: string, rootNode: ts.Node): ts.Declaration|null {
  let chosenDecl: ts.Declaration|null = null;
  rootNode.forEachChild(node => {
    if (chosenDecl !== null) {
      return;
    }
    if (ts.isVariableStatement(node)) {
      node.declarationList.declarations.forEach(decl => {
        if (bindingNameEquals(decl.name, name)) {
          chosenDecl = decl;
        } else {
          chosenDecl = walkForDeclaration(name, node);
        }
      });
    } else if (
        ts.isClassDeclaration(node) || ts.isFunctionDeclaration(node) ||
        ts.isInterfaceDeclaration(node) || ts.isClassExpression(node)) {
      if (node.name !== undefined && node.name.text === name) {
        chosenDecl = node;
      }
    } else if (
        ts.isImportDeclaration(node) && node.importClause !== undefined &&
        node.importClause.name !== undefined && node.importClause.name.text === name) {
      chosenDecl = node.importClause;
    } else {
      chosenDecl = walkForDeclaration(name, node);
    }
  });
  return chosenDecl;
}

const COMPLETE_REUSE_FAILURE_MESSAGE =
    'The original program was not reused completely, even though no changes should have been made to its structure';

/**
 * Extracted from TypeScript's internal enum `StructureIsReused`.
 */
enum TsStructureIsReused {
  Not = 0,
  SafeModules = 1,
  Completely = 2,
}

export function expectCompleteReuse(oldProgram: ts.Program): void {
  // Assert complete reuse using TypeScript's private API.
  expect((oldProgram as any).structureIsReused)
      .toBe(TsStructureIsReused.Completely, COMPLETE_REUSE_FAILURE_MESSAGE);
}

function bindingNameEquals(node: ts.BindingName, name: string): boolean {
  if (ts.isIdentifier(node)) {
    return node.text === name;
  }
  return false;
}
