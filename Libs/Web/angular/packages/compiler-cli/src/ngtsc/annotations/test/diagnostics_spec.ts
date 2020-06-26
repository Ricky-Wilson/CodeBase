/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {platform} from 'os';
import * as ts from 'typescript';

import {FatalDiagnosticError} from '../../diagnostics';
import {absoluteFrom as _} from '../../file_system';
import {runInEachFileSystem, TestFile} from '../../file_system/testing';
import {PartialEvaluator} from '../../partial_evaluator';
import {TypeScriptReflectionHost} from '../../reflection';
import {getDeclaration, makeProgram} from '../../testing';
import {createValueHasWrongTypeError} from '../src/diagnostics';

runInEachFileSystem(os => {
  describe('ngtsc annotation diagnostics', () => {
    // These tests are currently disabled when running in Windows mode as the assertions involving
    // the filename attached to the diagnostic are suffering from a case-sensitivity issue.
    //
    // TODO(JoostK): re-enable on Windows once the case issue has been solved.
    if (os !== 'Windows' && platform() !== 'win32') {
      describe('createValueError()', () => {
        it('should include a trace for dynamic values', () => {
          const error = createError('', 'nonexistent', 'Error message');

          if (typeof error.message === 'string') {
            return fail('Created error must have a message chain');
          }
          expect(error.message.messageText).toBe('Error message');
          expect(error.message.next!.length).toBe(1);
          expect(error.message.next![0].messageText)
              .toBe(`Value could not be determined statically.`);

          expect(error.relatedInformation).toBeDefined();
          expect(error.relatedInformation!.length).toBe(1);

          expect(error.relatedInformation![0].messageText).toBe('Unknown reference.');
          expect(error.relatedInformation![0].file!.fileName).toBe(_('/entry.ts'));
          expect(getSourceCode(error.relatedInformation![0])).toBe('nonexistent');
        });

        it('should include a pointer for a reference to a named declaration', () => {
          const error = createError(
              `import {Foo} from './foo';`, 'Foo', 'Error message',
              [{name: _('/foo.ts'), contents: 'export class Foo {}'}]);

          if (typeof error.message === 'string') {
            return fail('Created error must have a message chain');
          }
          expect(error.message.messageText).toBe('Error message');
          expect(error.message.next!.length).toBe(1);
          expect(error.message.next![0].messageText).toBe(`Value is a reference to 'Foo'.`);

          expect(error.relatedInformation).toBeDefined();
          expect(error.relatedInformation!.length).toBe(1);
          expect(error.relatedInformation![0].messageText).toBe('Reference is declared here.');
          expect(error.relatedInformation![0].file!.fileName).toBe(_('/foo.ts'));
          expect(getSourceCode(error.relatedInformation![0])).toBe('Foo');
        });

        it('should include a pointer for a reference to an anonymous declaration', () => {
          const error = createError(
              `import Foo from './foo';`, 'Foo', 'Error message',
              [{name: _('/foo.ts'), contents: 'export default class {}'}]);

          if (typeof error.message === 'string') {
            return fail('Created error must have a message chain');
          }
          expect(error.message.messageText).toBe('Error message');
          expect(error.message.next!.length).toBe(1);
          expect(error.message.next![0].messageText)
              .toBe(`Value is a reference to an anonymous declaration.`);

          expect(error.relatedInformation).toBeDefined();
          expect(error.relatedInformation!.length).toBe(1);
          expect(error.relatedInformation![0].messageText).toBe('Reference is declared here.');
          expect(error.relatedInformation![0].file!.fileName).toBe(_('/foo.ts'));
          expect(getSourceCode(error.relatedInformation![0])).toBe('export default class {}');
        });

        it('should include a representation of the value\'s type', () => {
          const error = createError('', '{a: 2}', 'Error message');

          if (typeof error.message === 'string') {
            return fail('Created error must have a message chain');
          }
          expect(error.message.messageText).toBe('Error message');
          expect(error.message.next!.length).toBe(1);
          expect(error.message.next![0].messageText).toBe(`Value is of type '{ a: number }'.`);

          expect(error.relatedInformation).not.toBeDefined();
        });
      });
    }

    it('should not be empty', () => {});
  });
});

function getSourceCode(diag: ts.DiagnosticRelatedInformation): string {
  const text = diag.file!.text;
  return text.substr(diag.start!, diag.length!);
}

function createError(
    code: string, expr: string, messageText: string,
    supportingFiles: TestFile[] = []): FatalDiagnosticError {
  const {program} = makeProgram(
      [{name: _('/entry.ts'), contents: `${code}; const target$ = ${expr}`}, ...supportingFiles],
      /* options */ undefined, /* host */ undefined, /* checkForErrors */ false);
  const checker = program.getTypeChecker();
  const decl = getDeclaration(program, _('/entry.ts'), 'target$', ts.isVariableDeclaration);
  const valueExpr = decl.initializer!;

  const reflectionHost = new TypeScriptReflectionHost(checker);
  const evaluator = new PartialEvaluator(reflectionHost, checker, /* dependencyTracker */ null);

  const value = evaluator.evaluate(valueExpr);
  return createValueHasWrongTypeError(valueExpr, value, messageText);
}
