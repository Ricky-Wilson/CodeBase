/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import * as ts from 'typescript';

import {TypeScriptReflectionHost} from '../../src/ngtsc/reflection';
import {getDownlevelDecoratorsTransform} from '../../src/transformers/downlevel_decorators_transform';
import {MockAotContext, MockCompilerHost} from '../mocks';

const TEST_FILE_INPUT = '/test.ts';
const TEST_FILE_OUTPUT = `/test.js`;
const TEST_FILE_DTS_OUTPUT = `/test.d.ts`;

describe('downlevel decorator transform', () => {
  let host: MockCompilerHost;
  let context: MockAotContext;
  let diagnostics: ts.Diagnostic[];
  let isClosureEnabled: boolean;
  let skipClassDecorators: boolean;

  beforeEach(() => {
    diagnostics = [];
    context = new MockAotContext('/', {
      'dom_globals.d.ts': `
        declare class HTMLElement {};
        declare class Document {};
      `
    });
    host = new MockCompilerHost(context);
    isClosureEnabled = false;
    skipClassDecorators = false;
  });

  function transform(
      contents: string, compilerOptions: ts.CompilerOptions = {},
      preTransformers: ts.TransformerFactory<ts.SourceFile>[] = []) {
    context.writeFile(TEST_FILE_INPUT, contents);
    const program = ts.createProgram(
        [TEST_FILE_INPUT, '/dom_globals.d.ts'], {
          module: ts.ModuleKind.CommonJS,
          importHelpers: true,
          lib: ['dom', 'es2015'],
          target: ts.ScriptTarget.ES2017,
          declaration: true,
          experimentalDecorators: true,
          emitDecoratorMetadata: false,
          ...compilerOptions
        },
        host);
    const testFile = program.getSourceFile(TEST_FILE_INPUT);
    const typeChecker = program.getTypeChecker();
    const reflectionHost = new TypeScriptReflectionHost(typeChecker);
    const transformers: ts.CustomTransformers = {
      before: [
        ...preTransformers,
        getDownlevelDecoratorsTransform(
            program.getTypeChecker(), reflectionHost, diagnostics,
            /* isCore */ false, isClosureEnabled, skipClassDecorators)
      ]
    };
    let output: string|null = null;
    let dtsOutput: string|null = null;
    const emitResult = program.emit(
        testFile, ((fileName, outputText) => {
          if (fileName === TEST_FILE_OUTPUT) {
            output = outputText;
          } else if (fileName === TEST_FILE_DTS_OUTPUT) {
            dtsOutput = outputText;
          }
        }),
        undefined, undefined, transformers);
    diagnostics.push(...emitResult.diagnostics);
    expect(output).not.toBeNull();
    return {
      output: omitLeadingWhitespace(output!),
      dtsOutput: dtsOutput ? omitLeadingWhitespace(dtsOutput) : null
    };
  }

  it('should downlevel decorators for @Injectable decorated class', () => {
    const {output} = transform(`
      import {Injectable} from '@angular/core';

      export class ClassInject {};

      @Injectable()
      export class MyService {
        constructor(v: ClassInject) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyService.decorators = [
          { type: core_1.Injectable }
      ];
      MyService.ctorParameters = () => [
          { type: ClassInject }
      ];`);
    expect(output).not.toContain('tslib');
  });

  it('should downlevel decorators for @Directive decorated class', () => {
    const {output} = transform(`
      import {Directive} from '@angular/core';

      export class ClassInject {};

      @Directive()
      export class MyDir {
        constructor(v: ClassInject) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyDir.decorators = [
          { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
          { type: ClassInject }
      ];`);
    expect(output).not.toContain('tslib');
  });

  it('should downlevel decorators for @Component decorated class', () => {
    const {output} = transform(`
      import {Component} from '@angular/core';

      export class ClassInject {};

      @Component({template: 'hello'})
      export class MyComp {
        constructor(v: ClassInject) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyComp.decorators = [
        { type: core_1.Component, args: [{ template: 'hello' },] }
      ];
      MyComp.ctorParameters = () => [
        { type: ClassInject }
      ];`);
    expect(output).not.toContain('tslib');
  });

  it('should downlevel decorators for @Pipe decorated class', () => {
    const {output} = transform(`
      import {Pipe} from '@angular/core';

      export class ClassInject {};

      @Pipe({selector: 'hello'})
      export class MyPipe {
        constructor(v: ClassInject) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyPipe.decorators = [
        { type: core_1.Pipe, args: [{ selector: 'hello' },] }
      ];
      MyPipe.ctorParameters = () => [
        { type: ClassInject }
      ];`);
    expect(output).not.toContain('tslib');
  });

  it('should not downlevel non-Angular class decorators', () => {
    const {output} = transform(`
      @SomeUnknownDecorator()
      export class MyClass {}
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyClass = tslib_1.__decorate([
        SomeUnknownDecorator()
      ], MyClass);
    `);
    expect(output).not.toContain('MyClass.decorators');
  });

  it('should downlevel Angular-decorated class member', () => {
    const {output} = transform(`
      import {Input} from '@angular/core';
      
      export class MyDir {
        @Input() disabled: boolean = false;
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyDir.propDecorators = {
        disabled: [{ type: core_1.Input }]
      };
    `);
    expect(output).not.toContain('tslib');
  });

  it('should not downlevel class member with unknown decorator', () => {
    const {output} = transform(`
      export class MyDir {
        @SomeDecorator() disabled: boolean = false;
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      tslib_1.__decorate([
        SomeDecorator()
      ], MyDir.prototype, "disabled", void 0);
    `);
    expect(output).not.toContain('MyClass.propDecorators');
  });

  // Angular is not concerned with type information for decorated class members. Instead,
  // the type is omitted. This also helps with server side rendering as DOM globals which
  // are used as types, do not load at runtime. https://github.com/angular/angular/issues/30586.
  it('should downlevel Angular-decorated class member but not preserve type', () => {
    context.writeFile('/other-file.ts', `export class MyOtherClass {}`);
    const {output} = transform(`
      import {Input} from '@angular/core';
      import {MyOtherClass} from './other-file';
      
      export class MyDir {
        @Input() trigger: HTMLElement;
        @Input() fromOtherFile: MyOtherClass;
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyDir.propDecorators = {
        trigger: [{ type: core_1.Input }],
        fromOtherFile: [{ type: core_1.Input }]
      };
    `);
    expect(output).not.toContain('HTMLElement');
    expect(output).not.toContain('MyOtherClass');
  });

  it('should capture constructor type metadata with `emitDecoratorMetadata` enabled', () => {
    context.writeFile('/other-file.ts', `export class MyOtherClass {}`);
    const {output} = transform(
        `
      import {Directive} from '@angular/core';
      import {MyOtherClass} from './other-file';
      
      @Directive()
      export class MyDir {
        constructor(other: MyOtherClass) {}
      }
    `,
        {emitDecoratorMetadata: true});

    expect(diagnostics.length).toBe(0);
    expect(output).toContain('const other_file_1 = require("./other-file");');
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
        { type: other_file_1.MyOtherClass }
      ];
    `);
  });

  it('should capture constructor type metadata with `emitDecoratorMetadata` disabled', () => {
    context.writeFile('/other-file.ts', `export class MyOtherClass {}`);
    const {output, dtsOutput} = transform(
        `
      import {Directive} from '@angular/core';
      import {MyOtherClass} from './other-file';
      
      @Directive()
      export class MyDir {
        constructor(other: MyOtherClass) {}
      }
    `,
        {emitDecoratorMetadata: false});

    expect(diagnostics.length).toBe(0);
    expect(output).toContain('const other_file_1 = require("./other-file");');
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
        { type: other_file_1.MyOtherClass }
      ];
    `);
    expect(dtsOutput).toContain('import');
  });

  it('should properly serialize constructor parameter with external qualified name type', () => {
    context.writeFile('/other-file.ts', `export class MyOtherClass {}`);
    const {output} = transform(`
      import {Directive} from '@angular/core';
      import * as externalFile from './other-file';
      
      @Directive()
      export class MyDir {
        constructor(other: externalFile.MyOtherClass) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain('const externalFile = require("./other-file");');
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
        { type: externalFile.MyOtherClass }
      ];
    `);
  });

  it('should properly serialize constructor parameter with local qualified name type', () => {
    const {output} = transform(`
      import {Directive} from '@angular/core';
      
      namespace other {
        export class OtherClass {}
      };
      
      @Directive()
      export class MyDir {
        constructor(other: other.OtherClass) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain('var other;');
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
        { type: other.OtherClass }
      ];
    `);
  });

  it('should properly downlevel constructor parameter decorators', () => {
    const {output} = transform(`
      import {Inject, Directive, DOCUMENT} from '@angular/core';
      
      @Directive()
      export class MyDir {
        constructor(@Inject(DOCUMENT) document: Document) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
        { type: Document, decorators: [{ type: core_1.Inject, args: [core_1.DOCUMENT,] }] }
      ];
    `);
  });

  it('should properly downlevel constructor parameters with union type', () => {
    const {output} = transform(`
      import {Optional, Directive, NgZone} from '@angular/core';
      
      @Directive()
      export class MyDir {
        constructor(@Optional() ngZone: NgZone|null) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
        { type: core_1.NgZone, decorators: [{ type: core_1.Optional }] }
      ];
    `);
  });

  it('should add @nocollapse if closure compiler is enabled', () => {
    isClosureEnabled = true;
    const {output} = transform(`
      import {Directive} from '@angular/core';

      export class ClassInject {};

      @Directive()
      export class MyDir {
        constructor(v: ClassInject) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      /** @nocollapse */
      MyDir.ctorParameters = () => [
        { type: ClassInject }
      ];
    `);
    expect(output).not.toContain('tslib');
  });

  it('should not retain unused type imports due to decorator downleveling with ' +
         '`emitDecoratorMetadata` enabled.',
     () => {
       context.writeFile('/external.ts', `
      export class ErrorHandler {}
      export class ClassInject {}
    `);
       const {output} = transform(
           `
      import {Directive} from '@angular/core';
      import {ErrorHandler, ClassInject} from './external';

      @Directive()
      export class MyDir {
        private _errorHandler: ErrorHandler;
        constructor(v: ClassInject) {}
      }
    `,
           {module: ts.ModuleKind.ES2015, emitDecoratorMetadata: true});

       expect(diagnostics.length).toBe(0);
       expect(output).not.toContain('tslib');
       expect(output).not.toContain('ErrorHandler');
     });

  it('should not retain unused type imports due to decorator downleveling with ' +
         '`emitDecoratorMetadata` disabled',
     () => {
       context.writeFile('/external.ts', `
      export class ErrorHandler {}
      export class ClassInject {}
    `);
       const {output} = transform(
           `
      import {Directive} from '@angular/core';
      import {ErrorHandler, ClassInject} from './external';

      @Directive()
      export class MyDir {
        private _errorHandler: ErrorHandler;
        constructor(v: ClassInject) {}
      }
    `,
           {module: ts.ModuleKind.ES2015, emitDecoratorMetadata: false});

       expect(diagnostics.length).toBe(0);
       expect(output).not.toContain('tslib');
       expect(output).not.toContain('ErrorHandler');
     });

  it('should not generate invalid reference due to conflicting parameter name', () => {
    context.writeFile('/external.ts', `
      export class Dep {
        greet() {}
      }
    `);
    const {output} = transform(
        `
      import {Directive} from '@angular/core';
      import {Dep} from './external';

      @Directive()
      export class MyDir {
        constructor(Dep: Dep) {
          Dep.greet();
        }
      }
    `,
        {emitDecoratorMetadata: false});

    expect(diagnostics.length).toBe(0);
    expect(output).not.toContain('tslib');
    expect(output).toContain(`external_1 = require("./external");`);
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
        { type: external_1.Dep }
      ];
    `);
  });

  it('should be able to serialize circular constructor parameter type', () => {
    const {output} = transform(`
      import {Directive, Optional, Inject, SkipSelf} from '@angular/core';

      @Directive()
      export class MyDir {
        constructor(@Optional() @SkipSelf() @Inject(MyDir) parentDir: MyDir|null) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
        { type: MyDir, decorators: [{ type: core_1.Optional }, { type: core_1.SkipSelf }, { type: core_1.Inject, args: [MyDir,] }] }
      ];
    `);
  });

  it('should create diagnostic if property name is non-serializable', () => {
    transform(`
      import {Directive, ViewChild, TemplateRef} from '@angular/core';

      @Directive()
      export class MyDir {
        @ViewChild(TemplateRef) ['some' + 'name']: TemplateRef<any>|undefined;
      }
    `);

    expect(diagnostics.length).toBe(1);
    expect(diagnostics[0].messageText as string)
        .toBe(`Cannot process decorators for class element with non-analyzable name.`);
  });

  it('should not capture constructor parameter types when not resolving to a value', () => {
    context.writeFile('/external.ts', `
      export interface IState {}
      export type IOverlay = {hello: true}&IState;
      export default interface {
        hello: false;
      }
    `);
    const {output} = transform(`
      import {Directive, Inject} from '@angular/core';
      import * as angular from './external';
      import {IOverlay} from './external';
      import TypeFromDefaultImport from './external';

      @Directive()
      export class MyDir {
        constructor(@Inject('$state') param: angular.IState,
                    @Inject('$overlay') other: IOverlay,
                    @Inject('$default') default: TypeFromDefaultImport) {}
      }
    `);

    expect(diagnostics.length).toBe(0);
    expect(output).not.toContain('external');
    expect(output).toContain(dedent`
      MyDir.decorators = [
        { type: core_1.Directive }
      ];
      MyDir.ctorParameters = () => [
        { type: undefined, decorators: [{ type: core_1.Inject, args: ['$state',] }] },
        { type: undefined, decorators: [{ type: core_1.Inject, args: ['$overlay',] }] },
        { type: undefined, decorators: [{ type: core_1.Inject, args: ['$default',] }] }
      ];
    `);
  });

  it('should allow preceding custom transformers to strip decorators', () => {
    const stripAllDecoratorsTransform: ts.TransformerFactory<ts.SourceFile> = context => {
      return (sourceFile: ts.SourceFile) => {
        const visitNode = (node: ts.Node): ts.Node => {
          if (ts.isClassDeclaration(node) || ts.isClassElement(node)) {
            const cloned = ts.getMutableClone(node);
            cloned.decorators = undefined;
            return cloned;
          }
          return ts.visitEachChild(node, visitNode, context);
        };
        return visitNode(sourceFile) as ts.SourceFile;
      };
    };

    const {output} = transform(
        `
      import {Directive} from '@angular/core';
      
      export class MyInjectedClass {}

      @Directive()
      export class MyDir {
        constructor(someToken: MyInjectedClass) {}
      }
    `,
        {}, [stripAllDecoratorsTransform]);

    expect(diagnostics.length).toBe(0);
    expect(output).not.toContain('MyDir.decorators');
    expect(output).not.toContain('MyDir.ctorParameters');
    expect(output).not.toContain('tslib');
  });

  describe('class decorators skipped', () => {
    beforeEach(() => skipClassDecorators = true);

    it('should not downlevel Angular class decorators', () => {
      const {output} = transform(`
        import {Injectable} from '@angular/core';
  
        @Injectable()
        export class MyService {}
      `);

      expect(diagnostics.length).toBe(0);
      expect(output).not.toContain('MyService.decorators');
      expect(output).toContain(dedent`
        MyService = tslib_1.__decorate([
          core_1.Injectable()
        ], MyService);
      `);
    });

    it('should downlevel constructor parameters', () => {
      const {output} = transform(`
        import {Injectable} from '@angular/core';
 
        @Injectable()
        export class InjectClass {}
 
        @Injectable()
        export class MyService {
          constructor(dep: InjectClass) {}
        }
      `);

      expect(diagnostics.length).toBe(0);
      expect(output).not.toContain('MyService.decorators');
      expect(output).toContain('MyService.ctorParameters');
      expect(output).toContain(dedent`
        MyService.ctorParameters = () => [
          { type: InjectClass }
        ];
        MyService = tslib_1.__decorate([
          core_1.Injectable()
        ], MyService);
      `);
    });

    it('should downlevel constructor parameter decorators', () => {
      const {output} = transform(`
        import {Injectable, Inject} from '@angular/core';
 
        @Injectable()
        export class InjectClass {}
 
        @Injectable()
        export class MyService {
          constructor(@Inject('test') dep: InjectClass) {}
        }
      `);

      expect(diagnostics.length).toBe(0);
      expect(output).not.toContain('MyService.decorators');
      expect(output).toContain('MyService.ctorParameters');
      expect(output).toContain(dedent`
        MyService.ctorParameters = () => [
          { type: InjectClass, decorators: [{ type: core_1.Inject, args: ['test',] }] }
        ];
        MyService = tslib_1.__decorate([
          core_1.Injectable()
        ], MyService);
      `);
    });

    it('should downlevel class member Angular decorators', () => {
      const {output} = transform(`
        import {Injectable, Input} from '@angular/core';
 
        export class MyService {
          @Input() disabled: boolean;
        }
      `);

      expect(diagnostics.length).toBe(0);
      expect(output).not.toContain('tslib');
      expect(output).toContain(dedent`
        MyService.propDecorators = {
          disabled: [{ type: core_1.Input }]
        };
      `);
    });
  });
});

/** Template string function that can be used to dedent a given string literal. */
export function dedent(strings: TemplateStringsArray, ...values: any[]) {
  let joinedString = '';
  for (let i = 0; i < values.length; i++) {
    joinedString += `${strings[i]}${values[i]}`;
  }
  joinedString += strings[strings.length - 1];
  return omitLeadingWhitespace(joinedString);
}

/** Omits the leading whitespace for each line of the given text. */
function omitLeadingWhitespace(text: string): string {
  return text.replace(/^\s+/gm, '');
}
