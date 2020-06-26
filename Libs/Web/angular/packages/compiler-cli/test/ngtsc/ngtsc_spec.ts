/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {platform} from 'os';
import * as ts from 'typescript';

import {ErrorCode, ngErrorCode} from '../../src/ngtsc/diagnostics';
import {absoluteFrom} from '../../src/ngtsc/file_system';
import {runInEachFileSystem} from '../../src/ngtsc/file_system/testing';
import {LazyRoute} from '../../src/ngtsc/routing';
import {restoreTypeScriptVersionForTesting, setTypeScriptVersionForTesting} from '../../src/typescript_support';
import {loadStandardTestFiles} from '../helpers/src/mock_file_loading';

import {NgtscTestEnvironment} from './env';

const trim = (input: string): string => input.replace(/\s+/g, ' ').trim();

const varRegExp = (name: string): RegExp => new RegExp(`var \\w+ = \\[\"${name}\"\\];`);

const viewQueryRegExp = (predicate: string, descend: boolean, ref?: string): RegExp => {
  const maybeRef = ref ? `, ${ref}` : ``;
  return new RegExp(`i0\\.ɵɵviewQuery\\(${predicate}, ${descend}${maybeRef}\\)`);
};

const contentQueryRegExp = (predicate: string, descend: boolean, ref?: string): RegExp => {
  const maybeRef = ref ? `, ${ref}` : ``;
  return new RegExp(`i0\\.ɵɵcontentQuery\\(dirIndex, ${predicate}, ${descend}${maybeRef}\\)`);
};

const setClassMetadataRegExp = (expectedType: string): RegExp =>
    new RegExp(`setClassMetadata(.*?${expectedType}.*?)`);

const testFiles = loadStandardTestFiles();

function getDiagnosticSourceCode(diag: ts.Diagnostic): string {
  return diag.file!.text.substr(diag.start!, diag.length!);
}

runInEachFileSystem(os => {
  describe('ngtsc behavioral tests', () => {
    let env!: NgtscTestEnvironment;

    beforeEach(() => {
      env = NgtscTestEnvironment.setup(testFiles);
      env.tsconfig();
    });

    it('should compile Injectables without errors', () => {
      env.write('test.ts', `
        import {Injectable} from '@angular/core';

        @Injectable()
        export class Dep {}

        @Injectable()
        export class Service {
          constructor(dep: Dep) {}
        }
    `);
      env.driveMain();


      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('Dep.ɵprov =');
      expect(jsContents).toContain('Service.ɵprov =');
      expect(jsContents).not.toContain('__decorate');
      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents).toContain('static ɵprov: i0.ɵɵInjectableDef<Dep>;');
      expect(dtsContents).toContain('static ɵprov: i0.ɵɵInjectableDef<Service>;');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<Dep, never>;');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<Service, never>;');
    });

    it('should compile Injectables with a generic service', () => {
      env.write('test.ts', `
        import {Injectable} from '@angular/core';

        @Injectable()
        export class Store<T> {}
    `);

      env.driveMain();


      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('Store.ɵprov =');
      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<Store<any>, never>;');
      expect(dtsContents).toContain('static ɵprov: i0.ɵɵInjectableDef<Store<any>>;');
    });

    it('should compile Injectables with providedIn without errors', () => {
      env.write('test.ts', `
        import {Injectable} from '@angular/core';

        @Injectable()
        export class Dep {}

        @Injectable({ providedIn: 'root' })
        export class Service {
          constructor(dep: Dep) {}
        }
    `);

      env.driveMain();


      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('Dep.ɵprov =');
      expect(jsContents).toContain('Service.ɵprov =');
      expect(jsContents)
          .toContain(
              'Service.ɵfac = function Service_Factory(t) { return new (t || Service)(i0.ɵɵinject(Dep)); };');
      expect(jsContents).toContain('providedIn: \'root\' })');
      expect(jsContents).not.toContain('__decorate');
      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents).toContain('static ɵprov: i0.ɵɵInjectableDef<Dep>;');
      expect(dtsContents).toContain('static ɵprov: i0.ɵɵInjectableDef<Service>;');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<Dep, never>;');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<Service, never>;');
    });

    it('should compile Injectables with providedIn and factory without errors', () => {
      env.write('test.ts', `
        import {Injectable} from '@angular/core';

        @Injectable({ providedIn: 'root', useFactory: () => new Service() })
        export class Service {
          constructor() {}
        }
    `);

      env.driveMain();


      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('Service.ɵprov =');
      expect(jsContents)
          .toContain('factory: function () { return (function () { return new Service(); })(); }');
      expect(jsContents).toContain('Service_Factory(t) { return new (t || Service)(); }');
      expect(jsContents).toContain(', providedIn: \'root\' });');
      expect(jsContents).not.toContain('__decorate');
      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents).toContain('static ɵprov: i0.ɵɵInjectableDef<Service>;');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<Service, never>;');
    });

    it('should compile Injectables with providedIn and factory with deps without errors', () => {
      env.write('test.ts', `
        import {Injectable} from '@angular/core';

        @Injectable()
        export class Dep {}

        @Injectable({ providedIn: 'root', useFactory: (dep: Dep) => new Service(dep), deps: [Dep] })
        export class Service {
          constructor(dep: Dep) {}
        }
    `);

      env.driveMain();


      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('Service.ɵprov =');
      expect(jsContents).toContain('factory: function Service_Factory(t) { var r = null; if (t) {');
      expect(jsContents).toContain('return new (t || Service)(i0.ɵɵinject(Dep));');
      expect(jsContents)
          .toContain('r = (function (dep) { return new Service(dep); })(i0.ɵɵinject(Dep));');
      expect(jsContents).toContain('return r; }, providedIn: \'root\' });');
      expect(jsContents).not.toContain('__decorate');
      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents).toContain('static ɵprov: i0.ɵɵInjectableDef<Service>;');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<Service, never>;');
    });

    it('should compile @Injectable with an @Optional dependency', () => {
      env.write('test.ts', `
      import {Injectable, Optional as Opt} from '@angular/core';

      @Injectable()
      class Dep {}

      @Injectable()
      class Service {
        constructor(@Opt() dep: Dep) {}
      }
    `);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('inject(Dep, 8)');
    });

    it('should compile @Injectable with constructor overloads', () => {
      env.write('test.ts', `
      import {Injectable, Optional} from '@angular/core';

      @Injectable()
      class Dep {}

      @Injectable()
      class OptionalDep {}

      @Injectable()
      class Service {
        constructor(dep: Dep);

        constructor(dep: Dep, @Optional() optionalDep?: OptionalDep) {}
      }
    `);
      env.driveMain();
      const jsContents = env.getContents('test.js');

      expect(jsContents)
          .toContain(
              `Service.ɵfac = function Service_Factory(t) { ` +
              `return new (t || Service)(i0.ɵɵinject(Dep), i0.ɵɵinject(OptionalDep, 8)); };`);
    });

    it('should compile Directives without errors', () => {
      env.write('test.ts', `
        import {Directive} from '@angular/core';

        @Directive({selector: '[dir]'})
        export class TestDir {}
      `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('TestDir.ɵdir = i0.ɵɵdefineDirective');
      expect(jsContents).toContain('TestDir.ɵfac = function');
      expect(jsContents).not.toContain('__decorate');

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵdir: i0.ɵɵDirectiveDefWithMeta<TestDir, "[dir]", never, {}, {}, never>');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<TestDir, never>');
    });

    it('should compile abstract Directives without errors', () => {
      env.write('test.ts', `
        import {Directive} from '@angular/core';

        @Directive()
        export class TestDir {}
      `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('TestDir.ɵdir = i0.ɵɵdefineDirective');
      expect(jsContents).toContain('TestDir.ɵfac = function');
      expect(jsContents).not.toContain('__decorate');

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵdir: i0.ɵɵDirectiveDefWithMeta<TestDir, never, never, {}, {}, never>');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<TestDir, never>');
    });

    it('should compile Components (inline template) without errors', () => {
      env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test-cmp',
          template: 'this is a test',
        })
        export class TestCmp {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('TestCmp.ɵcmp = i0.ɵɵdefineComponent');
      expect(jsContents).toContain('TestCmp.ɵfac = function');
      expect(jsContents).not.toContain('__decorate');

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵcmp: i0.ɵɵComponentDefWithMeta<TestCmp, "test-cmp", never, {}, {}, never, never>');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<TestCmp, never>');
    });

    it('should compile Components (dynamic inline template) without errors', () => {
      env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test-cmp',
          template: 'this is ' + 'a test',
        })
        export class TestCmp {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('TestCmp.ɵcmp = i0.ɵɵdefineComponent');
      expect(jsContents).toContain('TestCmp.ɵfac = function');
      expect(jsContents).not.toContain('__decorate');

      const dtsContents = env.getContents('test.d.ts');

      expect(dtsContents)
          .toContain(
              'static ɵcmp: i0.ɵɵComponentDefWithMeta' +
              '<TestCmp, "test-cmp", never, {}, {}, never, never>');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<TestCmp, never>');
    });

    it('should compile Components (function call inline template) without errors', () => {
      env.write('test.ts', `
        import {Component} from '@angular/core';

        function getTemplate() {
          return 'this is a test';
        }
        @Component({
          selector: 'test-cmp',
          template: getTemplate(),
        })
        export class TestCmp {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('TestCmp.ɵcmp = i0.ɵɵdefineComponent');
      expect(jsContents).toContain('TestCmp.ɵfac = function');
      expect(jsContents).not.toContain('__decorate');

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵcmp: i0.ɵɵComponentDefWithMeta<TestCmp, "test-cmp", never, {}, {}, never, never>');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<TestCmp, never>');
    });

    it('should compile Components (external template) without errors', () => {
      env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test-cmp',
          templateUrl: './dir/test.html',
        })
        export class TestCmp {}
    `);
      env.write('dir/test.html', '<p>Hello World</p>');

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('Hello World');
    });

    // This test triggers the Tsickle compiler which asserts that the file-paths
    // are valid for the real OS. When on non-Windows systems it doesn't like paths
    // that start with `C:`.
    if (os !== 'Windows' || platform() === 'win32') {
      describe('when closure annotations are requested', () => {
        it('should add @nocollapse to static fields', () => {
          env.tsconfig({
            'annotateForClosureCompiler': true,
          });
          env.write('test.ts', `
            import {Component} from '@angular/core';

            @Component({
              selector: 'test-cmp',
              templateUrl: './dir/test.html',
            })
            export class TestCmp {}
          `);
          env.write('dir/test.html', '<p>Hello World</p>');

          env.driveMain();

          const jsContents = env.getContents('test.js');
          expect(jsContents).toContain('/** @nocollapse */ TestCmp.ɵcmp');
        });

        /**
         * The following set of tests verify that after Tsickle run we do not have cases
         * which trigger automatic semicolon insertion, which breaks the code. In order
         * to avoid the problem, we wrap all function expressions in certain fields
         * ("providers" and "viewProviders") in parentheses. More info on Tsickle
         * processing related to this case can be found here:
         * https://github.com/angular/tsickle/blob/d7974262571c8a17d684e5ba07680e1b1993afdd/src/jsdoc_transformer.ts#L1021
         */
        describe('wrap functions in certain fields in parentheses', () => {
          const providers = `
            [{
              provide: 'token-a',
              useFactory: (service: Service) => {
                return () => service.id;
              }
            }, {
              provide: 'token-b',
              useFactory: function(service: Service) {
                return function() {
                  return service.id;
                }
              }
            }]
          `;

          const service = `
              export class Service {
                id: string = 'service-id';
              }
            `;

          const verifyOutput = (jsContents: string) => {
            // verify that there is no pattern that triggers automatic semicolon
            // insertion by checking that there are no return statements not wrapped in
            // parentheses
            expect(trim(jsContents)).not.toContain(trim(`
              return /**
              * @return {?}
              */
            `));
            expect(trim(jsContents)).toContain(trim(`
              [{
                  provide: 'token-a',
                  useFactory: (function (service) {
                      return (/**
                      * @return {?}
                      */
                      function () { return service.id; });
                  })
              }, {
                  provide: 'token-b',
                  useFactory: (function (service) {
                      return (/**
                      * @return {?}
                      */
                      function () {
                          return service.id;
                      });
                  })
              }]
            `));
          };

          it('should wrap functions in "providers" list in NgModule', () => {
            env.tsconfig({
              'annotateForClosureCompiler': true,
            });
            env.write('service.ts', service);
            env.write('test.ts', `
              import {NgModule} from '@angular/core';
              import {Service} from './service';

              @NgModule({
                providers: ${providers}
              })
              export class SomeModule {}
            `);

            env.driveMain();
            verifyOutput(env.getContents('test.js'));
          });

          it('should wrap functions in "providers" list in Component', () => {
            env.tsconfig({
              'annotateForClosureCompiler': true,
            });
            env.write('service.ts', service);
            env.write('test.ts', `
              import {Component} from '@angular/core';
              import {Service} from './service';

              @Component({
                template: '...',
                providers: ${providers}
              })
              export class SomeComponent {}
            `);

            env.driveMain();
            verifyOutput(env.getContents('test.js'));
          });

          it('should wrap functions in "viewProviders" list in Component', () => {
            env.tsconfig({
              'annotateForClosureCompiler': true,
            });
            env.write('service.ts', service);
            env.write('test.ts', `
              import {Component} from '@angular/core';
              import {Service} from './service';

              @Component({
                template: '...',
                viewProviders: ${providers}
              })
              export class SomeComponent {}
            `);

            env.driveMain();
            verifyOutput(env.getContents('test.js'));
          });

          it('should wrap functions in "providers" list in Directive', () => {
            env.tsconfig({
              'annotateForClosureCompiler': true,
            });
            env.write('service.ts', service);
            env.write('test.ts', `
              import {Directive} from '@angular/core';
              import {Service} from './service';

              @Directive({
                providers: ${providers}
              })
              export class SomeDirective {}
            `);

            env.driveMain();
            verifyOutput(env.getContents('test.js'));
          });
        });
      });
    }

    it('should recognize aliased decorators', () => {
      env.write('test.ts', `
      import {
        Component as AngularComponent,
        Directive as AngularDirective,
        Pipe as AngularPipe,
        Injectable as AngularInjectable,
        NgModule as AngularNgModule,
        Input as AngularInput,
        Output as AngularOutput
      } from '@angular/core';

      @AngularDirective()
      export class TestBase {
        @AngularInput() input: any;
        @AngularOutput() output: any;
      }

      @AngularComponent({
        selector: 'test-component',
        template: '...'
      })
      export class TestComponent {
        @AngularInput() input: any;
        @AngularOutput() output: any;
      }

      @AngularDirective({
        selector: 'test-directive'
      })
      export class TestDirective {}

      @AngularPipe({
        name: 'test-pipe'
      })
      export class TestPipe {}

      @AngularInjectable({})
      export class TestInjectable {}

      @AngularNgModule({
        declarations: [
          TestComponent,
          TestDirective,
          TestPipe
        ],
        exports: [
          TestComponent,
          TestDirective,
          TestPipe
        ]
      })
      class MyModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('TestBase.ɵdir = i0.ɵɵdefineDirective');
      expect(jsContents).toContain('TestComponent.ɵcmp = i0.ɵɵdefineComponent');
      expect(jsContents).toContain('TestDirective.ɵdir = i0.ɵɵdefineDirective');
      expect(jsContents).toContain('TestPipe.ɵpipe = i0.ɵɵdefinePipe');
      expect(jsContents).toContain('TestInjectable.ɵprov = i0.ɵɵdefineInjectable');
      expect(jsContents).toContain('MyModule.ɵmod = i0.ɵɵdefineNgModule');
      expect(jsContents).toContain('MyModule.ɵinj = i0.ɵɵdefineInjector');
      expect(jsContents).toContain('inputs: { input: "input" }');
      expect(jsContents).toContain('outputs: { output: "output" }');
    });

    it('should pick a Pipe defined in `declarations` over imported Pipes', () => {
      env.tsconfig({});
      env.write('test.ts', `
        import {Component, Pipe, NgModule} from '@angular/core';

        // ModuleA classes

        @Pipe({name: 'number'})
        class PipeA {}

        @NgModule({
          declarations: [PipeA],
          exports: [PipeA]
        })
        class ModuleA {}

        // ModuleB classes

        @Pipe({name: 'number'})
        class PipeB {}

        @Component({
          selector: 'app',
          template: '{{ count | number }}'
        })
        export class App {}

        @NgModule({
          imports: [ModuleA],
          declarations: [PipeB, App],
        })
        class ModuleB {}
      `);

      env.driveMain();

      const jsContents = trim(env.getContents('test.js'));
      expect(jsContents).toContain('pipes: [PipeB]');
    });

    it('should respect imported module order when selecting Pipe (last imported Pipe is used)',
       () => {
         env.tsconfig({});
         env.write('test.ts', `
            import {Component, Pipe, NgModule} from '@angular/core';

            // ModuleA classes

            @Pipe({name: 'number'})
            class PipeA {}

            @NgModule({
              declarations: [PipeA],
              exports: [PipeA]
            })
            class ModuleA {}

            // ModuleB classes

            @Pipe({name: 'number'})
            class PipeB {}

            @NgModule({
              declarations: [PipeB],
              exports: [PipeB]
            })
            class ModuleB {}

            // ModuleC classes

            @Component({
              selector: 'app',
              template: '{{ count | number }}'
            })
            export class App {}

            @NgModule({
              imports: [ModuleA, ModuleB],
              declarations: [App],
            })
            class ModuleC {}
          `);

         env.driveMain();

         const jsContents = trim(env.getContents('test.js'));
         expect(jsContents).toContain('pipes: [PipeB]');
       });

    it('should add Directives and Components from `declarations` at the end of the list', () => {
      env.tsconfig({});
      env.write('test.ts', `
        import {Component, Directive, NgModule} from '@angular/core';

        // ModuleA classes

        @Directive({selector: '[dir]'})
        class DirectiveA {}

        @Component({
          selector: 'comp',
          template: '...'
        })
        class ComponentA {}

        @NgModule({
          declarations: [DirectiveA, ComponentA],
          exports: [DirectiveA, ComponentA]
        })
        class ModuleA {}

        // ModuleB classes

        @Directive({selector: '[dir]'})
        class DirectiveB {}

        @Component({
          selector: 'comp',
          template: '...',
        })
        export class ComponentB {}

        @Component({
          selector: 'app',
          template: \`
            <div dir></div>
            <comp></comp>
          \`,
        })
        export class App {}

        @NgModule({
          imports: [ModuleA],
          declarations: [DirectiveB, ComponentB, App],
        })
        class ModuleB {}
      `);

      env.driveMain();

      const jsContents = trim(env.getContents('test.js'));
      expect(jsContents).toContain('directives: [DirectiveA, DirectiveB, ComponentA, ComponentB]');
    });

    it('should respect imported module order while processing Directives and Components', () => {
      env.tsconfig({});
      env.write('test.ts', `
        import {Component, Directive, NgModule} from '@angular/core';

        // ModuleA classes

        @Directive({selector: '[dir]'})
        class DirectiveA {}

        @Component({
          selector: 'comp',
          template: '...'
        })
        class ComponentA {}

        @NgModule({
          declarations: [DirectiveA, ComponentA],
          exports: [DirectiveA, ComponentA]
        })
        class ModuleA {}

        // ModuleB classes

        @Directive({selector: '[dir]'})
        class DirectiveB {}

        @Component({
          selector: 'comp',
          template: '...'
        })
        class ComponentB {}

        @NgModule({
          declarations: [DirectiveB, ComponentB],
          exports: [DirectiveB, ComponentB]
        })
        class ModuleB {}

        // ModuleC classes

        @Component({
          selector: 'app',
          template: \`
            <div dir></div>
            <comp></comp>
          \`,
        })
        export class App {}

        @NgModule({
          imports: [ModuleA, ModuleB],
          declarations: [App],
        })
        class ModuleC {}
      `);

      env.driveMain();

      const jsContents = trim(env.getContents('test.js'));
      expect(jsContents).toContain('directives: [DirectiveA, DirectiveB, ComponentA, ComponentB]');
    });

    it('should compile Components with a templateUrl in a different rootDir', () => {
      env.tsconfig({}, ['./extraRootDir']);
      env.write('extraRootDir/test.html', '<p>Hello World</p>');
      env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test-cmp',
          templateUrl: 'test.html',
        })
        export class TestCmp {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('Hello World');
    });

    it('should compile Components with an absolute templateUrl in a different rootDir', () => {
      env.tsconfig({}, ['./extraRootDir']);
      env.write('extraRootDir/test.html', '<p>Hello World</p>');
      env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test-cmp',
          templateUrl: '/test.html',
        })
        export class TestCmp {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('Hello World');
    });

    it('should compile components with styleUrls', () => {
      env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test-cmp',
          styleUrls: ['./dir/style.css'],
          template: '',
        })
        export class TestCmp {}
    `);
      env.write('dir/style.css', ':host { background-color: blue; }');

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('background-color: blue');
    });

    it('should compile components with styleUrls with fallback to .css extension', () => {
      env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test-cmp',
          styleUrls: ['./dir/style.scss'],
          template: '',
        })
        export class TestCmp {}
    `);
      env.write('dir/style.css', ':host { background-color: blue; }');

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('background-color: blue');
    });

    it('should include generic type in directive definition', () => {
      env.write('test.ts', `
        import {Directive, Input, NgModule} from '@angular/core';

        @Directive()
        export class TestBase {
          @Input() input: any;
        }
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents)
          .toContain('i0.ɵɵdefineDirective({ type: TestBase, inputs: { input: "input" } });');

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              `static ɵdir: i0.ɵɵDirectiveDefWithMeta<TestBase, never, never, { "input": "input"; }, {}, never>;`);
    });

    describe('undecorated classes using Angular features', () => {
      it('should error if @Input has been discovered',
         () => assertErrorUndecoratedClassWithField('Input'));
      it('should error if @Output has been discovered',
         () => assertErrorUndecoratedClassWithField('Output'));
      it('should error if @ViewChild has been discovered',
         () => assertErrorUndecoratedClassWithField('ViewChild'));
      it('should error if @ViewChildren has been discovered',
         () => assertErrorUndecoratedClassWithField('ViewChildren'));
      it('should error if @ContentChild has been discovered',
         () => assertErrorUndecoratedClassWithField('ContentChildren'));
      it('should error if @HostBinding has been discovered',
         () => assertErrorUndecoratedClassWithField('HostBinding'));
      it('should error if @HostListener has been discovered',
         () => assertErrorUndecoratedClassWithField('HostListener'));

      it(`should error if ngOnChanges lifecycle hook has been discovered`,
         () => assertErrorUndecoratedClassWithLifecycleHook('ngOnChanges'));
      it(`should error if ngOnInit lifecycle hook has been discovered`,
         () => assertErrorUndecoratedClassWithLifecycleHook('ngOnInit'));
      it(`should error if ngOnDestroy lifecycle hook has been discovered`,
         () => assertErrorUndecoratedClassWithLifecycleHook('ngOnDestroy'));
      it(`should error if ngDoCheck lifecycle hook has been discovered`,
         () => assertErrorUndecoratedClassWithLifecycleHook('ngDoCheck'));
      it(`should error if ngAfterViewInit lifecycle hook has been discovered`,
         () => assertErrorUndecoratedClassWithLifecycleHook('ngAfterViewInit'));
      it(`should error if ngAfterViewChecked lifecycle hook has been discovered`,
         () => assertErrorUndecoratedClassWithLifecycleHook('ngAfterViewChecked'));
      it(`should error if ngAfterContentInit lifecycle hook has been discovered`,
         () => assertErrorUndecoratedClassWithLifecycleHook('ngAfterContentInit'));
      it(`should error if ngAfterContentChecked lifecycle hook has been discovered`,
         () => assertErrorUndecoratedClassWithLifecycleHook('ngAfterContentChecked'));

      function assertErrorUndecoratedClassWithField(fieldDecoratorName: string) {
        env.write('test.ts', `
          import {Component, ${fieldDecoratorName}, NgModule} from '@angular/core';

          export class SomeBaseClass {
            @${fieldDecoratorName}() someMember: any;
          }
        `);

        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(1);
        expect(trim(errors[0].messageText as string))
            .toContain(
                'Class is using Angular features but is not decorated. Please add an explicit ' +
                'Angular decorator.');
      }

      function assertErrorUndecoratedClassWithLifecycleHook(lifecycleName: string) {
        env.write('test.ts', `
            import {Component, NgModule} from '@angular/core';

            export class SomeBaseClass {
              ${lifecycleName}() {
                // empty
              }
            }
          `);

        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(1);
        expect(trim(errors[0].messageText as string))
            .toContain(
                'Class is using Angular features but is not decorated. Please add an explicit ' +
                'Angular decorator.');
      }
    });

    it('should compile NgModules without errors', () => {
      env.write('test.ts', `
        import {Component, NgModule} from '@angular/core';

        @Component({
          selector: 'test-cmp',
          template: 'this is a test',
        })
        export class TestCmp {}

        @NgModule({
          declarations: [TestCmp],
          bootstrap: [TestCmp],
        })
        export class TestModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents)
          .toContain('i0.ɵɵdefineNgModule({ type: TestModule, bootstrap: [TestCmp] });');
      expect(jsContents)
          .toContain(
              'function () { (typeof ngJitMode === "undefined" || ngJitMode) && i0.ɵɵsetNgModuleScope(TestModule, { declarations: [TestCmp] }); })();');
      expect(jsContents)
          .toContain(
              'i0.ɵɵdefineInjector({ factory: ' +
              'function TestModule_Factory(t) { return new (t || TestModule)(); } });');

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵcmp: i0.ɵɵComponentDefWithMeta<TestCmp, "test-cmp", never, {}, {}, never, never>');
      expect(dtsContents)
          .toContain(
              'static ɵmod: i0.ɵɵNgModuleDefWithMeta<TestModule, [typeof TestCmp], never, never>');
      expect(dtsContents).not.toContain('__decorate');
    });

    it('should not emit a ɵɵsetNgModuleScope call when no scope metadata is present', () => {
      env.write('test.ts', `
        import {NgModule} from '@angular/core';

        @NgModule({})
        export class TestModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('i0.ɵɵdefineNgModule({ type: TestModule });');
      expect(jsContents).not.toContain('ɵɵsetNgModuleScope(TestModule,');
    });

    it('should emit the id when the module\'s id is a string', () => {
      env.write('test.ts', `
        import {NgModule} from '@angular/core';

        @NgModule({id: 'test'})
        export class TestModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain(`i0.ɵɵdefineNgModule({ type: TestModule, id: 'test' })`);
    });

    it('should emit the id when the module\'s id is defined as `module.id`', () => {
      env.write('index.d.ts', `
         declare const module = {id: string};
       `);
      env.write('test.ts', `
         import {NgModule} from '@angular/core';

         @NgModule({id: module.id})
         export class TestModule {}
       `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('i0.ɵɵdefineNgModule({ type: TestModule, id: module.id })');
    });

    it('should filter out directives and pipes from module exports in the injector def', () => {
      env.write('test.ts', `
      import {NgModule} from '@angular/core';
      import {RouterComp, RouterModule} from '@angular/router';
      import {Dir, OtherDir, MyPipe, Comp} from './decls';

      @NgModule({
        declarations: [OtherDir],
        exports: [OtherDir],
      })
      export class OtherModule {}

      const EXPORTS = [Dir, MyPipe, Comp, OtherModule, OtherDir, RouterModule, RouterComp];

      @NgModule({
        declarations: [Dir, MyPipe, Comp],
        imports: [OtherModule, RouterModule.forRoot()],
        exports: [EXPORTS],
      })
      export class TestModule {}
    `);
      env.write(`decls.ts`, `
      import {Component, Directive, Pipe} from '@angular/core';

      @Directive({selector: '[dir]'})
      export class Dir {}

      @Directive({selector: '[other]'})
      export class OtherDir {}

      @Pipe({name:'pipe'})
      export class MyPipe {}

      @Component({selector: 'test', template: ''})
      export class Comp {}
    `);
      env.write('node_modules/@angular/router/index.d.ts', `
      import {ɵɵComponentDefWithMeta, ModuleWithProviders, ɵɵNgModuleDefWithMeta} from '@angular/core';

      export declare class RouterComp {
        static ɵcmp: ɵɵComponentDefWithMeta<RouterComp, "lib-cmp", never, {}, {}, never>
      }

      declare class RouterModule {
        static forRoot(): ModuleWithProviders<RouterModule>;
        static ɵmod: ɵɵNgModuleDefWithMeta<RouterModule, [typeof RouterComp], never, [typeof RouterComp]>;
      }
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents)
          .toContain(
              'i0.ɵɵdefineInjector({ factory: function TestModule_Factory(t) ' +
              '{ return new (t || TestModule)(); }, imports: [[OtherModule, RouterModule.forRoot()],' +
              ' OtherModule, RouterModule] });');
    });

    it('should compile NgModules with services without errors', () => {
      env.write('test.ts', `
        import {Component, NgModule} from '@angular/core';

        export class Token {}

        @NgModule({})
        export class OtherModule {}

        @Component({
          selector: 'test-cmp',
          template: 'this is a test',
        })
        export class TestCmp {}

        @NgModule({
          declarations: [TestCmp],
          providers: [{provide: Token, useValue: 'test'}],
          imports: [OtherModule],
        })
        export class TestModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('i0.ɵɵdefineNgModule({ type: TestModule });');
      expect(jsContents)
          .toContain(
              `TestModule.ɵinj = i0.ɵɵdefineInjector({ factory: ` +
              `function TestModule_Factory(t) { return new (t || TestModule)(); }, providers: [{ provide: ` +
              `Token, useValue: 'test' }], imports: [[OtherModule]] });`);

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵmod: i0.ɵɵNgModuleDefWithMeta<TestModule, [typeof TestCmp], [typeof OtherModule], never>');
      expect(dtsContents).toContain('static ɵinj: i0.ɵɵInjectorDef');
    });

    it('should compile NgModules with factory providers without errors', () => {
      env.write('test.ts', `
        import {Component, NgModule} from '@angular/core';

        export class Token {}

        @NgModule({})
        export class OtherModule {}

        @Component({
          selector: 'test-cmp',
          template: 'this is a test',
        })
        export class TestCmp {}

        @NgModule({
          declarations: [TestCmp],
          providers: [{provide: Token, useFactory: () => new Token()}],
          imports: [OtherModule],
        })
        export class TestModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('i0.ɵɵdefineNgModule({ type: TestModule });');
      expect(jsContents)
          .toContain(
              `TestModule.ɵinj = i0.ɵɵdefineInjector({ factory: ` +
              `function TestModule_Factory(t) { return new (t || TestModule)(); }, providers: [{ provide: ` +
              `Token, useFactory: function () { return new Token(); } }], imports: [[OtherModule]] });`);

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵmod: i0.ɵɵNgModuleDefWithMeta<TestModule, [typeof TestCmp], [typeof OtherModule], never>');
      expect(dtsContents).toContain('static ɵinj: i0.ɵɵInjectorDef');
    });

    it('should compile NgModules with factory providers and deps without errors', () => {
      env.write('test.ts', `
        import {Component, NgModule} from '@angular/core';

        export class Dep {}

        export class Token {
          constructor(dep: Dep) {}
        }

        @NgModule({})
        export class OtherModule {}

        @Component({
          selector: 'test-cmp',
          template: 'this is a test',
        })
        export class TestCmp {}

        @NgModule({
          declarations: [TestCmp],
          providers: [{provide: Token, useFactory: (dep: Dep) => new Token(dep), deps: [Dep]}],
          imports: [OtherModule],
        })
        export class TestModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('i0.ɵɵdefineNgModule({ type: TestModule });');
      expect(jsContents)
          .toContain(
              `TestModule.ɵinj = i0.ɵɵdefineInjector({ factory: ` +
              `function TestModule_Factory(t) { return new (t || TestModule)(); }, providers: [{ provide: ` +
              `Token, useFactory: function (dep) { return new Token(dep); }, deps: [Dep] }], imports: [[OtherModule]] });`);

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵmod: i0.ɵɵNgModuleDefWithMeta<TestModule, [typeof TestCmp], [typeof OtherModule], never>');
      expect(dtsContents).toContain('static ɵinj: i0.ɵɵInjectorDef');
    });

    it('should compile NgModules with references to local components', () => {
      env.write('test.ts', `
      import {NgModule} from '@angular/core';
      import {Foo} from './foo';

      @NgModule({
        declarations: [Foo],
      })
      export class FooModule {}
    `);
      env.write('foo.ts', `
      import {Component} from '@angular/core';
      @Component({selector: 'foo', template: ''})
      export class Foo {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      const dtsContents = env.getContents('test.d.ts');

      expect(jsContents).toContain('import { Foo } from \'./foo\';');
      expect(jsContents).not.toMatch(/as i[0-9] from ".\/foo"/);
      expect(dtsContents).toContain('as i1 from "./foo";');
    });

    it('should compile NgModules with references to absolute components', () => {
      env.write('test.ts', `
      import {NgModule} from '@angular/core';
      import {Foo} from 'foo';

      @NgModule({
        declarations: [Foo],
      })
      export class FooModule {}
    `);
      env.write('node_modules/foo/index.ts', `
      import {Component} from '@angular/core';

      @Component({
        selector: 'foo',
        template: '',
      })
      export class Foo {
      }
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      const dtsContents = env.getContents('test.d.ts');

      expect(jsContents).toContain('import { Foo } from \'foo\';');
      expect(jsContents).not.toMatch(/as i[0-9] from "foo"/);
      expect(dtsContents).toContain('as i1 from "foo";');
    });

    it('should compile NgModules with references to forward declared bootstrap components', () => {
      env.write('test.ts', `
      import {Component, forwardRef, NgModule} from '@angular/core';

      @NgModule({
        bootstrap: [forwardRef(() => Foo)],
      })
      export class FooModule {}

      @Component({selector: 'foo', template: 'foo'})
      export class Foo {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('bootstrap: function () { return [Foo]; }');
    });

    it('should compile NgModules with references to forward declared directives', () => {
      env.write('test.ts', `
      import {Directive, forwardRef, NgModule} from '@angular/core';

      @NgModule({
        declarations: [forwardRef(() => Foo)],
      })
      export class FooModule {}

      @Directive({selector: 'foo'})
      export class Foo {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('declarations: function () { return [Foo]; }');
    });

    it('should compile NgModules with references to forward declared imports', () => {
      env.write('test.ts', `
      import {forwardRef, NgModule} from '@angular/core';

      @NgModule({
        imports: [forwardRef(() => BarModule)],
      })
      export class FooModule {}

      @NgModule({})
      export class BarModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('imports: function () { return [BarModule]; }');
    });

    it('should compile NgModules with references to forward declared exports', () => {
      env.write('test.ts', `
      import {forwardRef, NgModule} from '@angular/core';

      @NgModule({
        exports: [forwardRef(() => BarModule)],
      })
      export class FooModule {}

      @NgModule({})
      export class BarModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('exports: function () { return [BarModule]; }');
    });

    it('should compile Pipes without errors', () => {
      env.write('test.ts', `
        import {Pipe} from '@angular/core';

        @Pipe({
          name: 'test-pipe',
          pure: false,
        })
        export class TestPipe {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      const dtsContents = env.getContents('test.d.ts');

      expect(jsContents)
          .toContain(
              'TestPipe.ɵpipe = i0.ɵɵdefinePipe({ name: "test-pipe", type: TestPipe, pure: false })');
      expect(jsContents)
          .toContain(
              'TestPipe.ɵfac = function TestPipe_Factory(t) { return new (t || TestPipe)(); }');
      expect(dtsContents).toContain('static ɵpipe: i0.ɵɵPipeDefWithMeta<TestPipe, "test-pipe">;');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<TestPipe, never>;');
    });

    it('should compile pure Pipes without errors', () => {
      env.write('test.ts', `
        import {Pipe} from '@angular/core';

        @Pipe({
          name: 'test-pipe',
        })
        export class TestPipe {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      const dtsContents = env.getContents('test.d.ts');

      expect(jsContents)
          .toContain(
              'TestPipe.ɵpipe = i0.ɵɵdefinePipe({ name: "test-pipe", type: TestPipe, pure: true })');
      expect(jsContents)
          .toContain(
              'TestPipe.ɵfac = function TestPipe_Factory(t) { return new (t || TestPipe)(); }');
      expect(dtsContents).toContain('static ɵpipe: i0.ɵɵPipeDefWithMeta<TestPipe, "test-pipe">;');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<TestPipe, never>;');
    });

    it('should compile Pipes with dependencies', () => {
      env.write('test.ts', `
        import {Pipe} from '@angular/core';

        export class Dep {}

        @Pipe({
          name: 'test-pipe',
          pure: false,
        })
        export class TestPipe {
          constructor(dep: Dep) {}
        }
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('return new (t || TestPipe)(i0.ɵɵdirectiveInject(Dep));');
    });

    it('should compile Pipes with generic types', () => {
      env.write('test.ts', `
        import {Pipe} from '@angular/core';

        @Pipe({
          name: 'test-pipe',
        })
        export class TestPipe<T> {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('TestPipe.ɵpipe =');
      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain('static ɵpipe: i0.ɵɵPipeDefWithMeta<TestPipe<any>, "test-pipe">;');
      expect(dtsContents).toContain('static ɵfac: i0.ɵɵFactoryDef<TestPipe<any>, never>;');
    });

    it('should include @Pipes in @NgModule scopes', () => {
      env.write('test.ts', `
        import {Component, NgModule, Pipe} from '@angular/core';

        @Pipe({name: 'test'})
        export class TestPipe {}

        @Component({selector: 'test-cmp', template: '{{value | test}}'})
        export class TestCmp {}

        @NgModule({declarations: [TestPipe, TestCmp]})
        export class TestModule {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('pipes: [TestPipe]');

      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'i0.ɵɵNgModuleDefWithMeta<TestModule, [typeof TestPipe, typeof TestCmp], never, never>');
    });

    describe('empty and missing selectors', () => {
      it('should use default selector for Components when no selector present', () => {
        env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          template: '...',
        })
        export class TestCmp {}
      `);

        env.driveMain();

        const jsContents = env.getContents('test.js');
        expect(jsContents).toContain('selectors: [["ng-component"]]');
      });

      it('should use default selector for Components with empty string selector', () => {
        env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: '',
          template: '...',
        })
        export class TestCmp {}
      `);

        env.driveMain();

        const jsContents = env.getContents('test.js');
        expect(jsContents).toContain('selectors: [["ng-component"]]');
      });

      it('should allow directives with no selector that are not in NgModules', () => {
        env.write('main.ts', `
          import {Directive} from '@angular/core';

          @Directive({})
          export class BaseDir {}

          @Directive({})
          export abstract class AbstractBaseDir {}

          @Directive()
          export abstract class EmptyDir {}

          @Directive({
            inputs: ['a', 'b']
          })
          export class TestDirWithInputs {}
        `);
        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(0);
      });

      it('should be able to use abstract directive in other compilation units', () => {
        env.write('tsconfig.json', JSON.stringify({
          extends: './tsconfig-base.json',
          angularCompilerOptions: {enableIvy: true},
          compilerOptions: {rootDir: '.', outDir: '../node_modules/lib1_built'},
        }));
        env.write('index.ts', `
          import {Directive} from '@angular/core';

          @Directive()
          export class BaseClass {}
        `);

        expect(env.driveDiagnostics().length).toBe(0);

        env.tsconfig();
        env.write('index.ts', `
          import {NgModule, Directive} from '@angular/core';
          import {BaseClass} from 'lib1_built';

          @Directive({selector: 'my-dir'})
          export class MyDirective extends BaseClass {}

          @NgModule({declarations: [MyDirective]})
          export class AppModule {}
        `);

        expect(env.driveDiagnostics().length).toBe(0);
      });

      it('should not allow directives with no selector that are in NgModules', () => {
        env.write('main.ts', `
          import {Directive, NgModule} from '@angular/core';

          @Directive({})
          export class BaseDir {}

          @NgModule({
            declarations: [BaseDir],
          })
          export class MyModule {}
        `);
        const errors = env.driveDiagnostics();
        expect(trim(errors[0].messageText as string))
            .toContain('Directive BaseDir has no selector, please add it!');
      });

      it('should throw if Directive selector is an empty string', () => {
        env.write('test.ts', `
        import {Directive} from '@angular/core';

        @Directive({
          selector: ''
        })
        export class TestDir {}
      `);

        const errors = env.driveDiagnostics();
        expect(trim(errors[0].messageText as string))
            .toContain('Directive TestDir has no selector, please add it!');
      });
    });

    describe('error handling', () => {
      function verifyThrownError(errorCode: ErrorCode, errorMessage: string) {
        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(1);
        const {code, messageText} = errors[0];
        expect(code).toBe(ngErrorCode(errorCode));
        const text = ts.flattenDiagnosticMessageText(messageText, '\n');
        expect(trim(text)).toContain(errorMessage);
      }

      it('should throw if invalid arguments are provided in @NgModule', () => {
        env.tsconfig({});
        env.write('test.ts', `
          import {NgModule} from '@angular/core';

          @NgModule('invalidNgModuleArgumentType')
          export class MyModule {}
        `);
        verifyThrownError(
            ErrorCode.DECORATOR_ARG_NOT_LITERAL, '@NgModule argument must be an object literal');
      });

      it('should throw if multiple query decorators are used on the same field', () => {
        env.tsconfig({});
        env.write('test.ts', `
          import {Component, ContentChild} from '@angular/core';

          @Component({
            selector: 'test-cmp',
            template: '...'
          })
          export class TestCmp {
            @ContentChild('bar', {static: true})
            @ContentChild('foo')
            foo: any;
          }
        `);
        verifyThrownError(
            ErrorCode.DECORATOR_COLLISION,
            'Cannot have multiple query decorators on the same class member');
      });

      ['ViewChild', 'ViewChildren', 'ContentChild', 'ContentChildren'].forEach(decorator => {
        it(`should throw if @Input and @${decorator} decorators are applied to the same property`,
           () => {
             env.tsconfig({});
             env.write('test.ts', `
              import {Component, ${decorator}, Input} from '@angular/core';

              @Component({
                selector: 'test-cmp',
                template: '<ng-content></ng-content>'
              })
              export class TestCmp {
                @Input() @${decorator}('foo') foo: any;
              }
            `);
             verifyThrownError(
                 ErrorCode.DECORATOR_COLLISION,
                 'Cannot combine @Input decorators with query decorators');
           });

        it(`should throw if invalid options are provided in ${decorator}`, () => {
          env.tsconfig({});
          env.write('test.ts', `
            import {Component, ${decorator}, Input} from '@angular/core';

            @Component({
              selector: 'test-cmp',
              template: '...'
            })
            export class TestCmp {
              @${decorator}('foo', 'invalidOptionsArgumentType') foo: any;
            }
          `);
          verifyThrownError(
              ErrorCode.DECORATOR_ARG_NOT_LITERAL,
              `@${decorator} options must be an object literal`);
        });

        it(`should throw if @${decorator} is used on non property-type member`, () => {
          env.tsconfig({});
          env.write('test.ts', `
            import {Component, ${decorator}} from '@angular/core';

            @Component({
              selector: 'test-cmp',
              template: '...'
            })
            export class TestCmp {
              @${decorator}('foo')
              private someFn() {}
            }
          `);
          verifyThrownError(
              ErrorCode.DECORATOR_UNEXPECTED, 'Query decorator must go on a property-type member');
        });

        it(`should throw error if @${decorator} has too many arguments`, () => {
          env.tsconfig({});
          env.write('test.ts', `
            import {Component, ${decorator}} from '@angular/core';

            @Component({
              selector: 'test-cmp',
              template: '...'
            })
            export class TestCmp {
              @${decorator}('foo', {}, 'invalid-extra-arg') foo: any;
            }
          `);
          verifyThrownError(
              ErrorCode.DECORATOR_ARITY_WRONG, `@${decorator} has too many arguments`);
        });

        it(`should throw error if @${decorator} predicate argument has wrong type`, () => {
          env.tsconfig({});
          env.write('test.ts', `
            import {Component, ${decorator}} from '@angular/core';

            @Component({
              selector: 'test-cmp',
              template: '...'
            })
            export class TestCmp {
              @${decorator}({'invalid-predicate-type': true}) foo: any;
            }
          `);
          verifyThrownError(
              ErrorCode.VALUE_HAS_WRONG_TYPE, `@${decorator} predicate cannot be interpreted`);
        });

        it(`should throw error if one of @${decorator}'s predicate has wrong type`, () => {
          env.tsconfig({});
          env.write('test.ts', `
            import {Component, ${decorator}} from '@angular/core';

            @Component({
              selector: 'test-cmp',
              template: '...'
            })
            export class TestCmp {
              @${decorator}(['predicate-a', {'invalid-predicate-type': true}]) foo: any;
            }
          `);
          verifyThrownError(
              ErrorCode.VALUE_HAS_WRONG_TYPE,
              `Failed to resolve @${decorator} predicate at position 1 to a string`);
        });
      });

      ['inputs', 'outputs'].forEach(field => {
        it(`should throw error if @Directive.${field} has wrong type`, () => {
          env.tsconfig({});
          env.write('test.ts', `
            import {Directive} from '@angular/core';

            @Directive({
              selector: 'test-dir',
              ${field}: 'invalid-field-type',
            })
            export class TestDir {}
          `);
          verifyThrownError(
              ErrorCode.VALUE_HAS_WRONG_TYPE,
              `Failed to resolve @Directive.${field} to a string array`);
        });
      });

      ['ContentChild', 'ContentChildren'].forEach(decorator => {
        it(`should throw if \`descendants\` field of @${
               decorator}'s options argument has wrong type`,
           () => {
             env.tsconfig({});
             env.write('test.ts', `
              import {Component, ContentChild} from '@angular/core';

              @Component({
                selector: 'test-cmp',
                template: '...'
              })
              export class TestCmp {
                @ContentChild('foo', {descendants: 'invalid'}) foo: any;
              }
            `);
             verifyThrownError(
                 ErrorCode.VALUE_HAS_WRONG_TYPE,
                 '@ContentChild options.descendants must be a boolean');
           });
      });

      ['Input', 'Output'].forEach(decorator => {
        it(`should throw error if @${decorator} decorator argument has unsupported type`, () => {
          env.tsconfig({});
          env.write('test.ts', `
            import {Component, ${decorator}} from '@angular/core';

            @Component({
              selector: 'test-cmp',
              template: '...'
            })
            export class TestCmp {
              @${decorator}(['invalid-arg-type']) foo: any;
            }
          `);
          verifyThrownError(
              ErrorCode.VALUE_HAS_WRONG_TYPE,
              `@${decorator} decorator argument must resolve to a string`);
        });

        it(`should throw error if @${decorator} decorator has too many arguments`, () => {
          env.tsconfig({});
          env.write('test.ts', `
            import {Component, ${decorator}} from '@angular/core';

            @Component({
              selector: 'test-cmp',
              template: '...'
            })
            export class TestCmp {
              @${decorator}('name', 'invalid-extra-arg') foo: any;
            }
          `);
          verifyThrownError(
              ErrorCode.DECORATOR_ARITY_WRONG,
              `@${decorator} can have at most one argument, got 2 argument(s)`);
        });
      });

      it('should throw error if @HostBinding decorator argument has unsupported type', () => {
        env.tsconfig({});
        env.write('test.ts', `
          import {Component, HostBinding} from '@angular/core';

          @Component({
            selector: 'test-cmp',
            template: '...'
          })
          export class TestCmp {
            @HostBinding(['invalid-arg-type']) foo: any;
          }
        `);
        verifyThrownError(
            ErrorCode.VALUE_HAS_WRONG_TYPE, `@HostBinding's argument must be a string`);
      });

      it('should throw error if @HostBinding decorator has too many arguments', () => {
        env.tsconfig({});
        env.write('test.ts', `
          import {Component, HostBinding} from '@angular/core';

          @Component({
            selector: 'test-cmp',
            template: '...'
          })
          export class TestCmp {
            @HostBinding('name', 'invalid-extra-arg') foo: any;
          }
        `);
        verifyThrownError(
            ErrorCode.DECORATOR_ARITY_WRONG, '@HostBinding can have at most one argument');
      });

      it('should throw error if @Directive.host field has wrong type', () => {
        env.tsconfig({});
        env.write('test.ts', `
          import {Directive} from '@angular/core';

          @Directive({
            selector: 'test-dir',
            host: 'invalid-host-type'
          })
          export class TestDir {}
        `);
        verifyThrownError(
            ErrorCode.VALUE_HAS_WRONG_TYPE, 'Decorator host metadata must be an object');
      });

      it('should throw error if @Directive.host field is an object with values that have wrong types',
         () => {
           env.tsconfig({});
           env.write('test.ts', `
              import {Directive} from '@angular/core';

              @Directive({
                selector: 'test-dir',
                host: {'key': ['invalid-host-value']}
              })
              export class TestDir {}
            `);
           verifyThrownError(
               ErrorCode.VALUE_HAS_WRONG_TYPE,
               'Decorator host metadata must be a string -> string object, but found unparseable value');
         });

      it('should throw error if @Directive.queries field has wrong type', () => {
        env.tsconfig({});
        env.write('test.ts', `
          import {Directive} from '@angular/core';

          @Directive({
            selector: 'test-dir',
            queries: 'invalid-queries-type'
          })
          export class TestDir {}
        `);
        verifyThrownError(
            ErrorCode.VALUE_HAS_WRONG_TYPE, 'Decorator queries metadata must be an object');
      });

      it('should throw error if @Directive.queries object has incorrect values', () => {
        env.tsconfig({});
        env.write('test.ts', `
          import {Directive} from '@angular/core';

          @Directive({
            selector: 'test-dir',
            queries: {
              myViewQuery: 'invalid-query-type'
            }
          })
          export class TestDir {}
        `);
        verifyThrownError(
            ErrorCode.VALUE_HAS_WRONG_TYPE,
            'Decorator query metadata must be an instance of a query type');
      });

      it('should throw error if @Directive.queries object has incorrect values (refs to other decorators)',
         () => {
           env.tsconfig({});
           env.write('test.ts', `
              import {Directive, Input} from '@angular/core';

              @Directive({
                selector: 'test-dir',
                queries: {
                  myViewQuery: new Input()
                }
              })
              export class TestDir {}
            `);
           verifyThrownError(
               ErrorCode.VALUE_HAS_WRONG_TYPE,
               'Decorator query metadata must be an instance of a query type');
         });

      it('should throw error if @Injectable has incorrect argument', () => {
        env.tsconfig({});
        env.write('test.ts', `
          import {Injectable} from '@angular/core';

          @Injectable('invalid')
          export class TestProvider {}
        `);
        verifyThrownError(
            ErrorCode.DECORATOR_ARG_NOT_LITERAL, '@Injectable argument must be an object literal');
      });
    });

    describe('multiple decorators on classes', () => {
      it('should compile @Injectable on Components, Directives, Pipes, and Modules', () => {
        env.write('test.ts', `
        import {Component, Directive, Injectable, NgModule, Pipe} from '@angular/core';

        @Component({selector: 'test', template: 'test'})
        @Injectable()
        export class TestCmp {}

        @Directive({selector: 'test'})
        @Injectable()
        export class TestDir {}

        @Pipe({name: 'test'})
        @Injectable()
        export class TestPipe {}

        @NgModule({declarations: [TestCmp, TestDir, TestPipe]})
        @Injectable()
        export class TestNgModule {}
      `);

        env.driveMain();
        const jsContents = env.getContents('test.js');
        const dtsContents = env.getContents('test.d.ts');

        // Validate that each class has the primary definition.
        expect(jsContents).toContain('TestCmp.ɵcmp =');
        expect(jsContents).toContain('TestDir.ɵdir =');
        expect(jsContents).toContain('TestPipe.ɵpipe =');
        expect(jsContents).toContain('TestNgModule.ɵmod =');

        // Validate that each class also has an injectable definition.
        expect(jsContents).toContain('TestCmp.ɵprov =');
        expect(jsContents).toContain('TestDir.ɵprov =');
        expect(jsContents).toContain('TestPipe.ɵprov =');
        expect(jsContents).toContain('TestNgModule.ɵprov =');

        // Validate that each class's .d.ts declaration has the primary definition.
        expect(dtsContents).toContain('ComponentDefWithMeta<TestCmp');
        expect(dtsContents).toContain('DirectiveDefWithMeta<TestDir');
        expect(dtsContents).toContain('PipeDefWithMeta<TestPipe');
        expect(dtsContents).toContain('ɵɵNgModuleDefWithMeta<TestNgModule');

        // Validate that each class's .d.ts declaration also has an injectable
        // definition.
        expect(dtsContents).toContain('InjectableDef<TestCmp');
        expect(dtsContents).toContain('InjectableDef<TestDir');
        expect(dtsContents).toContain('InjectableDef<TestPipe');
        expect(dtsContents).toContain('InjectableDef<TestNgModule');
      });

      it('should not compile a component and a directive annotation on the same class', () => {
        env.write('test.ts', `
        import {Component, Directive} from '@angular/core';

        @Component({selector: 'test', template: 'test'})
        @Directive({selector: 'test'})
        class ShouldNotCompile {}
      `);

        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(1);
        expect(errors[0].messageText).toContain('Two incompatible decorators on class');
      });



      it('should leave decorators present on jit: true directives', () => {
        env.write('test.ts', `
        import {Directive, Inject} from '@angular/core';

        @Directive({
          selector: 'test',
          jit: true,
        })
        export class Test {
          constructor(@Inject('foo') foo: string) {}
        }
      `);
        env.driveMain();
        const jsContents = env.getContents('test.js');
        expect(jsContents).toContain('Directive({');
        expect(jsContents).toContain('__param(0, Inject');
      });
    });

    describe('compiling invalid @Injectables', () => {
      describe('with strictInjectionParameters = true', () => {
        it('should give a compile-time error if an invalid @Injectable is used with no arguments',
           () => {
             env.tsconfig({strictInjectionParameters: true});
             env.write('test.ts', `
            import {Injectable} from '@angular/core';

            @Injectable()
            export class Test {
              constructor(private notInjectable: string) {}
            }
          `);

             const errors = env.driveDiagnostics();
             expect(errors.length).toBe(1);
             expect(errors[0].messageText).toContain('No suitable injection token for parameter');
           });

        it('should give a compile-time error if an invalid @Injectable is used with an argument',
           () => {
             env.tsconfig({strictInjectionParameters: true});
             env.write('test.ts', `
            import {Injectable} from '@angular/core';

            @Injectable({providedIn: 'root'})
            export class Test {
              constructor(private notInjectable: string) {}
            }
          `);

             const errors = env.driveDiagnostics();
             expect(errors.length).toBe(1);
             expect(errors[0].messageText).toContain('No suitable injection token for parameter');
           });

        it('should not give a compile-time error if an invalid @Injectable is used with useValue',
           () => {
             env.tsconfig({strictInjectionParameters: true});
             env.write('test.ts', `
               import {Injectable} from '@angular/core';

               @Injectable({
                 providedIn: 'root',
                 useValue: '42',
               })
               export class Test {
                 constructor(private notInjectable: string) {}
               }
             `);

             env.driveMain();
             const jsContents = env.getContents('test.js');
             expect(jsContents)
                 .toMatch(/function Test_Factory\(t\) { i0\.ɵɵinvalidFactory\(\)/ms);
           });

        it('should not give a compile-time error if an invalid @Injectable is used with useFactory',
           () => {
             env.tsconfig({strictInjectionParameters: true});
             env.write('test.ts', `
               import {Injectable} from '@angular/core';

               @Injectable({
                 providedIn: 'root',
                 useFactory: () => '42',
               })
               export class Test {
                 constructor(private notInjectable: string) {}
               }
             `);

             env.driveMain();
             const jsContents = env.getContents('test.js');
             expect(jsContents)
                 .toMatch(/function Test_Factory\(t\) { i0\.ɵɵinvalidFactory\(\)/ms);
           });

        it('should not give a compile-time error if an invalid @Injectable is used with useExisting',
           () => {
             env.tsconfig({strictInjectionParameters: true});
             env.write('test.ts', `
               import {Injectable} from '@angular/core';

               export class MyService {}

               @Injectable({
                 providedIn: 'root',
                 useExisting: MyService,
               })
               export class Test {
                 constructor(private notInjectable: string) {}
               }
             `);

             env.driveMain();
             const jsContents = env.getContents('test.js');
             expect(jsContents)
                 .toMatch(/function Test_Factory\(t\) { i0\.ɵɵinvalidFactory\(\)/ms);
           });

        it('should not give a compile-time error if an invalid @Injectable is used with useClass',
           () => {
             env.tsconfig({strictInjectionParameters: true});
             env.write('test.ts', `
               import {Injectable} from '@angular/core';

               export class MyService {}

               @Injectable({
                 providedIn: 'root',
                 useClass: MyService,
               })
               export class Test {
                 constructor(private notInjectable: string) {}
               }
             `);

             env.driveMain();
             const jsContents = env.getContents('test.js');
             expect(jsContents)
                 .toMatch(/function Test_Factory\(t\) { i0\.ɵɵinvalidFactory\(\)/ms);
           });
      });

      describe('with strictInjectionParameters = false', () => {
        it('should compile an @Injectable on a class with a non-injectable constructor', () => {
          env.tsconfig({strictInjectionParameters: false});
          env.write('test.ts', `
            import {Injectable} from '@angular/core';

            @Injectable()
            export class Test {
              constructor(private notInjectable: string) {}
            }
          `);

          env.driveMain();
          const jsContents = env.getContents('test.js');
          expect(jsContents)
              .toContain('Test.ɵfac = function Test_Factory(t) { i0.ɵɵinvalidFactory()');
        });

        it('should compile an @Injectable provided in the root on a class with a non-injectable constructor',
           () => {
             env.tsconfig({strictInjectionParameters: false});
             env.write('test.ts', `
              import {Injectable} from '@angular/core';
              @Injectable({providedIn: 'root'})
              export class Test {
                constructor(private notInjectable: string) {}
              }
            `);

             env.driveMain();
             const jsContents = env.getContents('test.js');
             expect(jsContents)
                 .toContain('Test.ɵfac = function Test_Factory(t) { i0.ɵɵinvalidFactory()');
           });
      });
    });

    describe('compiling invalid @Directives', () => {
      describe('directives with a selector', () => {
        it('should give a compile-time error if an invalid constructor is used', () => {
          env.tsconfig({strictInjectionParameters: true});
          env.write('test.ts', `
            import {Directive} from '@angular/core';

            @Directive({selector: 'app-test'})
            export class Test {
              constructor(private notInjectable: string) {}
            }
          `);

          const errors = env.driveDiagnostics();
          expect(errors.length).toBe(1);
          expect(errors[0].messageText).toContain('No suitable injection token for parameter');
        });
      });

      describe('abstract directives', () => {
        it('should generate a factory function that throws', () => {
          env.tsconfig({strictInjectionParameters: false});
          env.write('test.ts', `
          import {Directive} from '@angular/core';

          @Directive()
          export class Test {
            constructor(private notInjectable: string) {}
          }
        `);

          env.driveMain();
          const jsContents = env.getContents('test.js');
          expect(jsContents)
              .toContain('Test.ɵfac = function Test_Factory(t) { i0.ɵɵinvalidFactory()');
        });
      });

      it('should generate a factory function that throws, even under strictInjectionParameters',
         () => {
           env.tsconfig({strictInjectionParameters: true});
           env.write('test.ts', `
        import {Directive} from '@angular/core';

        @Directive()
        export class Test {
          constructor(private notInjectable: string) {}
        }
      `);

           env.driveMain();
           const jsContents = env.getContents('test.js');
           expect(jsContents)
               .toContain('Test.ɵfac = function Test_Factory(t) { i0.ɵɵinvalidFactory()');
         });
    });

    describe('templateUrl and styleUrls processing', () => {
      const testsForResource = (resource: string) => [
          // [component location, resource location, resource reference]

          // component and resource are in the same folder
          [`a/app.ts`, `a/${resource}`, `./${resource}`],  //
          [`a/app.ts`, `a/${resource}`, resource],         //
          [`a/app.ts`, `a/${resource}`, `/a/${resource}`],

          // resource is one level up
          [`a/app.ts`, resource, `../${resource}`],  //
          [`a/app.ts`, resource, `/${resource}`],

          // component and resource are in different folders
          [`a/app.ts`, `b/${resource}`, `../b/${resource}`],  //
          [`a/app.ts`, `b/${resource}`, `/b/${resource}`],

          // resource is in subfolder of component directory
          [`a/app.ts`, `a/b/c/${resource}`, `./b/c/${resource}`],  //
          [`a/app.ts`, `a/b/c/${resource}`, `b/c/${resource}`],    //
          [`a/app.ts`, `a/b/c/${resource}`, `/a/b/c/${resource}`],
      ];

      testsForResource('style.css').forEach((test) => {
        const [compLoc, styleLoc, styleRef] = test;
        it(`should handle ${styleRef}`, () => {
          env.write(styleLoc, ':host { background-color: blue; }');
          env.write(compLoc, `
          import {Component} from '@angular/core';

          @Component({
            selector: 'test-cmp',
            styleUrls: ['${styleRef}'],
            template: '...',
          })
          export class TestCmp {}
        `);

          env.driveMain();

          const jsContents = env.getContents(compLoc.replace('.ts', '.js'));
          expect(jsContents).toContain('background-color: blue');
        });
      });

      testsForResource('template.html').forEach((test) => {
        const [compLoc, templateLoc, templateRef] = test;
        it(`should handle ${templateRef}`, () => {
          env.write(templateLoc, 'Template Content');
          env.write(compLoc, `
          import {Component} from '@angular/core';

          @Component({
            selector: 'test-cmp',
            templateUrl: '${templateRef}'
          })
          export class TestCmp {}
        `);

          env.driveMain();

          const jsContents = env.getContents(compLoc.replace('.ts', '.js'));
          expect(jsContents).toContain('Template Content');
        });
      });
    });

    describe('former View Engine AST transform bugs', () => {
      it('should compile array literals behind conditionals', () => {
        env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test',
          template: '{{value ? "yes" : [no]}}',
        })
        class TestCmp {
          value = true;
          no = 'no';
        }
      `);

        env.driveMain();
        expect(env.getContents('test.js')).toContain('i0.ɵɵpureFunction1');
      });

      it('should compile array literals inside function arguments', () => {
        env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test',
          template: '{{fn([test])}}',
        })
        class TestCmp {
          fn(arg: any): string {
            return 'test';
          }

          test = 'test';
        }
      `);

        env.driveMain();
        expect(env.getContents('test.js')).toContain('i0.ɵɵpureFunction1');
      });
    });

    describe('unwrapping ModuleWithProviders functions', () => {
      it('should use a local ModuleWithProviders-annotated return type if a function is not statically analyzable',
         () => {
           env.write(`module.ts`, `
            import {NgModule, ModuleWithProviders} from '@angular/core';

            export function notStaticallyAnalyzable(): ModuleWithProviders<SomeModule> {
              console.log('this interferes with static analysis');
              return {
                ngModule: SomeModule,
                providers: [],
              };
            }

            @NgModule()
            export class SomeModule {}
          `);

           env.write('test.ts', `
            import {NgModule} from '@angular/core';
            import {notStaticallyAnalyzable} from './module';

            @NgModule({
              imports: [notStaticallyAnalyzable()]
            })
            export class TestModule {}
          `);

           env.driveMain();

           const jsContents = env.getContents('test.js');
           expect(jsContents).toContain('imports: [notStaticallyAnalyzable()]');

           const dtsContents = env.getContents('test.d.ts');
           expect(dtsContents).toContain(`import * as i1 from "./module";`);
           expect(dtsContents)
               .toContain(
                   'i0.ɵɵNgModuleDefWithMeta<TestModule, never, [typeof i1.SomeModule], never>');
         });

      it('should extract the generic type and include it in the module\'s declaration', () => {
        env.write(`test.ts`, `
        import {NgModule} from '@angular/core';
        import {RouterModule} from 'router';

        @NgModule({imports: [RouterModule.forRoot()]})
        export class TestModule {}
    `);

        env.write('node_modules/router/index.d.ts', `
        import {ModuleWithProviders, ɵɵNgModuleDefWithMeta} from '@angular/core';

        declare class RouterModule {
          static forRoot(): ModuleWithProviders<RouterModule>;
          static ɵmod: ɵɵNgModuleDefWithMeta<RouterModule, never, never, never>;
        }
    `);

        env.driveMain();

        const jsContents = env.getContents('test.js');
        expect(jsContents).toContain('imports: [[RouterModule.forRoot()]]');

        const dtsContents = env.getContents('test.d.ts');
        expect(dtsContents).toContain(`import * as i1 from "router";`);
        expect(dtsContents)
            .toContain(
                'i0.ɵɵNgModuleDefWithMeta<TestModule, never, [typeof i1.RouterModule], never>');
      });

      it('should throw if ModuleWithProviders is missing its generic type argument', () => {
        env.write(`test.ts`, `
          import {NgModule} from '@angular/core';
          import {RouterModule} from 'router';

          @NgModule({imports: [RouterModule.forRoot()]})
          export class TestModule {}
        `);

        env.write('node_modules/router/index.d.ts', `
          import {ModuleWithProviders, ɵɵNgModuleDefWithMeta} from '@angular/core';

          declare class RouterModule {
            static forRoot(): ModuleWithProviders;
            static ɵmod: ɵɵNgModuleDefWithMeta<RouterModule, never, never, never>;
          }
        `);
        const errors = env.driveDiagnostics();
        expect(trim(errors[0].messageText as string))
            .toContain(
                `RouterModule.forRoot returns a ModuleWithProviders type without a generic type argument. ` +
                `Please add a generic type argument to the ModuleWithProviders type. If this ` +
                `occurrence is in library code you don't control, please contact the library authors.`);
      });

      it('should extract the generic type if it is provided as qualified type name', () => {
        env.write(`test.ts`, `
        import {NgModule} from '@angular/core';
        import {RouterModule} from 'router';

        @NgModule({imports: [RouterModule.forRoot()]})
        export class TestModule {}
    `);

        env.write('node_modules/router/index.d.ts', `
        import {ModuleWithProviders} from '@angular/core';
        import * as internal from './internal';
        export {InternalRouterModule} from './internal';

        declare export class RouterModule {
          static forRoot(): ModuleWithProviders<internal.InternalRouterModule>;
        }

    `);

        env.write('node_modules/router/internal.d.ts', `
        import {ɵɵNgModuleDefWithMeta} from '@angular/core';
        export declare class InternalRouterModule {
          static ɵmod: ɵɵNgModuleDefWithMeta<InternalRouterModule, never, never, never>;
        }
    `);

        env.driveMain();

        const jsContents = env.getContents('test.js');
        expect(jsContents).toContain('imports: [[RouterModule.forRoot()]]');

        const dtsContents = env.getContents('test.d.ts');
        expect(dtsContents).toContain(`import * as i1 from "router";`);
        expect(dtsContents)
            .toContain(
                'i0.ɵɵNgModuleDefWithMeta<TestModule, never, [typeof i1.InternalRouterModule], never>');
      });

      it('should extract the generic type if it is provided as qualified type name from another package',
         () => {
           env.write(`test.ts`, `
            import {NgModule} from '@angular/core';
            import {RouterModule} from 'router';

            @NgModule({imports: [RouterModule.forRoot()]})
            export class TestModule {}`);

           env.write('node_modules/router/index.d.ts', `
            import {ModuleWithProviders} from '@angular/core';
            import * as router2 from 'router2';

            declare export class RouterModule {
              static forRoot(): ModuleWithProviders<router2.Router2Module>;
            }`);

           env.write('node_modules/router2/index.d.ts', `
            import {ɵɵNgModuleDefWithMeta} from '@angular/core';
            export declare class Router2Module {
              static ɵmod: ɵɵNgModuleDefWithMeta<Router2Module, never, never, never>;
            }`);

           env.driveMain();

           const jsContents = env.getContents('test.js');
           expect(jsContents).toContain('imports: [[RouterModule.forRoot()]]');

           const dtsContents = env.getContents('test.d.ts');
           expect(dtsContents).toContain(`import * as i1 from "router2";`);
           expect(dtsContents)
               .toContain(
                   'i0.ɵɵNgModuleDefWithMeta<TestModule, never, [typeof i1.Router2Module], never>');
         });

      it('should not reference a constant with a ModuleWithProviders value in module def imports',
         () => {
           env.write('dep.d.ts', `
          import {ModuleWithProviders, ɵɵNgModuleDefWithMeta as ɵɵNgModuleDefWithMeta} from '@angular/core';

          export declare class DepModule {
            static forRoot(arg1: any, arg2: any): ModuleWithProviders<DepModule>;
            static ɵmod: ɵɵNgModuleDefWithMeta<DepModule, never, never, never>;
          }
        `);
           env.write('test.ts', `
          import {NgModule, ModuleWithProviders} from '@angular/core';
          import {DepModule} from './dep';

          @NgModule({})
          export class Base {}

          const mwp = DepModule.forRoot(1,2);

          @NgModule({
            imports: [mwp],
          })
          export class Module {}
        `);
           env.driveMain();
           const jsContents = env.getContents('test.js');
           expect(jsContents).toContain('imports: [i1.DepModule]');
         });
    });

    it('should unwrap a ModuleWithProviders-like function if a matching literal type is provided for it',
       () => {
         env.write(`test.ts`, `
      import {NgModule} from '@angular/core';
      import {RouterModule} from 'router';

      @NgModule({imports: [RouterModule.forRoot()]})
      export class TestModule {}
  `);

         env.write('node_modules/router/index.d.ts', `
      import {ModuleWithProviders, ɵɵNgModuleDefWithMeta} from '@angular/core';

      export interface MyType extends ModuleWithProviders {}

      declare class RouterModule {
        static forRoot(): (MyType)&{ngModule:RouterModule};
        static ɵmod: ɵɵNgModuleDefWithMeta<RouterModule, never, never, never>;
      }
  `);

         env.driveMain();

         const jsContents = env.getContents('test.js');
         expect(jsContents).toContain('imports: [[RouterModule.forRoot()]]');

         const dtsContents = env.getContents('test.d.ts');
         expect(dtsContents).toContain(`import * as i1 from "router";`);
         expect(dtsContents)
             .toContain(
                 'i0.ɵɵNgModuleDefWithMeta<TestModule, never, [typeof i1.RouterModule], never>');
       });

    it('should unwrap a namespace imported ModuleWithProviders function if a generic type is provided for it',
       () => {
         env.write(`test.ts`, `
        import {NgModule} from '@angular/core';
        import {RouterModule} from 'router';

        @NgModule({imports: [RouterModule.forRoot()]})
        export class TestModule {}
    `);

         env.write('node_modules/router/index.d.ts', `
        import * as core from '@angular/core';
        import {RouterModule} from 'router';

        declare class RouterModule {
          static forRoot(): core.ModuleWithProviders<RouterModule>;
          static ɵmod: ɵɵNgModuleDefWithMeta<RouterModule, never, never, never>;
        }
    `);

         env.driveMain();

         const jsContents = env.getContents('test.js');
         expect(jsContents).toContain('imports: [[RouterModule.forRoot()]]');

         const dtsContents = env.getContents('test.d.ts');
         expect(dtsContents).toContain(`import * as i1 from "router";`);
         expect(dtsContents)
             .toContain(
                 'i0.ɵɵNgModuleDefWithMeta<TestModule, never, [typeof i1.RouterModule], never>');
       });

    it('should inject special types according to the metadata', () => {
      env.write(`test.ts`, `
        import {
          Attribute,
          ChangeDetectorRef,
          Component,
          ElementRef,
          Injector,
          Renderer2,
          TemplateRef,
          ViewContainerRef,
        } from '@angular/core';

        @Component({
          selector: 'test',
          template: 'Test',
        })
        class FooCmp {
          constructor(
            @Attribute("test") attr: string,
            cdr: ChangeDetectorRef,
            er: ElementRef,
            i: Injector,
            r2: Renderer2,
            tr: TemplateRef,
            vcr: ViewContainerRef,
          ) {}
        }
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents)
          .toContain(
              `FooCmp.ɵfac = function FooCmp_Factory(t) { return new (t || FooCmp)(i0.ɵɵinjectAttribute("test"), i0.ɵɵdirectiveInject(i0.ChangeDetectorRef), i0.ɵɵdirectiveInject(i0.ElementRef), i0.ɵɵdirectiveInject(i0.Injector), i0.ɵɵdirectiveInject(i0.Renderer2), i0.ɵɵdirectiveInject(i0.TemplateRef), i0.ɵɵdirectiveInject(i0.ViewContainerRef)); }`);
    });

    it('should include constructor dependency metadata for directives/components/pipes', () => {
      env.write(`test.ts`, `
        import {Attribute, Component, Directive, Pipe, Self, SkipSelf, Host, Optional} from '@angular/core';

        export class MyService {}
        export function dynamic() {};

        @Directive()
        export class WithDecorators {
          constructor(
            @Self() withSelf: MyService,
            @SkipSelf() withSkipSelf: MyService,
            @Host() withHost: MyService,
            @Optional() withOptional: MyService,
            @Attribute("attr") withAttribute: string,
            @Attribute(dynamic()) withAttributeDynamic: string,
            @Optional() @SkipSelf() @Host() withMany: MyService,
            noDecorators: MyService) {}
        }

        @Directive()
        export class NoCtor {}

        @Directive()
        export class EmptyCtor {
          constructor() {}
        }

        @Directive()
        export class WithoutDecorators {
          constructor(noDecorators: MyService) {}
        }

        @Component({ template: 'test' })
        export class MyCmp {
          constructor(@Host() withHost: MyService) {}
        }

        @Pipe({ name: 'test' })
        export class MyPipe {
          constructor(@Host() withHost: MyService) {}
        }
    `);

      env.driveMain();
      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵfac: i0.ɵɵFactoryDef<WithDecorators, [' +
              '{ self: true; }, { skipSelf: true; }, { host: true; }, ' +
              '{ optional: true; }, { attribute: "attr"; }, { attribute: unknown; }, ' +
              '{ optional: true; host: true; skipSelf: true; }, null]>');
      expect(dtsContents).toContain(`static ɵfac: i0.ɵɵFactoryDef<NoCtor, never>`);
      expect(dtsContents).toContain(`static ɵfac: i0.ɵɵFactoryDef<EmptyCtor, never>`);
      expect(dtsContents).toContain(`static ɵfac: i0.ɵɵFactoryDef<WithoutDecorators, never>`);
      expect(dtsContents).toContain(`static ɵfac: i0.ɵɵFactoryDef<MyCmp, [{ host: true; }]>`);
      expect(dtsContents).toContain(`static ɵfac: i0.ɵɵFactoryDef<MyPipe, [{ host: true; }]>`);
    });

    it('should include constructor dependency metadata for @Injectable', () => {
      env.write(`test.ts`, `
        import {Injectable, Self, Host} from '@angular/core';

        export class MyService {}

        @Injectable()
        export class Inj {
          constructor(@Self() service: MyService) {}
        }

        @Injectable({ useExisting: MyService })
        export class InjUseExisting {
          constructor(@Self() service: MyService) {}
        }

        @Injectable({ useClass: MyService })
        export class InjUseClass {
          constructor(@Self() service: MyService) {}
        }

        @Injectable({ useClass: MyService, deps: [[new Host(), MyService]] })
        export class InjUseClassWithDeps {
          constructor(@Self() service: MyService) {}
        }

        @Injectable({ useFactory: () => new Injectable(new MyService()) })
        export class InjUseFactory {
          constructor(@Self() service: MyService) {}
        }

        @Injectable({ useFactory: (service: MyService) => new Injectable(service), deps: [[new Host(), MyService]] })
        export class InjUseFactoryWithDeps {
          constructor(@Self() service: MyService) {}
        }

        @Injectable({ useValue: new Injectable(new MyService()) })
        export class InjUseValue {
          constructor(@Self() service: MyService) {}
        }
    `);

      env.driveMain();
      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents).toContain(`static ɵfac: i0.ɵɵFactoryDef<Inj, [{ self: true; }]>`);
      expect(dtsContents)
          .toContain(`static ɵfac: i0.ɵɵFactoryDef<InjUseExisting, [{ self: true; }]>`);
      expect(dtsContents).toContain(`static ɵfac: i0.ɵɵFactoryDef<InjUseClass, [{ self: true; }]>`);
      expect(dtsContents)
          .toContain(`static ɵfac: i0.ɵɵFactoryDef<InjUseClassWithDeps, [{ self: true; }]>`);
      expect(dtsContents)
          .toContain(`static ɵfac: i0.ɵɵFactoryDef<InjUseFactory, [{ self: true; }]>`);
      expect(dtsContents)
          .toContain(`static ɵfac: i0.ɵɵFactoryDef<InjUseFactoryWithDeps, [{ self: true; }]>`);
      expect(dtsContents).toContain(`static ɵfac: i0.ɵɵFactoryDef<InjUseValue, [{ self: true; }]>`);
    });

    it('should include ng-content selectors in the metadata', () => {
      env.write(`test.ts`, `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test',
          template: '<ng-content></ng-content> <ng-content select=".foo"></ng-content>',
        })
        export class TestCmp {
        }
    `);

      env.driveMain();
      const dtsContents = env.getContents('test.d.ts');
      expect(dtsContents)
          .toContain(
              'static ɵcmp: i0.ɵɵComponentDefWithMeta<TestCmp, "test", never, {}, {}, never, ["*", ".foo"]>');
    });

    it('should generate queries for components', () => {
      env.write(`test.ts`, `
        import {Component, ContentChild, ContentChildren, TemplateRef, ViewChild} from '@angular/core';

        @Component({
          selector: 'test',
          template: '<div #foo></div>',
          queries: {
            'mview': new ViewChild('test1'),
            'mcontent': new ContentChild('test2'),
          }
        })
        class FooCmp {
          @ContentChild('bar', {read: TemplateRef}) child: any;
          @ContentChildren(TemplateRef) children: any;
          get aview(): any { return null; }
          @ViewChild('accessor') set aview(value: any) {}
        }
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toMatch(varRegExp('bar'));
      expect(jsContents).toMatch(varRegExp('test1'));
      expect(jsContents).toMatch(varRegExp('test2'));
      expect(jsContents).toMatch(varRegExp('accessor'));
      // match `i0.ɵɵcontentQuery(dirIndex, _c1, true, TemplateRef)`
      expect(jsContents).toMatch(contentQueryRegExp('\\w+', true, 'TemplateRef'));
      // match `i0.ɵɵviewQuery(_c2, true, null)`
      expect(jsContents).toMatch(viewQueryRegExp('\\w+', true));
    });

    it('should generate queries for directives', () => {
      env.write(`test.ts`, `
        import {Directive, ContentChild, ContentChildren, TemplateRef, ViewChild} from '@angular/core';

        @Directive({
          selector: '[test]',
          queries: {
            'mview': new ViewChild('test1'),
            'mcontent': new ContentChild('test2'),
          }
        })
        class FooCmp {
          @ContentChild('bar', {read: TemplateRef}) child: any;
          @ContentChildren(TemplateRef) children: any;
          get aview(): any { return null; }
          @ViewChild('accessor') set aview(value: any) {}
        }
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toMatch(varRegExp('bar'));
      expect(jsContents).toMatch(varRegExp('test1'));
      expect(jsContents).toMatch(varRegExp('test2'));
      expect(jsContents).toMatch(varRegExp('accessor'));
      // match `i0.ɵɵcontentQuery(dirIndex, _c1, true, TemplateRef)`
      expect(jsContents).toMatch(contentQueryRegExp('\\w+', true, 'TemplateRef'));

      // match `i0.ɵɵviewQuery(_c2, true)`
      // Note that while ViewQuery doesn't necessarily make sense on a directive,
      // because it doesn't have a view, we still need to handle it because a component
      // could extend the directive.
      expect(jsContents).toMatch(viewQueryRegExp('\\w+', true));
    });

    it('should handle queries that use forwardRef', () => {
      env.write(`test.ts`, `
        import {Component, ContentChild, TemplateRef, ViewContainerRef, forwardRef} from '@angular/core';

        @Component({
          selector: 'test',
          template: '<div #foo></div>',
        })
        class FooCmp {
          @ContentChild(forwardRef(() => TemplateRef)) child: any;

          @ContentChild(forwardRef(function() { return ViewContainerRef; })) child2: any;

          @ContentChild((forwardRef((function() { return 'parens'; }) as any))) childInParens: any;
        }
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      // match `i0.ɵɵcontentQuery(dirIndex, TemplateRef, true, null)`
      expect(jsContents).toMatch(contentQueryRegExp('TemplateRef', true));
      // match `i0.ɵɵcontentQuery(dirIndex, ViewContainerRef, true, null)`
      expect(jsContents).toMatch(contentQueryRegExp('ViewContainerRef', true));
      // match `i0.ɵɵcontentQuery(dirIndex, _c0, true, null)`
      expect(jsContents).toContain('_c0 = ["parens"];');
      expect(jsContents).toMatch(contentQueryRegExp('_c0', true));
    });

    it('should handle queries that use an InjectionToken', () => {
      env.write(`test.ts`, `
        import {Component, ContentChild, InjectionToken, ViewChild} from '@angular/core';

        const TOKEN = new InjectionToken('token');

        @Component({
          selector: 'test',
          template: '<div></div>',
        })
        class FooCmp {
          @ViewChild(TOKEN) viewChild: any;
          @ContentChild(TOKEN) contentChild: any;
        }
      `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      // match `i0.ɵɵviewQuery(TOKEN, true, null)`
      expect(jsContents).toMatch(viewQueryRegExp('TOKEN', true));
      // match `i0.ɵɵcontentQuery(dirIndex, TOKEN, true, null)`
      expect(jsContents).toMatch(contentQueryRegExp('TOKEN', true));
    });

    it('should compile expressions that write keys', () => {
      env.write(`test.ts`, `
        import {Component, ContentChild, TemplateRef, ViewContainerRef, forwardRef} from '@angular/core';

        @Component({
          selector: 'test',
          template: '<div (click)="test[key] = $event">',
        })
        class TestCmp {
          test: any;
          key: string;
        }
    `);

      env.driveMain();
      expect(env.getContents('test.js')).toContain('test[key] = $event');
    });

    it('should generate host listeners for components', () => {
      env.write(`test.ts`, `
        import {Component, HostListener} from '@angular/core';

        @Component({
          selector: 'test',
          template: 'Test'
        })
        class FooCmp {
          @HostListener('click')
          onClick(event: any): void {}

          @HostListener('document:click', ['$event.target'])
          onDocumentClick(eventTarget: HTMLElement): void {}

          @HostListener('window:scroll')
          onWindowScroll(event: any): void {}
        }
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      const hostBindingsFn = `
      hostBindings: function FooCmp_HostBindings(rf, ctx) {
        if (rf & 1) {
          i0.ɵɵlistener("click", function FooCmp_click_HostBindingHandler() { return ctx.onClick(); })("click", function FooCmp_click_HostBindingHandler($event) { return ctx.onDocumentClick($event.target); }, false, i0.ɵɵresolveDocument)("scroll", function FooCmp_scroll_HostBindingHandler() { return ctx.onWindowScroll(); }, false, i0.ɵɵresolveWindow);
        }
      }
    `;
      expect(trim(jsContents)).toContain(trim(hostBindingsFn));
    });

    it('should throw in case unknown global target is provided', () => {
      env.write(`test.ts`, `
        import {Component, HostListener} from '@angular/core';

        @Component({
          selector: 'test',
          template: 'Test'
        })
        class FooCmp {
          @HostListener('UnknownTarget:click')
          onClick(event: any): void {}
        }
    `);
      const errors = env.driveDiagnostics();
      expect(trim(errors[0].messageText as string))
          .toContain(
              `Unexpected global target 'UnknownTarget' defined for 'click' event. Supported list of global targets: window,document,body.`);
    });

    it('should provide error location for invalid host properties', () => {
      env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test',
          template: '...',
          host: {
            '(click)': 'act() | pipe',
          }
        })
        class FooCmp {}
      `);

      const errors = env.driveDiagnostics();
      expect(getDiagnosticSourceCode(errors[0])).toBe(`{
            '(click)': 'act() | pipe',
          }`);
      expect(errors[0].messageText).toContain('/test.ts@7:17');
    });

    it('should throw in case pipes are used in host listeners', () => {
      env.write(`test.ts`, `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test',
          template: '...',
          host: {
            '(click)': 'doSmth() | myPipe'
          }
        })
        class FooCmp {}
      `);
      const errors = env.driveDiagnostics();
      expect(trim(errors[0].messageText as string))
          .toContain('Cannot have a pipe in an action expression');
    });

    it('should throw in case pipes are used in host bindings (defined as `value | pipe`)', () => {
      env.write(`test.ts`, `
            import {Component} from '@angular/core';

            @Component({
              selector: 'test',
              template: '...',
              host: {
                '[id]': 'id | myPipe'
              }
            })
            class FooCmp {}
         `);
      const errors = env.driveDiagnostics();
      expect(trim(errors[0].messageText as string))
          .toContain('Host binding expression cannot contain pipes');
    });

    it('should throw in case pipes are used in host bindings (defined as `!(value | pipe)`)',
       () => {
         env.write(`test.ts`, `
            import {Component} from '@angular/core';

            @Component({
              selector: 'test',
              template: '...',
              host: {
                '[id]': '!(id | myPipe)'
              }
            })
            class FooCmp {}
         `);
         const errors = env.driveDiagnostics();
         expect(trim(errors[0].messageText as string))
             .toContain('Host binding expression cannot contain pipes');
       });

    it('should throw in case pipes are used in host bindings (defined as `(value | pipe) === X`)',
       () => {
         env.write(`test.ts`, `
            import {Component} from '@angular/core';

            @Component({
              selector: 'test',
              template: '...',
              host: {
                '[id]': '(id | myPipe) === true'
              }
            })
            class FooCmp {}
         `);
         const errors = env.driveDiagnostics();
         expect(trim(errors[0].messageText as string))
             .toContain('Host binding expression cannot contain pipes');
       });

    it('should generate host bindings for directives', () => {
      env.write(`test.ts`, `
        import {Component, HostBinding, HostListener, TemplateRef} from '@angular/core';

        @Component({
          selector: 'test',
          template: 'Test',
          host: {
            '[attr.hello]': 'foo',
            '(click)': 'onClick($event)',
            '(body:click)': 'onBodyClick($event)',
            '[prop]': 'bar',
          },
        })
        class FooCmp {
          onClick(event: any): void {}

          @HostBinding('class.someclass')
          get someClass(): boolean { return false; }

          @HostListener('change', ['arg1', 'arg2', 'arg3'])
          onChange(event: any, arg: any): void {}
        }
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      const hostBindingsFn = `
      hostVars: 4,
      hostBindings: function FooCmp_HostBindings(rf, ctx) {
        if (rf & 1) {
          i0.ɵɵlistener("click", function FooCmp_click_HostBindingHandler($event) { return ctx.onClick($event); })("click", function FooCmp_click_HostBindingHandler($event) { return ctx.onBodyClick($event); }, false, i0.ɵɵresolveBody)("change", function FooCmp_change_HostBindingHandler() { return ctx.onChange(ctx.arg1, ctx.arg2, ctx.arg3); });
        }
        if (rf & 2) {
          i0.ɵɵhostProperty("prop", ctx.bar);
          i0.ɵɵattribute("hello", ctx.foo);
          i0.ɵɵclassProp("someclass", ctx.someClass);
        }
      }
    `;
      expect(trim(jsContents)).toContain(trim(hostBindingsFn));
    });

    it('should accept dynamic host attribute bindings', () => {
      env.write('other.d.ts', `
      export declare const foo: any;
    `);
      env.write('test.ts', `
      import {Component} from '@angular/core';
      import {foo} from './other';

      const test = foo.bar();

      @Component({
        selector: 'test',
        template: '',
        host: {
          'test': test,
        },
      })
      export class TestCmp {}
    `);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('hostAttrs: ["test", test]');
    });

    it('should accept enum values as host bindings', () => {
      env.write(`test.ts`, `
        import {Component, HostBinding, HostListener, TemplateRef} from '@angular/core';

        enum HostBindings {
          Hello = 'foo'
        }

        @Component({
          selector: 'test',
          template: 'Test',
          host: {
            '[attr.hello]': HostBindings.Hello,
          },
        })
        class FooCmp {
          foo = 'test';
        }
    `);

      env.driveMain();
      expect(env.getContents('test.js')).toContain('i0.ɵɵattribute("hello", ctx.foo)');
    });

    it('should generate host listeners for directives within hostBindings section', () => {
      env.write(`test.ts`, `
        import {Directive, HostListener} from '@angular/core';

        @Directive({
          selector: '[test]',
        })
        class Dir {
          @HostListener('change', ['$event', 'arg'])
          onChange(event: any, arg: any): void {}
        }
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      const hostBindingsFn = `
      hostBindings: function Dir_HostBindings(rf, ctx) {
        if (rf & 1) {
          i0.ɵɵlistener("change", function Dir_change_HostBindingHandler($event) { return ctx.onChange($event, ctx.arg); });
        }
      }
    `;
      expect(trim(jsContents)).toContain(trim(hostBindingsFn));
    });

    it('should use proper default value for preserveWhitespaces config param', () => {
      env.tsconfig();  // default is `false`
      env.write(`test.ts`, `
      import {Component} from '@angular/core';
       @Component({
        selector: 'test',
        preserveWhitespaces: false,
        template: \`
          <div>
            Template with whitespaces
          </div>
        \`
      })
      class FooCmp {}
    `);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('text(1, " Template with whitespaces ");');
    });

    it('should take preserveWhitespaces config option into account', () => {
      env.tsconfig({preserveWhitespaces: true});
      env.write(`test.ts`, `
      import {Component} from '@angular/core';
       @Component({
        selector: 'test',
        template: \`
          <div>
            Template with whitespaces
          </div>
        \`
      })
      class FooCmp {}
    `);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents)
          .toContain('text(2, "\\n            Template with whitespaces\\n          ");');
    });

    it('@Component\'s preserveWhitespaces should override the one defined in config', () => {
      env.tsconfig({preserveWhitespaces: true});
      env.write(`test.ts`, `
      import {Component} from '@angular/core';
       @Component({
        selector: 'test',
        preserveWhitespaces: false,
        template: \`
          <div>
            Template with whitespaces
          </div>
        \`
      })
      class FooCmp {}
    `);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('text(1, " Template with whitespaces ");');
    });

    it('should use proper default value for i18nUseExternalIds config param', () => {
      env.tsconfig();  // default is `true`
      env.write(`test.ts`, `
      import {Component} from '@angular/core';
       @Component({
        selector: 'test',
        template: '<div i18n>Some text</div>'
      })
      class FooCmp {}
    `);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('MSG_EXTERNAL_8321000940098097247$$TEST_TS_1');
    });

    it('should take i18nUseExternalIds config option into account', () => {
      env.tsconfig({i18nUseExternalIds: false});
      env.write(`test.ts`, `
      import {Component} from '@angular/core';
       @Component({
        selector: 'test',
        template: '<div i18n>Some text</div>'
      })
      class FooCmp {}
    `);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).not.toContain('MSG_EXTERNAL_');
    });

    it('should render legacy ids when `enableI18nLegacyMessageIdFormat` is not false', () => {
      env.tsconfig({});
      env.write(`test.ts`, `
        import {Component} from '@angular/core';
        @Component({
          selector: 'test',
          template: '<div i18n>Some text</div>'
        })
        class FooCmp {}`);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents)
          .toContain(
              '":\\u241F5dbba0a3da8dff890e20cf76eb075d58900fbcd3\\u241F8321000940098097247:Some text"');
    });

    it('should render custom id and legacy ids if `enableI18nLegacyMessageIdFormat` is not false',
       () => {
         env.tsconfig({i18nFormatIn: 'xlf'});
         env.write(`test.ts`, `
        import {Component} from '@angular/core';
        @Component({
          selector: 'test',
          template: '<div i18n="@@custom">Some text</div>'
        })
        class FooCmp {}`);
         env.driveMain();
         const jsContents = env.getContents('test.js');
         expect(jsContents)
             .toContain(
                 ':@@custom\\u241F5dbba0a3da8dff890e20cf76eb075d58900fbcd3\\u241F8321000940098097247:Some text');
       });

    it('should not render legacy ids when `enableI18nLegacyMessageIdFormat` is set to false',
       () => {
         env.tsconfig({enableI18nLegacyMessageIdFormat: false, i18nInFormat: 'xmb'});
         env.write(`test.ts`, `
     import {Component} from '@angular/core';
     @Component({
       selector: 'test',
       template: '<div i18n>Some text</div>'
     })
     class FooCmp {}`);
         env.driveMain();
         const jsContents = env.getContents('test.js');
         // Note that the colon would only be there if there is an id attached to the
         // string.
         expect(jsContents).not.toContain(':Some text');
       });

    it('should also render legacy ids for ICUs when normal messages are using legacy ids', () => {
      env.tsconfig({i18nInFormat: 'xliff'});
      env.write(`test.ts`, `
     import {Component} from '@angular/core';
     @Component({
       selector: 'test',
       template: '<div i18n="@@custom">Some text {age, plural, 10 {ten} other {other}}</div>'
     })
     class FooCmp {}`);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents)
          .toContain(
              ':\\u241F720ba589d043a0497ac721ff972f41db0c919efb\\u241F3221232817843005870:{VAR_PLURAL, plural, 10 {ten} other {other}}');
      expect(jsContents)
          .toContain(
              ':@@custom\\u241Fdcb6170595f5d548a3d00937e87d11858f51ad04\\u241F7419139165339437596:Some text');
    });

    it('@Component\'s `interpolation` should override default interpolation config', () => {
      env.write(`test.ts`, `
      import {Component} from '@angular/core';
      @Component({
        selector: 'cmp-with-custom-interpolation-a',
        template: \`<div>{%text%}</div>\`,
        interpolation: ['{%', '%}']
      })
      class ComponentWithCustomInterpolationA {
        text = 'Custom Interpolation A';
      }
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('ɵɵtextInterpolate(ctx.text)');
    });

    it('should handle `encapsulation` field', () => {
      env.write(`test.ts`, `
      import {Component, ViewEncapsulation} from '@angular/core';
      @Component({
        selector: 'comp-a',
        template: '...',
        encapsulation: ViewEncapsulation.None
      })
      class CompA {}
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('encapsulation: 2');
    });

    it('should throw if `encapsulation` contains invalid value', () => {
      env.write('test.ts', `
      import {Component} from '@angular/core';
      @Component({
        selector: 'comp-a',
        template: '...',
        encapsulation: 'invalid-value'
      })
      class CompA {}
    `);
      const errors = env.driveDiagnostics();
      expect(errors.length).toBe(1);
      const messageText = ts.flattenDiagnosticMessageText(errors[0].messageText, '\n');
      expect(messageText)
          .toContain('encapsulation must be a member of ViewEncapsulation enum from @angular/core');
      expect(messageText).toContain('Value is of type \'string\'.');
    });

    it('should handle `changeDetection` field', () => {
      env.write(`test.ts`, `
      import {Component, ChangeDetectionStrategy} from '@angular/core';
      @Component({
        selector: 'comp-a',
        template: '...',
        changeDetection: ChangeDetectionStrategy.OnPush
      })
      class CompA {}
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('changeDetection: 0');
    });

    it('should throw if `changeDetection` contains invalid value', () => {
      env.write('test.ts', `
      import {Component} from '@angular/core';
      @Component({
        selector: 'comp-a',
        template: '...',
        changeDetection: 'invalid-value'
      })
      class CompA {}
    `);
      const errors = env.driveDiagnostics();
      expect(errors.length).toBe(1);
      const messageText = ts.flattenDiagnosticMessageText(errors[0].messageText, '\n');
      expect(messageText)
          .toContain(
              'changeDetection must be a member of ChangeDetectionStrategy enum from @angular/core');
      expect(messageText).toContain('Value is of type \'string\'.');
    });

    it('should ignore empty bindings', () => {
      env.write(`test.ts`, `
      import {Component} from '@angular/core';
       @Component({
        selector: 'test',
        template: '<div [someProp]></div>'
      })
      class FooCmp {}
    `);
      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).not.toContain('i0.ɵɵproperty');
    });

    it('should correctly recognize local symbols', () => {
      env.write('module.ts', `
        import {NgModule} from '@angular/core';
        import {Dir, Comp} from './test';

        @NgModule({
          declarations: [Dir, Comp],
          exports: [Dir, Comp],
        })
        class Module {}
    `);
      env.write(`test.ts`, `
        import {Component, Directive} from '@angular/core';

        @Directive({
          selector: '[dir]',
        })
        export class Dir {}

        @Component({
          selector: 'test',
          template: '<div dir>Test</div>',
        })
        export class Comp {}
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).not.toMatch(/import \* as i[0-9] from ['"].\/test['"]/);
    });

    it('should generate exportAs declarations', () => {
      env.write('test.ts', `
        import {Component, Directive} from '@angular/core';

        @Directive({
          selector: '[test]',
          exportAs: 'foo',
        })
        class Dir {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain(`exportAs: ["foo"]`);
    });

    it('should generate multiple exportAs declarations', () => {
      env.write('test.ts', `
        import {Component, Directive} from '@angular/core';

        @Directive({
          selector: '[test]',
          exportAs: 'foo, bar',
        })
        class Dir {}
    `);

      env.driveMain();

      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain(`exportAs: ["foo", "bar"]`);
    });

    it('should generate correct factory stubs for a test module', () => {
      env.tsconfig({'generateNgFactoryShims': true});

      env.write('test.ts', `
        import {Injectable, NgModule} from '@angular/core';

        @Injectable()
        export class NotAModule {}

        @NgModule({})
        export class TestModule {}
    `);

      env.write('empty.ts', `
        import {Injectable} from '@angular/core';

        @Injectable()
        export class NotAModule {}
    `);

      env.driveMain();

      const factoryContents = env.getContents('test.ngfactory.js');
      expect(factoryContents).toContain(`import * as i0 from '@angular/core';`);
      expect(factoryContents).toContain(`import { NotAModule, TestModule } from './test';`);
      expect(factoryContents)
          .toContain(`export var TestModuleNgFactory = new i0.\u0275NgModuleFactory(TestModule);`);
      expect(factoryContents).not.toContain(`NotAModuleNgFactory`);
      expect(factoryContents).not.toContain('\u0275NonEmptyModule');

      const emptyFactory = env.getContents('empty.ngfactory.js');
      expect(emptyFactory).toContain(`import * as i0 from '@angular/core';`);
      expect(emptyFactory).toContain(`export var \u0275NonEmptyModule = true;`);
    });

    describe('ngfactory shims', () => {
      beforeEach(() => {
        env.tsconfig({'generateNgFactoryShims': true});
      });

      it('should not be generated for .js files', () => {
        // This test verifies that the compiler does not attempt to generate shim files for non-TS
        // input files (in this case, other.js).
        env.write('test.ts', `
          import {Component, NgModule} from '@angular/core';

          @Component({
            selector: 'test-cmp',
            template: 'This is a template',
          })
          export class TestCmp {}

          @NgModule({
            declarations: [TestCmp],
            exports: [TestCmp],
          })
          export class TestModule {}
        `);
        env.write('other.js', `
          export class TestJs {}
        `);

        expect(env.driveDiagnostics()).toEqual([]);
        env.assertExists('test.ngfactory.js');
        env.assertDoesNotExist('other.ngfactory.js');
      });

      it('should be able to depend on an existing factory shim', () => {
        // This test verifies that ngfactory files from the compilations of dependencies are
        // available to import in a fresh compilation. It is derived from a bug observed in g3 where
        // the shim system accidentally caused TypeScript to think that *.ngfactory.ts files always
        // exist.
        env.write('other.ngfactory.d.ts', `
          export class OtherNgFactory {}
        `);
        env.write('test.ts', `
          import {OtherNgFactory} from './other.ngfactory';

          class DoSomethingWith extends OtherNgFactory {}
        `);
        expect(env.driveDiagnostics()).toEqual([]);
      });

      it('should generate factory shims for files not listed in root files', () => {
        // This test verifies that shims are generated for all files in the user's program, even if
        // only a subset of those files are listed in the tsconfig as root files.

        env.tsconfig({'generateNgFactoryShims': true}, /* extraRootDirs */ undefined, [
          absoluteFrom('/test.ts'),
        ]);
        env.write('test.ts', `
          import {Component} from '@angular/core';

          import {OtherCmp} from './other';

          @Component({
            selector: 'test',
            template: '...',
          })
          export class TestCmp {
            constructor(other: OtherCmp) {}
          }
        `);
        env.write('other.ts', `
          import {Component} from '@angular/core';

          @Component({
            selector: 'other',
            template: '...',
          })
          export class OtherCmp {}
        `);
        env.driveMain();

        expect(env.getContents('other.ngfactory.js')).toContain('OtherCmp');
      });

      it('should generate correct type annotation for NgModuleFactory calls in ngfactories', () => {
        env.write('test.ts', `
        import {Component} from '@angular/core';
        @Component({
          selector: 'test',
          template: '...',
        })
        export class TestCmp {}
      `);
        env.driveMain();

        const ngfactoryContents = env.getContents('test.ngfactory.d.ts');
        expect(ngfactoryContents).toContain(`i0.ɵNgModuleFactory<any>`);
      });

      it('should be able to compile an app using the factory shim', () => {
        env.tsconfig({'allowEmptyCodegenFiles': true});

        env.write('test.ts', `
          export {MyModuleNgFactory} from './my-module.ngfactory';
      `);

        env.write('my-module.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class MyModule {}
      `);

        env.driveMain();
      });

      it('should generate correct imports in factory stubs when compiling @angular/core', () => {
        env.tsconfig({'allowEmptyCodegenFiles': true});

        env.write('test.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class TestModule {}
      `);

        // Trick the compiler into thinking it's compiling @angular/core.
        env.write('r3_symbols.ts', 'export const ITS_JUST_ANGULAR = true;');

        env.driveMain();

        const factoryContents = env.getContents('test.ngfactory.js');
        expect(normalize(factoryContents)).toBe(normalize(`
        import * as i0 from "./r3_symbols";
        import { TestModule } from './test';
        export var TestModuleNgFactory = new i0.NgModuleFactory(TestModule);
      `));
      });

      describe('file-level comments', () => {
        it('should copy a top-level comment into a factory stub', () => {
          env.tsconfig({'allowEmptyCodegenFiles': true});

          env.write('test.ts', `/** I am a top-level comment. */

            import {NgModule} from '@angular/core';

            @NgModule({})
            export class TestModule {}
          `);
          env.driveMain();

          const factoryContents = env.getContents('test.ngfactory.js');
          expect(factoryContents).toContain(`/** I am a top-level comment. */\n`);
        });

        it('should not copy a non-file level comment into a factory stub', () => {
          env.tsconfig({'allowEmptyCodegenFiles': true});

          env.write('test.ts', `/** I am a top-level comment, but not for the file. */
            export const TEST = true;
          `);
          env.driveMain();

          const factoryContents = env.getContents('test.ngfactory.js');
          expect(factoryContents).not.toContain('top-level comment');
        });

        it('should not copy a file level comment with an @license into a factory stub', () => {
          env.tsconfig({'allowEmptyCodegenFiles': true});

          env.write('test.ts', `/** @license I am a top-level comment, but have a license. */
            export const TEST = true;
          `);
          env.driveMain();

          const factoryContents = env.getContents('test.ngfactory.js');
          expect(factoryContents).not.toContain('top-level comment');
        });
      });
    });


    describe('ngsummary shim generation', () => {
      beforeEach(() => {
        env.tsconfig({'generateNgSummaryShims': true});
      });

      it('should generate a summary stub for decorated classes in the input file only', () => {
        env.write('test.ts', `
          import {Injectable, NgModule} from '@angular/core';

          export class NotAModule {}

          @NgModule({})
          export class TestModule {}
      `);

        env.driveMain();

        const summaryContents = env.getContents('test.ngsummary.js');
        expect(summaryContents).toEqual(`export var TestModuleNgSummary = null;\n`);
      });

      it('should generate a summary stub for classes exported via exports', () => {
        env.write('test.ts', `
          import {Injectable, NgModule} from '@angular/core';

          @NgModule({})
          class NotDirectlyExported {}

          export {NotDirectlyExported};
      `);

        env.driveMain();

        const summaryContents = env.getContents('test.ngsummary.js');
        expect(summaryContents).toEqual(`export var NotDirectlyExportedNgSummary = null;\n`);
      });

      it('it should generate empty export when there are no other summary symbols, to ensure the output is a valid ES module',
         () => {
           env.write('empty.ts', `
          export class NotAModule {}
      `);

           env.driveMain();

           const emptySummary = env.getContents('empty.ngsummary.js');
           // The empty export ensures this js file is still an ES module.
           expect(emptySummary).toEqual(`export var \u0275empty = null;\n`);
         });
    });


    it('should compile a banana-in-a-box inside of a template', () => {
      env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          template: '<div *tmpl [(bananaInABox)]="prop"></div>',
          selector: 'test'
        })
        class TestCmp {}
    `);

      env.driveMain();
    });

    it('generates inherited factory definitions', () => {
      env.write(`test.ts`, `
        import {Injectable} from '@angular/core';

        class Dep {}

        @Injectable()
        class Base {
          constructor(dep: Dep) {}
        }

        @Injectable()
        class Child extends Base {}

        @Injectable()
        class GrandChild extends Child {
          constructor() {
            super(null!);
          }
        }
    `);


      env.driveMain();
      const jsContents = env.getContents('test.js');

      expect(jsContents)
          .toContain('function Base_Factory(t) { return new (t || Base)(i0.ɵɵinject(Dep)); }');
      expect(jsContents).toContain('var \u0275Child_BaseFactory = i0.ɵɵgetInheritedFactory(Child)');
      expect(jsContents)
          .toContain('function Child_Factory(t) { return \u0275Child_BaseFactory(t || Child); }');
      expect(jsContents)
          .toContain('function GrandChild_Factory(t) { return new (t || GrandChild)(); }');
    });

    it('generates base factories for directives', () => {
      env.write(`test.ts`, `
        import {Directive} from '@angular/core';

        @Directive({
          selector: '[base]',
        })
        class Base {}

        @Directive({
          selector: '[test]',
        })
        class Dir extends Base {
        }
    `);


      env.driveMain();
      const jsContents = env.getContents('test.js');

      expect(jsContents).toContain('var \u0275Dir_BaseFactory = i0.ɵɵgetInheritedFactory(Dir)');
    });

    it('should wrap "directives" in component metadata in a closure when forward references are present',
       () => {
         env.write('test.ts', `
        import {Component, NgModule} from '@angular/core';

        @Component({
          selector: 'cmp-a',
          template: '<cmp-b></cmp-b>',
        })
        class CmpA {}

        @Component({
          selector: 'cmp-b',
          template: 'This is B',
        })
        class CmpB {}

        @NgModule({
          declarations: [CmpA, CmpB],
        })
        class Module {}
    `);

         env.driveMain();

         const jsContents = env.getContents('test.js');
         expect(jsContents).toContain('directives: function () { return [CmpB]; }');
       });

    it('should wrap setClassMetadata in an iife', () => {
      env.write('test.ts', `
        import {Injectable} from '@angular/core';

        @Injectable({providedIn: 'root'})
        export class Service {}
      `);

      env.driveMain();
      const jsContents = env.getContents('test.js').replace(/\s+/g, ' ');
      expect(jsContents)
          .toContain(
              `/*@__PURE__*/ (function () { i0.ɵsetClassMetadata(Service, [{ type: Injectable, args: [{ providedIn: 'root' }] }], null, null); })();`);
    });

    it('should not include `schemas` in component and module defs', () => {
      env.write('test.ts', `
        import {Component, NgModule, NO_ERRORS_SCHEMA} from '@angular/core';

        @Component({
          selector: 'comp',
          template: '<custom-el></custom-el>',
          schemas: [NO_ERRORS_SCHEMA],
        })
        class MyComp {}

        @NgModule({
          declarations: [MyComp],
          schemas: [NO_ERRORS_SCHEMA],
        })
        class MyModule {}
      `);

      env.driveMain();
      const jsContents = trim(env.getContents('test.js'));
      expect(jsContents).toContain(trim(`
        MyComp.ɵcmp = i0.ɵɵdefineComponent({
          type: MyComp,
          selectors: [["comp"]],
          decls: 1,
          vars: 0,
          template: function MyComp_Template(rf, ctx) {
            if (rf & 1) {
              i0.ɵɵelement(0, "custom-el");
            }
          },
          encapsulation: 2
        });
      `));
      expect(jsContents)
          .toContain(trim('MyModule.ɵmod = i0.ɵɵdefineNgModule({ type: MyModule });'));
    });

    it('should emit setClassMetadata calls for all types', () => {
      env.write('test.ts', `
      import {Component, Directive, Injectable, NgModule, Pipe} from '@angular/core';

      @Component({selector: 'cmp', template: 'I am a component!'}) class TestComponent {}
      @Directive({selector: 'dir'}) class TestDirective {}
      @Injectable() class TestInjectable {}
      @NgModule({declarations: [TestComponent, TestDirective]}) class TestNgModule {}
      @Pipe({name: 'pipe'}) class TestPipe {}
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toContain('\u0275setClassMetadata(TestComponent, ');
      expect(jsContents).toContain('\u0275setClassMetadata(TestDirective, ');
      expect(jsContents).toContain('\u0275setClassMetadata(TestInjectable, ');
      expect(jsContents).toContain('\u0275setClassMetadata(TestNgModule, ');
      expect(jsContents).toContain('\u0275setClassMetadata(TestPipe, ');
    });

    it('should use imported types in setClassMetadata if they can be represented as values', () => {
      env.write(`types.ts`, `
      export class MyTypeA {}
      export class MyTypeB {}
    `);
      env.write(`test.ts`, `
      import {Component, Inject, Injectable} from '@angular/core';
      import {MyTypeA, MyTypeB} from './types';

      @Injectable({providedIn: 'root'})
      export class SomeService {
        constructor(arg: MyTypeA) {}
      }

      @Component({
        selector: 'some-comp',
        template: '...',
      })
      export class SomeComp {
        constructor(@Inject('arg-token') arg: MyTypeB) {}
      }
    `);

      env.driveMain();
      const jsContents = trim(env.getContents('test.js'));
      expect(jsContents).toContain(`import * as i1 from "./types";`);
      expect(jsContents).toMatch(setClassMetadataRegExp('type: i1\\.MyTypeA'));
      expect(jsContents).toMatch(setClassMetadataRegExp('type: i1\\.MyTypeB'));
    });

    it('should use imported types in setClassMetadata if they can be represented as values and imported as `* as foo`',
       () => {
         env.write(`types.ts`, `
         export class MyTypeA {}
         export class MyTypeB {}
       `);
         env.write(`test.ts`, `
         import {Component, Inject, Injectable} from '@angular/core';
         import * as types from './types';

         @Injectable({providedIn: 'root'})
         export class SomeService {
           constructor(arg: types.MyTypeA) {}
         }

         @Component({
           selector: 'some-comp',
           template: '...',
         })
         export class SomeComp {
           constructor(@Inject('arg-token') arg: types.MyTypeB) {}
         }
      `);

         env.driveMain();
         const jsContents = trim(env.getContents('test.js'));
         expect(jsContents).toContain(`import * as i1 from "./types";`);
         expect(jsContents).toMatch(setClassMetadataRegExp('type: i1.MyTypeA'));
         expect(jsContents).toMatch(setClassMetadataRegExp('type: i1.MyTypeB'));
       });

    it('should use default-imported types if they can be represented as values', () => {
      env.write(`types.ts`, `
            export default class Default {}
            export class Other {}
          `);
      env.write(`test.ts`, `
            import {Component} from '@angular/core';
            import {Other} from './types';
            import Default from './types';

            @Component({selector: 'test', template: 'test'})
            export class SomeCmp {
              constructor(arg: Default, other: Other) {}
            }
         `);

      env.driveMain();
      const jsContents = trim(env.getContents('test.js'));
      expect(jsContents).toContain(`import Default from './types';`);
      expect(jsContents).toContain(`import * as i1 from "./types";`);
      expect(jsContents).toContain('i0.ɵɵdirectiveInject(Default)');
      expect(jsContents).toContain('i0.ɵɵdirectiveInject(i1.Other)');
      expect(jsContents).toMatch(setClassMetadataRegExp('type: Default'));
      expect(jsContents).toMatch(setClassMetadataRegExp('type: i1.Other'));
    });

    describe('namespace support', () => {
      it('should generate correct imports for type references to namespaced symbols using a namespace import',
         () => {
           env.write(`/node_modules/ns/index.d.ts`, `
              export declare class Zero {}
              export declare namespace one {
                export declare class One {}
              }
              export declare namespace one.two {
                export declare class Two {}
              }
           `);
           env.write(`test.ts`, `
              import {Inject, Injectable, InjectionToken} from '@angular/core';
              import * as ns from 'ns';

              @Injectable()
              export class MyService {
                constructor(
                  zero: ns.Zero,
                  one: ns.one.One,
                  two: ns.one.two.Two,
                ) {}
              }
           `);

           env.driveMain();
           const jsContents = trim(env.getContents('test.js'));
           expect(jsContents).toContain(`import * as i1 from "ns";`);
           expect(jsContents).toContain('i0.ɵɵinject(i1.Zero)');
           expect(jsContents).toContain('i0.ɵɵinject(i1.one.One)');
           expect(jsContents).toContain('i0.ɵɵinject(i1.one.two.Two)');
           expect(jsContents).toMatch(setClassMetadataRegExp('type: i1.Zero'));
           expect(jsContents).toMatch(setClassMetadataRegExp('type: i1.one.One'));
           expect(jsContents).toMatch(setClassMetadataRegExp('type: i1.one.two.Two'));
         });

      it('should generate correct imports for type references to namespaced symbols using named imports',
         () => {
           env.write(`/node_modules/ns/index.d.ts`, `
              export namespace ns {
                export declare class Zero {}
                export declare namespace one {
                  export declare class One {}
                }
                export declare namespace one.two {
                  export declare class Two {}
                }
              }
           `);
           env.write(`test.ts`, `
              import {Inject, Injectable, InjectionToken} from '@angular/core';
              import {ns} from 'ns';
              import {ns as alias} from 'ns';

              @Injectable()
              export class MyService {
                constructor(
                  zero: ns.Zero,
                  one: ns.one.One,
                  two: ns.one.two.Two,
                  aliasedZero: alias.Zero,
                  aliasedOne: alias.one.One,
                  aliasedTwo: alias.one.two.Two,
                ) {}
              }
           `);

           env.driveMain();
           const jsContents = trim(env.getContents('test.js'));
           expect(jsContents).toContain(`import * as i1 from "ns";`);
           expect(jsContents)
               .toContain(
                   'i0.ɵɵinject(i1.ns.Zero), ' +
                   'i0.ɵɵinject(i1.ns.one.One), ' +
                   'i0.ɵɵinject(i1.ns.one.two.Two), ' +
                   'i0.ɵɵinject(i1.ns.Zero), ' +
                   'i0.ɵɵinject(i1.ns.one.One), ' +
                   'i0.ɵɵinject(i1.ns.one.two.Two)');
           expect(jsContents).toMatch(setClassMetadataRegExp('type: i1.ns.Zero'));
           expect(jsContents).toMatch(setClassMetadataRegExp('type: i1.ns.one.One'));
           expect(jsContents).toMatch(setClassMetadataRegExp('type: i1.ns.one.two.Two'));
         });

      it('should not error for a namespace import as parameter type when @Inject is used', () => {
        env.tsconfig({'strictInjectionParameters': true});
        env.write(`/node_modules/foo/index.d.ts`, `
          export = Foo;
          declare class Foo {}
          declare namespace Foo {}
        `);
        env.write(`test.ts`, `
          import {Inject, Injectable, InjectionToken} from '@angular/core';
          import * as Foo from 'foo';

          export const TOKEN = new InjectionToken<Foo>('Foo');

          @Injectable()
          export class MyService {
            constructor(@Inject(TOKEN) foo: Foo) {}
          }
       `);

        env.driveMain();
        const jsContents = trim(env.getContents('test.js'));
        expect(jsContents).toContain('i0.ɵɵinject(TOKEN)');
        expect(jsContents).toMatch(setClassMetadataRegExp('type: undefined'));
      });

      it('should error for a namespace import as parameter type used for DI', () => {
        env.tsconfig({'strictInjectionParameters': true});
        env.write(`/node_modules/foo/index.d.ts`, `
          export = Foo;
          declare class Foo {}
          declare namespace Foo {}
        `);
        env.write(`test.ts`, `
          import {Injectable} from '@angular/core';
          import * as Foo from 'foo';

          @Injectable()
          export class MyService {
            constructor(foo: Foo) {}
          }
       `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(1);
        expect(diags[0].messageText)
            .toBe(
                `No suitable injection token for parameter 'foo' of class 'MyService'.\nFound Foo`);
      });
    });

    it('should use `undefined` in setClassMetadata if types can\'t be represented as values',
       () => {
         env.write(`types.ts`, `
      export type MyType = Map<any, any>;
    `);
         env.write(`test.ts`, `
      import {Component, Inject, Injectable} from '@angular/core';
      import {MyType} from './types';

      @Component({
        selector: 'some-comp',
        template: '...',
      })
      export class SomeComp {
        constructor(@Inject('arg-token') arg: MyType) {}
      }
    `);

         env.driveMain();
         const jsContents = trim(env.getContents('test.js'));
         expect(jsContents).not.toContain(`import { MyType } from './types';`);
         // Note: `type: undefined` below, since MyType can't be represented as a value
         expect(jsContents).toMatch(setClassMetadataRegExp('type: undefined'));
       });

    it('should not throw in case whitespaces and HTML comments are present inside <ng-content>',
       () => {
         env.write('test.ts', `
          import {Component} from '@angular/core';

          @Component({
            selector: 'cmp-a',
            template: \`
              <ng-content>
                <!-- Some comments -->
              </ng-content>
            \`,
          })
          class CmpA {}
       `);
         const errors = env.driveDiagnostics();
         expect(errors.length).toBe(0);
       });

    it('should compile a template using multiple directives with the same selector', () => {
      env.write('test.ts', `
      import {Component, Directive, NgModule} from '@angular/core';

      @Directive({selector: '[test]'})
      class DirA {}

      @Directive({selector: '[test]'})
      class DirB {}

      @Component({
        template: '<div test></div>',
      })
      class Cmp {}

      @NgModule({
        declarations: [Cmp, DirA, DirB],
      })
      class Module {}
  `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      expect(jsContents).toMatch(/directives: \[DirA,\s+DirB\]/);
    });

    describe('cycle detection', () => {
      it('should detect a simple cycle and use remote component scoping', () => {
        env.write('test.ts', `
        import {Component, NgModule} from '@angular/core';
        import {NormalComponent} from './cyclic';

        @Component({
          selector: 'cyclic-component',
          template: 'Importing this causes a cycle',
        })
        export class CyclicComponent {}

        @NgModule({
          declarations: [NormalComponent, CyclicComponent],
        })
        export class Module {}
      `);

        env.write('cyclic.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'normal-component',
          template: '<cyclic-component></cyclic-component>',
        })
        export class NormalComponent {}
      `);

        env.driveMain();
        const jsContents = env.getContents('test.js');
        expect(jsContents)
            .toMatch(
                /i\d\.ɵɵsetComponentScope\(NormalComponent,\s+\[NormalComponent,\s+CyclicComponent\],\s+\[\]\)/);
        expect(jsContents).not.toContain('/*__PURE__*/ i0.ɵɵsetComponentScope');
      });

      it('should detect a cycle added entirely during compilation', () => {
        env.write('test.ts', `
        import {NgModule} from '@angular/core';
        import {ACmp} from './a';
        import {BCmp} from './b';

        @NgModule({declarations: [ACmp, BCmp]})
        export class Module {}
      `);
        env.write('a.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'a-cmp',
          template: '<b-cmp></b-cmp>',
        })
        export class ACmp {}
      `);
        env.write('b.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'b-cmp',
          template: '<a-cmp></a-cmp>',
        })
        export class BCmp {}
      `);
        env.driveMain();
        const aJsContents = env.getContents('a.js');
        const bJsContents = env.getContents('b.js');
        expect(aJsContents).toMatch(/import \* as i\d? from ".\/b"/);
        expect(bJsContents).not.toMatch(/import \* as i\d? from ".\/a"/);
      });

      it('should not detect a potential cycle if it doesn\'t actually happen', () => {
        env.write('test.ts', `
        import {NgModule} from '@angular/core';
        import {ACmp} from './a';
        import {BCmp} from './b';

        @NgModule({declarations: [ACmp, BCmp]})
        export class Module {}
      `);
        env.write('a.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'a-cmp',
          template: '<b-cmp></b-cmp>',
        })
        export class ACmp {}
      `);
        env.write('b.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'b-cmp',
          template: 'does not use a-cmp',
        })
        export class BCmp {}
      `);
        env.driveMain();
        const jsContents = env.getContents('test.js');
        expect(jsContents).not.toContain('setComponentScope');
      });
    });

    describe('local refs', () => {
      it('should not generate an error when a local ref is unresolved' +
             ' (outside of template type-checking)',
         () => {
           env.write('test.ts', `
          import {Component} from '@angular/core';

          @Component({
            template: '<div #ref="unknownTarget"></div>',
          })
          export class TestCmp {}
        `);
           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(0);
         });
    });

    describe('multiple local refs', () => {
      const getComponentScript = (template: string): string => `
      import {Component, Directive, NgModule} from '@angular/core';

      @Component({selector: 'my-cmp', template: \`${template}\`})
      class Cmp {}

      @NgModule({declarations: [Cmp]})
      class Module {}
    `;

      const cases = [
        `
        <div #ref></div>
        <div #ref></div>
      `,
        `
        <ng-container>
          <div #ref></div>
        </ng-container>
        <div #ref></div>
      `,
        `
        <ng-template>
          <div #ref></div>
        </ng-template>
        <div #ref></div>
      `,
        `
        <div *ngIf="visible" #ref></div>
        <div #ref></div>
      `,
        `
        <div *ngFor="let item of items" #ref></div>
        <div #ref></div>
      `
      ];

      cases.forEach(template => {
        it('should not throw', () => {
          env.write('test.ts', getComponentScript(template));
          const errors = env.driveDiagnostics();
          expect(errors.length).toBe(0);
        });
      });
    });

    it('should wrap "inputs" and "outputs" keys if they contain unsafe characters', () => {
      env.write(`test.ts`, `
      import {Directive, Input} from '@angular/core';

      @Directive({
        selector: '[somedir]',
        inputs: ['track-type', 'track-name', 'inputTrackName', 'src.xl'],
        outputs: ['output-track-type', 'output-track-name', 'outputTrackName', 'output.event']
      })
      export class SomeDir {
        @Input('track-type') trackType: string;
        @Input('track-name') trackName: string;
      }
    `);

      env.driveMain();
      const jsContents = env.getContents('test.js');
      const inputsAndOutputs = `
      inputs: {
        "track-type": "track-type",
        "track-name": "track-name",
        inputTrackName: "inputTrackName",
        "src.xl": "src.xl",
        trackType: ["track-type", "trackType"],
        trackName: ["track-name", "trackName"]
      },
      outputs: {
        "output-track-type": "output-track-type",
        "output-track-name": "output-track-name",
        outputTrackName: "outputTrackName",
        "output.event": "output.event"
      }
    `;
      expect(trim(jsContents)).toContain(trim(inputsAndOutputs));
    });

    it('should compile programs with typeRoots', () => {
      // Write out a custom tsconfig.json that includes 'typeRoots' and 'files'. 'files'
      // is necessary because otherwise TS picks up the testTypeRoot/test/index.d.ts
      // file into the program automatically. Shims are also turned on because the shim
      // ts.CompilerHost wrapper can break typeRoot functionality (which this test is
      // meant to detect).
      env.write('tsconfig.json', `{
      "extends": "./tsconfig-base.json",
      "angularCompilerOptions": {
        "generateNgFactoryShims": true,
        "generateNgSummaryShims": true,
      },
      "compilerOptions": {
        "typeRoots": ["./testTypeRoot"],
      },
      "files": ["./test.ts"]
    }`);
      env.write('test.ts', `
      import {Test} from 'ambient';
      console.log(Test);
    `);
      env.write('testTypeRoot/.exists', '');
      env.write('testTypeRoot/test/index.d.ts', `
      declare module 'ambient' {
        export const Test = 'This is a test';
      }
    `);

      env.driveMain();

      // Success is enough to indicate that this passes.
    });

    describe('NgModule invalid import/export errors', () => {
      function verifyThrownError(errorCode: ErrorCode, errorMessage: string) {
        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(1);
        const {code, messageText} = errors[0];
        expect(code).toBe(ngErrorCode(errorCode));
        expect(trim(messageText as string)).toContain(errorMessage);
      }

      it('should provide a hint when importing an invalid NgModule from node_modules', () => {
        env.write('node_modules/external/index.d.ts', `
          export declare class NotAModule {}
        `);
        env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {NotAModule} from 'external';

          @NgModule({
            imports: [NotAModule],
          })
          export class Module {}
        `);

        verifyThrownError(
            ErrorCode.NGMODULE_INVALID_IMPORT,
            'This likely means that the library (external) which declares NotAModule has not ' +
                'been processed correctly by ngcc, or is not compatible with Angular Ivy.');
      });

      it('should provide a hint when importing an invalid NgModule from a local library', () => {
        env.write('libs/external/index.d.ts', `
          export declare class NotAModule {}
        `);

        env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {NotAModule} from './libs/external';

          @NgModule({
            imports: [NotAModule],
          })
          export class Module {}
        `);

        verifyThrownError(
            ErrorCode.NGMODULE_INVALID_IMPORT,
            'This likely means that the dependency which declares NotAModule has not ' +
                'been processed correctly by ngcc.');
      });

      it('should provide a hint when importing an invalid NgModule in the current program', () => {
        env.write('invalid.ts', `
          export class NotAModule {}
        `);

        env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {NotAModule} from './invalid';

          @NgModule({
            imports: [NotAModule],
          })
          export class Module {}
        `);

        verifyThrownError(
            ErrorCode.NGMODULE_INVALID_IMPORT, 'Is it missing an @NgModule annotation?');
      });
    });

    describe('when processing external directives', () => {
      it('should not emit multiple references to the same directive', () => {
        env.write('node_modules/external/index.d.ts', `
        import {ɵɵDirectiveDefWithMeta, ɵɵNgModuleDefWithMeta} from '@angular/core';

        export declare class ExternalDir {
          static ɵdir: ɵɵDirectiveDefWithMeta<ExternalDir, '[test]', never, never, never, never>;
        }

        export declare class ExternalModule {
          static ɵmod: ɵɵNgModuleDefWithMeta<ExternalModule, [typeof ExternalDir], never, [typeof ExternalDir]>;
        }
      `);
        env.write('test.ts', `
        import {Component, Directive, NgModule} from '@angular/core';
        import {ExternalModule} from 'external';

        @Component({
          template: '<div test></div>',
        })
        class Cmp {}

        @NgModule({
          declarations: [Cmp],
          // Multiple imports of the same module used to result in duplicate directive references
          // in the output.
          imports: [ExternalModule, ExternalModule],
        })
        class Module {}
      `);

        env.driveMain();
        const jsContents = env.getContents('test.js');
        expect(jsContents).toMatch(/directives: \[i1\.ExternalDir\]/);
      });

      it('should import directives by their external name', () => {
        env.write('node_modules/external/index.d.ts', `
        import {ɵɵDirectiveDefWithMeta, ɵɵNgModuleDefWithMeta} from '@angular/core';
        import {InternalDir} from './internal';

        export {InternalDir as ExternalDir} from './internal';

        export declare class ExternalModule {
          static ɵmod: ɵɵNgModuleDefWithMeta<ExternalModule, [typeof InternalDir], never, [typeof InternalDir]>;
        }
      `);
        env.write('node_modules/external/internal.d.ts', `

        export declare class InternalDir {
          static ɵdir: ɵɵDirectiveDefWithMeta<InternalDir, '[test]', never, never, never, never>;
        }
      `);
        env.write('test.ts', `
        import {Component, Directive, NgModule} from '@angular/core';
        import {ExternalModule} from 'external';

        @Component({
          template: '<div test></div>',
        })
        class Cmp {}

        @NgModule({
          declarations: [Cmp],
          imports: [ExternalModule],
        })
        class Module {}
      `);

        env.driveMain();
        const jsContents = env.getContents('test.js');
        expect(jsContents).toMatch(/directives: \[i1\.ExternalDir\]/);
      });
    });

    // Run checks that are present in preanalysis phase in both sync and async mode, to
    // make sure the error messages are consistently thrown from `analyzeSync` and
    // `analyzeAsync` functions.
    ['sync', 'async'].forEach(mode => {
      describe(`preanalysis phase checks [${mode}]`, () => {
        let driveDiagnostics: () => Promise<ReadonlyArray<ts.Diagnostic>>;
        beforeEach(() => {
          if (mode === 'async') {
            env.enablePreloading();
            driveDiagnostics = () => env.driveDiagnosticsAsync();
          } else {
            driveDiagnostics = () => Promise.resolve(env.driveDiagnostics());
          }
        });

        it('should throw if @Component is missing a template', async () => {
          env.write('test.ts', `
            import {Component} from '@angular/core';

            @Component({
              selector: 'test',
            })
            export class TestCmp {}
          `);

          const diags = await driveDiagnostics();
          expect(diags[0].messageText).toBe('component is missing a template');
          expect(diags[0].file!.fileName).toBe(absoluteFrom('/test.ts'));
        });

        it('should throw if `styleUrls` is defined incorrectly in @Component', async () => {
          env.write('test.ts', `
            import {Component} from '@angular/core';

            @Component({
              selector: 'test',
              template: '...',
              styleUrls: '...'
            })
            export class TestCmp {}
          `);

          const diags = await driveDiagnostics();
          expect(diags.length).toBe(1);
          const messageText = ts.flattenDiagnosticMessageText(diags[0].messageText, '\n');
          expect(messageText).toContain('styleUrls must be an array of strings');
          expect(messageText).toContain('Value is of type \'string\'.');
          expect(diags[0].file!.fileName).toBe(absoluteFrom('/test.ts'));
        });
      });
    });

    describe('flat module indices', () => {
      it('should generate a basic flat module index', () => {
        env.tsconfig({
          'flatModuleOutFile': 'flat.js',
        });
        env.write('test.ts', 'export const TEST = "this is a test";');

        env.driveMain();
        const jsContents = env.getContents('flat.js');
        expect(jsContents).toContain('export * from \'./test\';');
      });

      it('should determine the flat module entry-point within multiple root files', () => {
        env.tsconfig({
          'flatModuleOutFile': 'flat.js',
        });
        env.write('ignored.ts', 'export const TEST = "this is ignored";');
        env.write('index.ts', 'export const ENTRY = "this is the entry";');

        env.driveMain();
        const jsContents = env.getContents('flat.js');
        expect(jsContents)
            .toContain(
                'export * from \'./index\';',
                'Should detect the "index.ts" file as flat module entry-point.');
      });

      it('should generate a flat module with an id', () => {
        env.tsconfig({
          'flatModuleOutFile': 'flat.js',
          'flatModuleId': '@mymodule',
        });
        env.write('test.ts', 'export const TEST = "this is a test";');

        env.driveMain();
        const dtsContents = env.getContents('flat.d.ts');
        expect(dtsContents).toContain('/// <amd-module name="@mymodule" />');
      });

      it('should generate a proper flat module index file when nested', () => {
        env.tsconfig({
          'flatModuleOutFile': './public-api/index.js',
        });

        env.write('test.ts', `export const SOME_EXPORT = 'some-export'`);
        env.driveMain();

        expect(env.getContents('./public-api/index.js')).toContain(`export * from '../test';`);
      });

      it('should not throw if "flatModuleOutFile" is set to null', () => {
        env.tsconfig({
          'flatModuleOutFile': null,
        });

        env.write('test.ts', `export const SOME_EXPORT = 'some-export'`);
        // The "driveMain" method automatically ensures that there is no
        // exception and that the build succeeded.
        env.driveMain();
      });

      it('should not throw or produce flat module index if "flatModuleOutFile" is set to ' +
             'empty string',
         () => {
           env.tsconfig({
             'flatModuleOutFile': '',
           });

           env.write('test.ts', `export const SOME_EXPORT = 'some-export'`);
           // The "driveMain" method automatically ensures that there is no
           // exception and that the build succeeded.
           env.driveMain();
           // Previously ngtsc incorrectly tried generating a flat module index
           // file if the "flatModuleOutFile" was set to an empty string. ngtsc
           // just wrote the bundle file with an empty filename (just extension).
           env.assertDoesNotExist('.js');
           env.assertDoesNotExist('.d.ts');
         });

      it('should report an error when a flat module index is requested but no entrypoint can be determined',
         () => {
           env.tsconfig({'flatModuleOutFile': 'flat.js'});
           env.write('test.ts', 'export class Foo {}');
           env.write('test2.ts', 'export class Bar {}');

           const errors = env.driveDiagnostics();
           expect(errors.length).toBe(1);
           expect(errors[0].messageText)
               .toBe(
                   'Angular compiler option "flatModuleOutFile" requires one and only one .ts file in the "files" field.');
         });

      it('should report an error when a visible directive is not exported', () => {
        env.tsconfig({'flatModuleOutFile': 'flat.js'});
        env.write('test.ts', `
        import {Directive, NgModule} from '@angular/core';

        // The directive is not exported.
        @Directive({selector: 'test'})
        class Dir {}

        // The module is, which makes the directive visible.
        @NgModule({declarations: [Dir], exports: [Dir]})
        export class Module {}
      `);

        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(1);
        expect(errors[0].messageText)
            .toBe(
                'Unsupported private class Dir. This class is visible ' +
                'to consumers via Module -> Dir, but is not exported from the top-level library ' +
                'entrypoint.');

        // Verify that the error is for the correct class.
        const error = errors[0] as ts.Diagnostic;
        const id = expectTokenAtPosition(error.file!, error.start!, ts.isIdentifier);
        expect(id.text).toBe('Dir');
        expect(ts.isClassDeclaration(id.parent)).toBe(true);
      });

      it('should report an error when a deeply visible directive is not exported', () => {
        env.tsconfig({'flatModuleOutFile': 'flat.js'});
        env.write('test.ts', `
        import {Directive, NgModule} from '@angular/core';

        // The directive is not exported.
        @Directive({selector: 'test'})
        class Dir {}

        // Neither is the module which declares it - meaning the directive is not visible here.
        @NgModule({declarations: [Dir], exports: [Dir]})
        class DirModule {}

        // The module is, which makes the directive visible.
        @NgModule({exports: [DirModule]})
        export class Module {}
      `);

        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(2);
        expect(errors[0].messageText)
            .toBe(
                'Unsupported private class DirModule. This class is ' +
                'visible to consumers via Module -> DirModule, but is not exported from the top-level ' +
                'library entrypoint.');
        expect(errors[1].messageText)
            .toBe(
                'Unsupported private class Dir. This class is visible ' +
                'to consumers via Module -> DirModule -> Dir, but is not exported from the top-level ' +
                'library entrypoint.');
      });

      it('should report an error when a deeply visible module is not exported', () => {
        env.tsconfig({'flatModuleOutFile': 'flat.js'});
        env.write('test.ts', `
        import {Directive, NgModule} from '@angular/core';

        // The directive is exported.
        @Directive({selector: 'test'})
        export class Dir {}

        // The module which declares it is not.
        @NgModule({declarations: [Dir], exports: [Dir]})
        class DirModule {}

        // The module is, which makes the module and directive visible.
        @NgModule({exports: [DirModule]})
        export class Module {}
      `);

        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(1);
        expect(errors[0].messageText)
            .toBe(
                'Unsupported private class DirModule. This class is ' +
                'visible to consumers via Module -> DirModule, but is not exported from the top-level ' +
                'library entrypoint.');
      });

      it('should not report an error when a non-exported module is imported by a visible one',
         () => {
           env.tsconfig({'flatModuleOutFile': 'flat.js'});
           env.write('test.ts', `
        import {Directive, NgModule} from '@angular/core';

        // The directive is not exported.
        @Directive({selector: 'test'})
        class Dir {}

        // Neither is the module which declares it.
        @NgModule({declarations: [Dir], exports: [Dir]})
        class DirModule {}

        // This module is, but it doesn't re-export the module, so it doesn't make the module and
        // directive visible.
        @NgModule({imports: [DirModule]})
        export class Module {}
      `);

           const errors = env.driveDiagnostics();
           expect(errors.length).toBe(0);
         });

      it('should not report an error when re-exporting an external symbol', () => {
        env.tsconfig({'flatModuleOutFile': 'flat.js'});
        env.write('test.ts', `
        import {Directive, NgModule} from '@angular/core';
        import {ExternalModule} from 'external';

        // This module makes ExternalModule and ExternalDir visible.
        @NgModule({exports: [ExternalModule]})
        export class Module {}
      `);
        env.write('node_modules/external/index.d.ts', `
        import {ɵɵDirectiveDefWithMeta, ɵɵNgModuleDefWithMeta} from '@angular/core';

        export declare class ExternalDir {
          static ɵdir: ɵɵDirectiveDefWithMeta<ExternalDir, '[test]', never, never, never, never>;
        }

        export declare class ExternalModule {
          static ɵmod: ɵɵNgModuleDefWithMeta<ExternalModule, [typeof ExternalDir], never, [typeof ExternalDir]>;
        }
      `);

        const errors = env.driveDiagnostics();
        expect(errors.length).toBe(0);
      });
    });

    describe('aliasing re-exports', () => {
      beforeEach(() => {
        env.tsconfig({
          'generateDeepReexports': true,
        });
      });

      it('should re-export a directive from a different file under a private symbol name', () => {
        env.write('dir.ts', `
          import {Directive} from '@angular/core';

          @Directive({
            selector: 'dir',
          })
          export class Dir {}
        `);
        env.write('module.ts', `
          import {Directive, NgModule} from '@angular/core';
          import {Dir} from './dir';

          @Directive({selector: '[inline]'})
          export class InlineDir {}

          @NgModule({
            declarations: [Dir, InlineDir],
            exports: [Dir, InlineDir],
          })
          export class Module {}
        `);

        env.driveMain();
        const jsContents = env.getContents('module.js');
        const dtsContents = env.getContents('module.d.ts');

        expect(jsContents).toContain('export { Dir as ɵngExportɵModuleɵDir } from "./dir";');
        expect(jsContents).not.toContain('ɵngExportɵModuleɵInlineDir');
        expect(dtsContents).toContain('export { Dir as ɵngExportɵModuleɵDir } from "./dir";');
        expect(dtsContents).not.toContain('ɵngExportɵModuleɵInlineDir');
      });

      it('should re-export a directive from an exported NgModule under a private symbol name',
         () => {
           env.write('dir.ts', `
          import {Directive, NgModule} from '@angular/core';

          @Directive({
            selector: 'dir',
          })
          export class Dir {}

          @NgModule({
            declarations: [Dir],
            exports: [Dir],
          })
          export class DirModule {}
        `);
           env.write('module.ts', `
          import {NgModule} from '@angular/core';
          import {DirModule} from './dir';

          @NgModule({
            exports: [DirModule],
          })
          export class Module {}
        `);

           env.driveMain();
           const jsContents = env.getContents('module.js');
           const dtsContents = env.getContents('module.d.ts');

           expect(jsContents).toContain('export { Dir as ɵngExportɵModuleɵDir } from "./dir";');
           expect(dtsContents).toContain('export { Dir as ɵngExportɵModuleɵDir } from "./dir";');
         });

      it('should not re-export a directive that\'s not exported from the NgModule', () => {
        env.write('dir.ts', `
             import {Directive} from '@angular/core';

             @Directive({
               selector: 'dir',
             })
             export class Dir {}
           `);
        env.write('module.ts', `
             import {NgModule} from '@angular/core';
             import {Dir} from './dir';

             @NgModule({
               declarations: [Dir],
               exports: [],
             })
             export class Module {}
           `);

        env.driveMain();
        const jsContents = env.getContents('module.js');
        const dtsContents = env.getContents('module.d.ts');

        expect(jsContents).not.toContain('ɵngExportɵModuleɵDir');
        expect(dtsContents).not.toContain('ɵngExportɵModuleɵDir');
      });

      it('should not re-export a directive that\'s already exported', () => {
        env.write('dir.ts', `
          import {Directive} from '@angular/core';

          @Directive({
            selector: 'dir',
          })
          export class Dir {}
        `);
        env.write('module.ts', `
          import {NgModule} from '@angular/core';
          import {Dir} from './dir';

          @NgModule({
            declarations: [Dir],
            exports: [Dir],
          })
          export class Module {}

          export {Dir};
        `);

        env.driveMain();
        const jsContents = env.getContents('module.js');
        const dtsContents = env.getContents('module.d.ts');

        expect(jsContents).not.toContain('ɵngExportɵModuleɵDir');
        expect(dtsContents).not.toContain('ɵngExportɵModuleɵDir');
      });

      it('should not re-export a directive from an exported, external NgModule', () => {
        env.write(`node_modules/external/index.d.ts`, `
          import {ɵɵDirectiveDefWithMeta, ɵɵNgModuleDefWithMeta} from '@angular/core';

          export declare class ExternalDir {
            static ɵdir: ɵɵDirectiveDefWithMeta<ExternalDir, '[test]', never, never, never, never>;
          }

          export declare class ExternalModule {
            static ɵmod: ɵɵNgModuleDefWithMeta<ExternalModule, [typeof ExternalDir], never, [typeof ExternalDir]>;
          }
          `);
        env.write('module.ts', `
          import {NgModule} from '@angular/core';
          import {ExternalModule} from 'external';

          @NgModule({
            exports: [ExternalModule],
          })
          export class Module {}
        `);

        env.driveMain();
        const jsContents = env.getContents('module.js');

        expect(jsContents).not.toContain('ɵngExportɵExternalModuleɵExternalDir');
      });

      it('should error when two directives with the same declared name are exported from the same NgModule',
         () => {
           env.write('dir.ts', `
          import {Directive} from '@angular/core';

          @Directive({
            selector: 'dir',
          })
          export class Dir {}
        `);
           env.write('dir2.ts', `
          import {Directive} from '@angular/core';

          @Directive({
            selector: 'dir',
          })
          export class Dir {}
        `);
           env.write('module.ts', `
          import {NgModule} from '@angular/core';
          import {Dir} from './dir';
          import {Dir as Dir2} from './dir2';

          @NgModule({
            declarations: [Dir, Dir2],
            exports: [Dir, Dir2],
          })
          export class Module {}
        `);

           const diag = env.driveDiagnostics();
           expect(diag.length).toBe(1);
           expect(diag[0]!.code).toEqual(ngErrorCode(ErrorCode.NGMODULE_REEXPORT_NAME_COLLISION));
         });

      it('should not error when two directives with the same declared name are exported from the same NgModule, but one is exported from the file directly',
         () => {
           env.write('dir.ts', `
             import {Directive} from '@angular/core';

             @Directive({
               selector: 'dir',
             })
             export class Dir {}
           `);
           env.write('dir2.ts', `
             import {Directive} from '@angular/core';

             @Directive({
               selector: 'dir',
             })
             export class Dir {}
           `);
           env.write('module.ts', `
             import {NgModule} from '@angular/core';
             import {Dir} from './dir';
             import {Dir as Dir2} from './dir2';

             @NgModule({
               declarations: [Dir, Dir2],
               exports: [Dir, Dir2],
             })
             export class Module {}

             export {Dir} from './dir2';
           `);

           env.driveMain();
           const jsContents = env.getContents('module.js');
           expect(jsContents).toContain('export { Dir as ɵngExportɵModuleɵDir } from "./dir";');
         });

      it('should choose a re-exported symbol if one is present', () => {
        env.write(`node_modules/external/dir.d.ts`, `
          import {ɵɵDirectiveDefWithMeta} from '@angular/core';

          export declare class ExternalDir {
            static ɵdir: ɵɵDirectiveDefWithMeta<ExternalDir, '[test]', never, never, never, never>;
          }
          `);
        env.write('node_modules/external/module.d.ts', `
          import {ɵɵNgModuleDefWithMeta} from '@angular/core';
          import {ExternalDir} from './dir';

          export declare class ExternalModule {
            static ɵmod: ɵɵNgModuleDefWithMeta<ExternalModule, [typeof ExternalDir], never, [typeof ExternalDir]>;
          }

          export {ExternalDir as ɵngExportɵExternalModuleɵExternalDir};
        `);
        env.write('test.ts', `
          import {Component, Directive, NgModule} from '@angular/core';
          import {ExternalModule} from 'external/module';

          @Component({
            selector: 'test-cmp',
            template: '<div test></div>',
          })
          class Cmp {}

          @NgModule({
            declarations: [Cmp],
            imports: [ExternalModule],
          })
          class Module {}
        `);

        env.driveMain();
        const jsContents = env.getContents('test.js');
        expect(jsContents).toContain('import * as i1 from "external/module";');
        expect(jsContents).toContain('directives: [i1.ɵngExportɵExternalModuleɵExternalDir]');
      });

      it('should not generate re-exports when disabled', () => {
        // Return to the default configuration, which has re-exports disabled.
        env.tsconfig();

        env.write('dir.ts', `
          import {Directive} from '@angular/core';

          @Directive({
            selector: 'dir',
          })
          export class Dir {}
        `);
        env.write('module.ts', `
          import {NgModule} from '@angular/core';
          import {Dir} from './dir';

          @NgModule({
            declarations: [Dir],
            exports: [Dir],
          })
          export class Module {}
        `);

        env.driveMain();
        const jsContents = env.getContents('module.js');
        const dtsContents = env.getContents('module.d.ts');

        expect(jsContents).not.toContain('ɵngExportɵModuleɵDir');
        expect(dtsContents).not.toContain('ɵngExportɵModuleɵDir');
      });
    });

    it('should execute custom transformers', () => {
      let beforeCount = 0;
      let afterCount = 0;

      env.write('test.ts', `
      import {NgModule} from '@angular/core';

      @NgModule({})
      class Module {}
    `);

      env.driveMain({
        beforeTs: [() => (sourceFile: ts.SourceFile) => {
          beforeCount++;
          return sourceFile;
        }],
        afterTs: [() => (sourceFile: ts.SourceFile) => {
          afterCount++;
          return sourceFile;
        }],
      });

      expect(beforeCount).toBe(1);
      expect(afterCount).toBe(1);
    });

    // These tests trigger the Tsickle compiler which asserts that the file-paths
    // are valid for the real OS. When on non-Windows systems it doesn't like paths
    // that start with `C:`.
    if (os !== 'Windows' || platform() === 'win32') {
      describe('@fileoverview Closure annotations', () => {
        it('should be produced if not present in source file', () => {
          env.tsconfig({
            'annotateForClosureCompiler': true,
          });
          env.write(`test.ts`, `
        import {Component} from '@angular/core';

        @Component({
          template: '<div class="test"></div>',
        })
        export class SomeComp {}
      `);

          env.driveMain();
          const jsContents = env.getContents('test.js');
          const fileoverview = `
        /**
         * @fileoverview added by tsickle
         * Generated from: test.ts
         * @suppress {checkTypes,constantProperty,extraRequire,missingOverride,missingReturn,unusedPrivateMembers,uselessCode} checked by tsc
         */
      `;
          expect(trim(jsContents).startsWith(trim(fileoverview))).toBeTruthy();
        });

        it('should be produced for empty source files', () => {
          env.tsconfig({
            'annotateForClosureCompiler': true,
          });
          env.write(`test.ts`, ``);

          env.driveMain();
          const jsContents = env.getContents('test.js');
          const fileoverview = `
        /**
         * @fileoverview added by tsickle
         * Generated from: test.ts
         * @suppress {checkTypes,constantProperty,extraRequire,missingOverride,missingReturn,unusedPrivateMembers,uselessCode} checked by tsc
         */
      `;
          expect(trim(jsContents).startsWith(trim(fileoverview))).toBeTruthy();
        });

        it('should be produced for generated factory files', () => {
          env.tsconfig({
            'annotateForClosureCompiler': true,
            'generateNgFactoryShims': true,
          });
          env.write(`test.ts`, `
            import {Component} from '@angular/core';

            @Component({
              template: '<div class="test"></div>',
            })
            export class SomeComp {}
          `);

          env.driveMain();
          const jsContents = env.getContents('test.ngfactory.js');
          const fileoverview = `
        /**
         * @fileoverview added by tsickle
         * Generated from: test.ngfactory.ts
         * @suppress {checkTypes,constantProperty,extraRequire,missingOverride,missingReturn,unusedPrivateMembers,uselessCode} checked by tsc
         */
      `;
          expect(trim(jsContents).startsWith(trim(fileoverview))).toBeTruthy();
        });

        it('should always be at the very beginning of a script (if placed above imports)', () => {
          env.tsconfig({
            'annotateForClosureCompiler': true,
          });
          env.write(`test.ts`, `
        /**
         * @fileoverview Some Comp overview
         * @modName {some_comp}
         */

        import {Component} from '@angular/core';

        @Component({
          template: '<div class="test"></div>',
        })
        export class SomeComp {}
      `);

          env.driveMain();
          const jsContents = env.getContents('test.js');
          const fileoverview = `
        /**
         *
         * @fileoverview Some Comp overview
         * Generated from: test.ts
         * @modName {some_comp}
         *
         * @suppress {checkTypes,constantProperty,extraRequire,missingOverride,missingReturn,unusedPrivateMembers,uselessCode} checked by tsc
         */
      `;
          expect(trim(jsContents).startsWith(trim(fileoverview))).toBeTruthy();
        });

        it('should always be at the very beginning of a script (if placed above non-imports)',
           () => {
             env.tsconfig({
               'annotateForClosureCompiler': true,
             });
             env.write(`test.ts`, `
        /**
         * @fileoverview Some Comp overview
         * @modName {some_comp}
         */

        const testConst = 'testConstValue';
        const testFn = function() { return true; }
      `);

             env.driveMain();
             const jsContents = env.getContents('test.js');
             const fileoverview = `
        /**
         *
         * @fileoverview Some Comp overview
         * Generated from: test.ts
         * @modName {some_comp}
         *
         * @suppress {checkTypes,constantProperty,extraRequire,missingOverride,missingReturn,unusedPrivateMembers,uselessCode} checked by tsc
         */
      `;
             expect(trim(jsContents).startsWith(trim(fileoverview))).toBeTruthy();
           });
      });
    }

    describe('sanitization', () => {
      it('should generate sanitizers for unsafe attributes in hostBindings fn in Directives',
         () => {
           env.write(`test.ts`, `
        import {Component, Directive, HostBinding} from '@angular/core';

        @Directive({
          selector: '[unsafeAttrs]'
        })
        class UnsafeAttrsDirective {
          @HostBinding('attr.href')
          attrHref: string;

          @HostBinding('attr.src')
          attrSrc: string;

          @HostBinding('attr.action')
          attrAction: string;

          @HostBinding('attr.profile')
          attrProfile: string;

          @HostBinding('attr.innerHTML')
          attrInnerHTML: string;

          @HostBinding('attr.title')
          attrSafeTitle: string;
        }

        @Component({
          selector: 'foo',
          template: '<a [unsafeAttrs]="ctxProp">Link Title</a>'
        })
        class FooCmp {}
      `);

           env.driveMain();
           const jsContents = env.getContents('test.js');
           const hostBindingsFn = `
        hostVars: 6,
        hostBindings: function UnsafeAttrsDirective_HostBindings(rf, ctx) {
          if (rf & 2) {
            i0.ɵɵattribute("href", ctx.attrHref, i0.ɵɵsanitizeUrlOrResourceUrl)("src", ctx.attrSrc, i0.ɵɵsanitizeUrlOrResourceUrl)("action", ctx.attrAction, i0.ɵɵsanitizeUrl)("profile", ctx.attrProfile, i0.ɵɵsanitizeResourceUrl)("innerHTML", ctx.attrInnerHTML, i0.ɵɵsanitizeHtml)("title", ctx.attrSafeTitle);
          }
        }
      `;
           expect(trim(jsContents)).toContain(trim(hostBindingsFn));
         });

      it('should generate sanitizers for unsafe properties in hostBindings fn in Directives',
         () => {
           env.write(`test.ts`, `
        import {Component, Directive, HostBinding} from '@angular/core';

        @Directive({
          selector: '[unsafeProps]'
        })
        class UnsafePropsDirective {
          @HostBinding('href')
          propHref: string;

          @HostBinding('src')
          propSrc: string;

          @HostBinding('action')
          propAction: string;

          @HostBinding('profile')
          propProfile: string;

          @HostBinding('innerHTML')
          propInnerHTML: string;

          @HostBinding('title')
          propSafeTitle: string;
        }

        @Component({
          selector: 'foo',
          template: '<a [unsafeProps]="ctxProp">Link Title</a>'
        })
        class FooCmp {}
      `);

           env.driveMain();
           const jsContents = env.getContents('test.js');
           const hostBindingsFn = `
        hostVars: 6,
        hostBindings: function UnsafePropsDirective_HostBindings(rf, ctx) {
          if (rf & 2) {
            i0.ɵɵhostProperty("href", ctx.propHref, i0.ɵɵsanitizeUrlOrResourceUrl)("src", ctx.propSrc, i0.ɵɵsanitizeUrlOrResourceUrl)("action", ctx.propAction, i0.ɵɵsanitizeUrl)("profile", ctx.propProfile, i0.ɵɵsanitizeResourceUrl)("innerHTML", ctx.propInnerHTML, i0.ɵɵsanitizeHtml)("title", ctx.propSafeTitle);
          }
        }
      `;
           expect(trim(jsContents)).toContain(trim(hostBindingsFn));
         });

      it('should not generate sanitizers for URL properties in hostBindings fn in Component',
         () => {
           env.write(`test.ts`, `
        import {Component} from '@angular/core';

        @Component({
          selector: 'foo',
          template: '<a href="example.com">Link Title</a>',
          host: {
            '[src]': 'srcProp',
            '[href]': 'hrefProp',
            '[title]': 'titleProp',
            '[attr.src]': 'srcAttr',
            '[attr.href]': 'hrefAttr',
            '[attr.title]': 'titleAttr',
          }
        })
        class FooCmp {}
      `);

           env.driveMain();
           const jsContents = env.getContents('test.js');
           const hostBindingsFn = `
        hostVars: 6,
        hostBindings: function FooCmp_HostBindings(rf, ctx) {
          if (rf & 2) {
            i0.ɵɵhostProperty("src", ctx.srcProp)("href", ctx.hrefProp)("title", ctx.titleProp);
            i0.ɵɵattribute("src", ctx.srcAttr)("href", ctx.hrefAttr)("title", ctx.titleAttr);
          }
        }
      `;
           expect(trim(jsContents)).toContain(trim(hostBindingsFn));
         });
    });

    describe('listLazyRoutes()', () => {
      // clang-format off
    const lazyRouteMatching = (
      route: string, fromModulePath: RegExp, fromModuleName: string, toModulePath: RegExp,
      toModuleName: string) => {
      return {
        route,
        module: jasmine.objectContaining({
          name: fromModuleName,
          filePath: jasmine.stringMatching(fromModulePath),
        }),
        referencedModule: jasmine.objectContaining({
          name: toModuleName,
          filePath: jasmine.stringMatching(toModulePath),
        }),
      } as unknown as LazyRoute;
    };
      // clang-format on

      beforeEach(() => {
        env.write('node_modules/@angular/router/index.d.ts', `
        import {ModuleWithProviders, ɵɵNgModuleDefWithMeta as ɵɵNgModuleDefWithMeta} from '@angular/core';

        export declare var ROUTES;
        export declare class RouterModule {
          static forRoot(arg1: any, arg2: any): ModuleWithProviders<RouterModule>;
          static forChild(arg1: any): ModuleWithProviders<RouterModule>;
          static ɵmod: ɵɵNgModuleDefWithMeta<RouterModule, never, never, never>;
        }
      `);
      });

      describe('when called without arguments', () => {
        it('should list all routes', () => {
          env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forRoot([
                {path: '1', loadChildren: './lazy/lazy-1#Lazy1Module'},
                {path: '2', loadChildren: './lazy/lazy-2#Lazy2Module'},
              ]),
            ],
          })
          export class TestModule {}
        `);
          env.write('lazy/lazy-1.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class Lazy1Module {}
        `);
          env.write('lazy/lazy-2.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: '3', loadChildren: './lazy-3#Lazy3Module'},
              ]),
            ],
          })
          export class Lazy2Module {}
        `);
          env.write('lazy/lazy-3.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class Lazy3Module {}
        `);

          const routes = env.driveRoutes();
          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy-3#Lazy3Module', /\/lazy\/lazy-2\.ts$/, 'Lazy2Module', /\/lazy\/lazy-3\.ts$/,
                'Lazy3Module'),
            lazyRouteMatching(
                './lazy/lazy-1#Lazy1Module', /\/test\.ts$/, 'TestModule', /\/lazy\/lazy-1\.ts$/,
                'Lazy1Module'),
            lazyRouteMatching(
                './lazy/lazy-2#Lazy2Module', /\/test\.ts$/, 'TestModule', /\/lazy\/lazy-2\.ts$/,
                'Lazy2Module'),
          ]);
        });

        it('should detect lazy routes in simple children routes', () => {
          env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @Component({
            selector: 'foo',
            template: '<div>Foo</div>'
          })
          class FooCmp {}

          @NgModule({
            imports: [
              RouterModule.forRoot([
                {path: '', children: [
                  {path: 'foo', component: FooCmp},
                  {path: 'lazy', loadChildren: './lazy#LazyModule'}
                ]},
              ]),
            ],
          })
          export class TestModule {}
        `);
          env.write('lazy.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({})
          export class LazyModule {}
        `);

          const routes = env.driveRoutes();
          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy#LazyModule', /\/test\.ts$/, 'TestModule', /\/lazy\.ts$/, 'LazyModule'),
          ]);
        });

        it('should detect lazy routes in all root directories', () => {
          env.tsconfig({}, ['./foo/other-root-dir', './bar/other-root-dir']);
          env.write('src/test.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forRoot([
                {path: '', loadChildren: './lazy-foo#LazyFooModule'},
              ]),
            ],
          })
          export class TestModule {}
        `);
          env.write('foo/other-root-dir/src/lazy-foo.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: '', loadChildren: './lazy-bar#LazyBarModule'},
              ]),
            ],
          })
          export class LazyFooModule {}
        `);
          env.write('bar/other-root-dir/src/lazy-bar.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: '', loadChildren: './lazier-bar#LazierBarModule'},
              ]),
            ],
          })
          export class LazyBarModule {}
        `);
          env.write('bar/other-root-dir/src/lazier-bar.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class LazierBarModule {}
        `);

          const routes = env.driveRoutes();

          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy-foo#LazyFooModule', /\/test\.ts$/, 'TestModule',
                /\/foo\/other-root-dir\/src\/lazy-foo\.ts$/, 'LazyFooModule'),
            lazyRouteMatching(
                './lazy-bar#LazyBarModule', /\/foo\/other-root-dir\/src\/lazy-foo\.ts$/,
                'LazyFooModule', /\/bar\/other-root-dir\/src\/lazy-bar\.ts$/, 'LazyBarModule'),
            lazyRouteMatching(
                './lazier-bar#LazierBarModule', /\/bar\/other-root-dir\/src\/lazy-bar\.ts$/,
                'LazyBarModule', /\/bar\/other-root-dir\/src\/lazier-bar\.ts$/, 'LazierBarModule'),
          ]);
        });
      });

      describe('when called with entry module', () => {
        it('should throw if the entry module hasn\'t been analyzed', () => {
          env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: '', loadChildren: './lazy#LazyModule'},
              ]),
            ],
          })
          export class TestModule {}
        `);

          const entryModule1 = absoluteFrom('/test#TestModule');
          const entryModule2 = absoluteFrom('/not-test#TestModule');
          const entryModule3 = absoluteFrom('/test#NotTestModule');

          expect(() => env.driveRoutes(entryModule1)).not.toThrow();
          expect(() => env.driveRoutes(entryModule2))
              .toThrowError(`Failed to list lazy routes: Unknown module '${entryModule2}'.`);
          expect(() => env.driveRoutes(entryModule3))
              .toThrowError(`Failed to list lazy routes: Unknown module '${entryModule3}'.`);
        });

        it('should list all transitive lazy routes', () => {
          env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';
          import {Test1Module as Test1ModuleRenamed} from './test-1';
          import {Test2Module} from './test-2';

          @NgModule({
            exports: [
              Test1ModuleRenamed,
            ],
            imports: [
              Test2Module,
              RouterModule.forRoot([
                {path: '', loadChildren: './lazy/lazy#LazyModule'},
              ]),
            ],
          })
          export class TestModule {}
        `);
          env.write('test-1.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: 'one', loadChildren: './lazy-1/lazy-1#Lazy1Module'},
              ]),
            ],
          })
          export class Test1Module {}
        `);
          env.write('test-2.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            exports: [
              RouterModule.forChild([
                {path: 'two', loadChildren: './lazy-2/lazy-2#Lazy2Module'},
              ]),
            ],
          })
          export class Test2Module {}
        `);
          env.write('lazy/lazy.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class LazyModule {}
        `);
          env.write('lazy-1/lazy-1.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class Lazy1Module {}
        `);
          env.write('lazy-2/lazy-2.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class Lazy2Module {}
        `);

          const routes = env.driveRoutes(absoluteFrom('/test#TestModule'));

          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy/lazy#LazyModule', /\/test\.ts$/, 'TestModule', /\/lazy\/lazy\.ts$/,
                'LazyModule'),
            lazyRouteMatching(
                './lazy-1/lazy-1#Lazy1Module', /\/test-1\.ts$/, 'Test1Module',
                /\/lazy-1\/lazy-1\.ts$/, 'Lazy1Module'),
            lazyRouteMatching(
                './lazy-2/lazy-2#Lazy2Module', /\/test-2\.ts$/, 'Test2Module',
                /\/lazy-2\/lazy-2\.ts$/, 'Lazy2Module'),
          ]);
        });

        it('should ignore exports that do not refer to an `NgModule`', () => {
          env.write('test-1.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';
          import {Test2Component, Test2Module} from './test-2';

          @NgModule({
            exports: [
              Test2Component,
              Test2Module,
            ],
            imports: [
              Test2Module,
              RouterModule.forRoot([
                {path: '', loadChildren: './lazy-1/lazy-1#Lazy1Module'},
              ]),
            ],
          })
          export class Test1Module {}
        `);
          env.write('test-2.ts', `
          import {Component, NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @Component({
            selector: 'test-2',
            template: '',
          })
          export class Test2Component {}

          @NgModule({
            declarations: [
              Test2Component,
            ],
            exports: [
              Test2Component,
              RouterModule.forChild([
                {path: 'two', loadChildren: './lazy-2/lazy-2#Lazy2Module'},
              ]),
            ],
          })
          export class Test2Module {}
        `);
          env.write('lazy-1/lazy-1.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class Lazy1Module {}
        `);
          env.write('lazy-2/lazy-2.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class Lazy2Module {}
        `);

          const routes = env.driveRoutes(absoluteFrom('/test-1#Test1Module'));

          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy-1/lazy-1#Lazy1Module', /\/test-1\.ts$/, 'Test1Module',
                /\/lazy-1\/lazy-1\.ts$/, 'Lazy1Module'),
            lazyRouteMatching(
                './lazy-2/lazy-2#Lazy2Module', /\/test-2\.ts$/, 'Test2Module',
                /\/lazy-2\/lazy-2\.ts$/, 'Lazy2Module'),
          ]);
        });

        it('should support `ModuleWithProviders`', () => {
          env.write('test.ts', `
          import {ModuleWithProviders, NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: '', loadChildren: './lazy-2/lazy-2#Lazy2Module'},
              ]),
            ],
          })
          export class TestRoutingModule {
            static forRoot(): ModuleWithProviders<TestRoutingModule> {
              return {
                ngModule: TestRoutingModule,
                providers: [],
              };
            }
          }

          @NgModule({
            imports: [
              TestRoutingModule.forRoot(),
              RouterModule.forRoot([
                {path: '', loadChildren: './lazy-1/lazy-1#Lazy1Module'},
              ]),
            ],
          })
          export class TestModule {}
        `);
          env.write('lazy-1/lazy-1.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class Lazy1Module {}
        `);
          env.write('lazy-2/lazy-2.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class Lazy2Module {}
        `);

          const routes = env.driveRoutes(absoluteFrom('/test#TestModule'));

          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy-1/lazy-1#Lazy1Module', /\/test\.ts$/, 'TestModule', /\/lazy-1\/lazy-1\.ts$/,
                'Lazy1Module'),
            lazyRouteMatching(
                './lazy-2/lazy-2#Lazy2Module', /\/test\.ts$/, 'TestRoutingModule',
                /\/lazy-2\/lazy-2\.ts$/, 'Lazy2Module'),
          ]);
        });

        it('should only process each module once', () => {
          env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: '', loadChildren: './lazy/lazy#LazyModule'},
              ]),
            ],
          })
          export class SharedModule {}

          @NgModule({
            imports: [
              SharedModule,
              RouterModule.forRoot([
                {path: '', loadChildren: './lazy/lazy#LazyModule'},
              ]),
            ],
          })
          export class TestModule {}
        `);
          env.write('lazy/lazy.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: '', loadChildren: '../lazier/lazier#LazierModule'},
              ]),
            ],
          })
          export class LazyModule {}
        `);
          env.write('lazier/lazier.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class LazierModule {}
        `);

          const routes = env.driveRoutes(absoluteFrom('/test#TestModule'));

          // `LazyModule` is referenced in both `SharedModule` and `TestModule`,
          // but it is only processed once (hence one `LazierModule` entry).
          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy/lazy#LazyModule', /\/test\.ts$/, 'TestModule', /\/lazy\/lazy\.ts$/,
                'LazyModule'),
            lazyRouteMatching(
                './lazy/lazy#LazyModule', /\/test\.ts$/, 'SharedModule', /\/lazy\/lazy\.ts$/,
                'LazyModule'),
            lazyRouteMatching(
                '../lazier/lazier#LazierModule', /\/lazy\/lazy\.ts$/, 'LazyModule',
                /\/lazier\/lazier\.ts$/, 'LazierModule'),
          ]);
        });

        it('should detect lazy routes in all root directories', () => {
          env.tsconfig({}, ['./foo/other-root-dir', './bar/other-root-dir']);
          env.write('src/test.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forRoot([
                {path: '', loadChildren: './lazy-foo#LazyFooModule'},
              ]),
            ],
          })
          export class TestModule {}
        `);
          env.write('foo/other-root-dir/src/lazy-foo.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: '', loadChildren: './lazy-bar#LazyBarModule'},
              ]),
            ],
          })
          export class LazyFooModule {}
        `);
          env.write('bar/other-root-dir/src/lazy-bar.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forChild([
                {path: '', loadChildren: './lazier-bar#LazierBarModule'},
              ]),
            ],
          })
          export class LazyBarModule {}
        `);
          env.write('bar/other-root-dir/src/lazier-bar.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class LazierBarModule {}
        `);

          const routes = env.driveRoutes(absoluteFrom('/src/test#TestModule'));

          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy-foo#LazyFooModule', /\/test\.ts$/, 'TestModule',
                /\/foo\/other-root-dir\/src\/lazy-foo\.ts$/, 'LazyFooModule'),
            lazyRouteMatching(
                './lazy-bar#LazyBarModule', /\/foo\/other-root-dir\/src\/lazy-foo\.ts$/,
                'LazyFooModule', /\/bar\/other-root-dir\/src\/lazy-bar\.ts$/, 'LazyBarModule'),
            lazyRouteMatching(
                './lazier-bar#LazierBarModule', /\/bar\/other-root-dir\/src\/lazy-bar\.ts$/,
                'LazyBarModule', /\/bar\/other-root-dir\/src\/lazier-bar\.ts$/, 'LazierBarModule'),
          ]);
        });

        it('should ignore modules not (transitively) referenced by the entry module', () => {
          env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forRoot([
                {path: '', loadChildren: './lazy/lazy#Lazy1Module'},
              ]),
            ],
          })
          export class Test1Module {}

          @NgModule({
            imports: [
              RouterModule.forRoot([
                {path: '', loadChildren: './lazy/lazy#Lazy2Module'},
              ]),
            ],
          })
          export class Test2Module {}
        `);
          env.write('lazy/lazy.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class Lazy1Module {}

          @NgModule({})
          export class Lazy2Module {}
        `);

          const routes = env.driveRoutes(absoluteFrom('/test#Test1Module'));

          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy/lazy#Lazy1Module', /\/test\.ts$/, 'Test1Module', /\/lazy\/lazy\.ts$/,
                'Lazy1Module'),
          ]);
        });

        it('should ignore routes to unknown modules', () => {
          env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {RouterModule} from '@angular/router';

          @NgModule({
            imports: [
              RouterModule.forRoot([
                {path: '', loadChildren: './unknown/unknown#UnknownModule'},
                {path: '', loadChildren: './lazy/lazy#LazyModule'},
              ]),
            ],
          })
          export class TestModule {}
        `);
          env.write('lazy/lazy.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({})
          export class LazyModule {}
        `);

          const routes = env.driveRoutes(absoluteFrom('/test#TestModule'));

          expect(routes).toEqual([
            lazyRouteMatching(
                './lazy/lazy#LazyModule', /\/test\.ts$/, 'TestModule', /\/lazy\/lazy\.ts$/,
                'LazyModule'),
          ]);
        });
      });
    });

    describe('ivy switch mode', () => {
      it('should allow for symbols to be renamed when they use a SWITCH_IVY naming mechanism',
         () => {
           env.write('test.ts', `
export const FooCmp__POST_R3__ = 1;
export const FooCmp__PRE_R3__ = 2;
export const FooCmp = FooCmp__PRE_R3__;`);
           env.driveMain();

           const source = env.getContents('test.js');
           expect(source).toContain(`export var FooCmp = FooCmp__POST_R3__`);
           expect(source).not.toContain(`export var FooCmp = FooCmp__PRE_R3__`);
         });

      it('should allow for SWITCH_IVY naming even even if it occurs outside of core', () => {
        const content = `
export const Foo__POST_R3__ = 1;
export const Foo__PRE_R3__ = 2;
export const Foo = Foo__PRE_R3__;
`;
        env.write('test_outside_angular_core.ts', content);
        env.write(
            'test_inside_angular_core.ts', content + '\nexport const ITS_JUST_ANGULAR = true;');
        env.driveMain();

        const sourceTestOutsideAngularCore = env.getContents('test_outside_angular_core.js');
        const sourceTestInsideAngularCore = env.getContents('test_inside_angular_core.js');
        expect(sourceTestInsideAngularCore).toContain(sourceTestOutsideAngularCore);
      });
    });

    describe('NgModule export aliasing', () => {
      it('should use an alias to import a directive from a deep dependency', () => {
        env.tsconfig({'_useHostForImportGeneration': true});

        // 'alpha' declares the directive which will ultimately be imported.
        env.write('alpha.d.ts', `
        import {ɵɵDirectiveDefWithMeta, ɵɵNgModuleDefWithMeta} from '@angular/core';

        export declare class ExternalDir {
          static ɵdir: ɵɵDirectiveDefWithMeta<ExternalDir, '[test]', never, never, never, never>;
        }

        export declare class AlphaModule {
          static ɵmod: ɵɵNgModuleDefWithMeta<AlphaModule, [typeof ExternalDir], never, [typeof ExternalDir]>;
        }
      `);

        // 'beta' re-exports AlphaModule from alpha.
        env.write('beta.d.ts', `
        import {ɵɵNgModuleDefWithMeta} from '@angular/core';
        import {AlphaModule} from './alpha';

        export declare class BetaModule {
          static ɵmod: ɵɵNgModuleDefWithMeta<AlphaModule, never, never, [typeof AlphaModule]>;
        }
      `);

        // The application imports BetaModule from beta, gaining visibility of
        // ExternalDir from alpha.
        env.write('test.ts', `
        import {Component, NgModule} from '@angular/core';
        import {BetaModule} from './beta';

        @Component({
          selector: 'cmp',
          template: '<div test></div>',
        })
        export class Cmp {}

        @NgModule({
          declarations: [Cmp],
          imports: [BetaModule],
        })
        export class Module {}
      `);
        env.driveMain();
        const jsContents = env.getContents('test.js');

        // Expect that ExternalDir from alpha is imported via the re-export from beta.
        expect(jsContents).toContain('import * as i1 from "root/beta";');
        expect(jsContents).toContain('directives: [i1.\u0275ng$root$alpha$$ExternalDir]');
      });

      it('should write alias ES2015 exports for NgModule exported directives', () => {
        env.tsconfig({'_useHostForImportGeneration': true});
        env.write('external.d.ts', `
        import {ɵɵDirectiveDefWithMeta, ɵɵNgModuleDefWithMeta} from '@angular/core';
        import {LibModule} from './lib';

        export declare class ExternalDir {
          static ɵdir: ɵɵDirectiveDefWithMeta<ExternalDir, '[test]', never, never, never, never>;
        }

        export declare class ExternalModule {
          static ɵmod: ɵɵNgModuleDefWithMeta<ExternalModule, [typeof ExternalDir], never, [typeof ExternalDir, typeof LibModule]>;
        }
      `);
        env.write('lib.d.ts', `
        import {ɵɵDirectiveDefWithMeta, ɵɵNgModuleDefWithMeta} from '@angular/core';

        export declare class LibDir {
          static ɵdir: ɵɵDirectiveDefWithMeta<LibDir, '[lib]', never, never, never, never>;
        }

        export declare class LibModule {
          static ɵmod: ɵɵNgModuleDefWithMeta<LibModule, [typeof LibDir], never, [typeof LibDir]>;
        }
      `);
        env.write('foo.ts', `
        import {Directive, NgModule} from '@angular/core';
        import {ExternalModule} from './external';

        @Directive({selector: '[foo]'})
        export class FooDir {}

        @NgModule({
          declarations: [FooDir],
          exports: [FooDir, ExternalModule]
        })
        export class FooModule {}
      `);
        env.write('index.ts', `
        import {Component, NgModule} from '@angular/core';
        import {FooModule} from './foo';

        @Component({
          selector: 'index',
          template: '<div foo test lib></div>',
        })
        export class IndexCmp {}

        @NgModule({
          declarations: [IndexCmp],
          exports: [FooModule],
        })
        export class IndexModule {}
      `);
        env.driveMain();
        const jsContents = env.getContents('index.js');
        expect(jsContents)
            .toContain('export { FooDir as \u0275ng$root$foo$$FooDir } from "root/foo";');
      });

      it('should escape unusual characters in aliased filenames', () => {
        env.tsconfig({'_useHostForImportGeneration': true});
        env.write('other._$test.ts', `
        import {Directive, NgModule} from '@angular/core';

        @Directive({selector: 'test'})
        export class TestDir {}

        @NgModule({
          declarations: [TestDir],
          exports: [TestDir],
        })
        export class OtherModule {}
      `);
        env.write('index.ts', `
        import {NgModule} from '@angular/core';
        import {OtherModule} from './other._$test';

        @NgModule({
          exports: [OtherModule],
        })
        export class IndexModule {}
      `);
        env.driveMain();
        const jsContents = env.getContents('index.js');
        expect(jsContents)
            .toContain(
                'export { TestDir as \u0275ng$root$other___test$$TestDir } from "root/other._$test";');
      });
    });

    describe('disableTypeScriptVersionCheck', () => {
      afterEach(() => restoreTypeScriptVersionForTesting());

      it('produces an error when not supported and version check is enabled', () => {
        setTypeScriptVersionForTesting('3.4.0');
        env.tsconfig({disableTypeScriptVersionCheck: false});
        env.write('empty.ts', '');

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(1);
        expect(diags[0].messageText).toContain('but 3.4.0 was found instead');
      });

      it('does not produce an error when supported and version check is enabled', () => {
        env.tsconfig({disableTypeScriptVersionCheck: false});
        env.write('empty.ts', '');

        // The TypeScript version is not overwritten, so the version
        // that is actually used should be supported
        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(0);
      });

      it('does not produce an error when not supported but version check is disabled', () => {
        setTypeScriptVersionForTesting('3.4.0');
        env.tsconfig({disableTypeScriptVersionCheck: true});
        env.write('empty.ts', '');

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(0);
      });

      it('produces an error when not supported using default configuration', () => {
        setTypeScriptVersionForTesting('3.4.0');
        env.write('empty.ts', '');

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(1);
        expect(diags[0].messageText).toContain('but 3.4.0 was found instead');
      });
    });

    describe('inherited directives', () => {
      beforeEach(() => {
        env.write('local.ts', `
          import {Component, Directive, ElementRef} from '@angular/core';

          export class BasePlain {}

          export class BasePlainWithBlankConstructor {
            constructor() {}
          }

          export class BasePlainWithConstructorParameters {
            constructor(elementRef: ElementRef) {}
          }

          @Component({
            selector: 'base-cmp',
            template: 'BaseCmp',
          })
          export class BaseCmp {}

          @Directive({
            selector: '[base]',
          })
          export class BaseDir {}
        `);

        env.write('lib.d.ts', `
          import {ɵɵComponentDefWithMeta, ɵɵDirectiveDefWithMeta, ElementRef} from '@angular/core';

          export declare class BasePlain {}

          export declare class BasePlainWithBlankConstructor {
            constructor() {}
          }

          export declare class BasePlainWithConstructorParameters {
            constructor(elementRef: ElementRef) {}
          }

          export declare class BaseCmp {
            static ɵcmp: ɵɵComponentDefWithMeta<BaseCmp, "base-cmp", never, {}, {}, never>
          }

          export declare class BaseDir {
            static ɵdir: ɵɵDirectiveDefWithMeta<BaseDir, '[base]', never, never, never, never>;
          }
        `);
      });

      it('should not error when inheriting a constructor from a decorated directive class', () => {
        env.tsconfig();
        env.write('test.ts', `
          import {Directive, Component} from '@angular/core';
          import {BaseDir, BaseCmp} from './local';

          @Directive({
            selector: '[dir]',
          })
          export class Dir extends BaseDir {}

          @Component({
            selector: 'test-cmp',
            template: 'TestCmp',
          })
          export class Cmp extends BaseCmp {}
        `);
        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(0);
      });

      it('should not error when inheriting a constructor without parameters', () => {
        env.tsconfig();
        env.write('test.ts', `
          import {Directive, Component} from '@angular/core';
          import {BasePlainWithBlankConstructor} from './local';

          @Directive({
            selector: '[dir]',
          })
          export class Dir extends BasePlainWithBlankConstructor {}

          @Component({
            selector: 'test-cmp',
            template: 'TestCmp',
          })
          export class Cmp extends BasePlainWithBlankConstructor {}
        `);
        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(0);
      });

      it('should not error when inheriting from a class without a constructor', () => {
        env.tsconfig();
        env.write('test.ts', `
          import {Directive, Component} from '@angular/core';
          import {BasePlain} from './local';

          @Directive({
            selector: '[dir]',
          })
          export class Dir extends BasePlain {}

          @Component({
            selector: 'test-cmp',
            template: 'TestCmp',
          })
          export class Cmp extends BasePlain {}
        `);
        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(0);
      });

      it('should error when inheriting a constructor from an undecorated class', () => {
        env.tsconfig();
        env.write('test.ts', `
          import {Directive, Component} from '@angular/core';
          import {BasePlainWithConstructorParameters} from './local';

          @Directive({
            selector: '[dir]',
          })
          export class Dir extends BasePlainWithConstructorParameters {}

          @Component({
            selector: 'test-cmp',
            template: 'TestCmp',
          })
          export class Cmp extends BasePlainWithConstructorParameters {}
        `);
        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(2);
        expect(diags[0].messageText).toContain('Dir');
        expect(diags[0].messageText).toContain('BasePlainWithConstructorParameters');
        expect(diags[1].messageText).toContain('Cmp');
        expect(diags[1].messageText).toContain('BasePlainWithConstructorParameters');
      });

      it('should error when inheriting a constructor from undecorated grand super class', () => {
        env.tsconfig();
        env.write('test.ts', `
          import {Directive, Component} from '@angular/core';
          import {BasePlainWithConstructorParameters} from './local';

          class Parent extends BasePlainWithConstructorParameters {}

          @Directive({
            selector: '[dir]',
          })
          export class Dir extends Parent {}

          @Component({
            selector: 'test-cmp',
            template: 'TestCmp',
          })
          export class Cmp extends Parent {}
        `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(2);
        expect(diags[0].messageText).toContain('Dir');
        expect(diags[0].messageText).toContain('BasePlainWithConstructorParameters');
        expect(diags[1].messageText).toContain('Cmp');
        expect(diags[1].messageText).toContain('BasePlainWithConstructorParameters');
      });

      it('should error when inheriting a constructor from undecorated grand grand super class',
         () => {
           env.tsconfig();
           env.write('test.ts', `
              import {Directive, Component} from '@angular/core';
              import {BasePlainWithConstructorParameters} from './local';

              class GrandParent extends BasePlainWithConstructorParameters {}

              class Parent extends GrandParent {}

              @Directive({
                selector: '[dir]',
              })
              export class Dir extends Parent {}

              @Component({
                selector: 'test-cmp',
                template: 'TestCmp',
              })
              export class Cmp extends Parent {}
            `);

           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(2);
           expect(diags[0].messageText).toContain('Dir');
           expect(diags[0].messageText).toContain('BasePlainWithConstructorParameters');
           expect(diags[1].messageText).toContain('Cmp');
           expect(diags[1].messageText).toContain('BasePlainWithConstructorParameters');
         });

      it('should not error when inheriting a constructor from decorated directive or component classes in a .d.ts file',
         () => {
           env.tsconfig();
           env.write('test.ts', `
              import {Component, Directive} from '@angular/core';
              import {BaseDir, BaseCmp} from './lib';

              @Directive({
                selector: '[dir]',
              })
              export class Dir extends BaseDir {}

              @Component({
                selector: 'test-cmp',
                template: 'TestCmp',
              })
              export class Cmp extends BaseCmp {}
           `);
           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(0);
         });

      it('should error when inheriting a constructor from an undecorated class in a .d.ts file',
         () => {
           env.tsconfig();
           env.write('test.ts', `
              import {Directive} from '@angular/core';

              import {BasePlainWithConstructorParameters} from './lib';

              @Directive({
                selector: '[dir]',
              })
              export class Dir extends BasePlainWithConstructorParameters {}
            `);
           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(1);
           expect(diags[0].messageText).toContain('Dir');
           expect(diags[0].messageText).toContain('Base');
         });
    });

    describe('inline resources', () => {
      it('should process inline <style> tags', () => {
        env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test',
          template: '<style>h1 {font-size: larger}</style>',
          styles: ['h2 {width: 10px}']
        })
        export class TestCmp {}
      `);

        env.driveMain();
        const jsContents = env.getContents('test.js');
        expect(jsContents)
            .toContain(
                'styles: ["h2[_ngcontent-%COMP%] {width: 10px}", "h1[_ngcontent-%COMP%] {font-size: larger}"]');
      });

      it('should process inline <link> tags', () => {
        env.write('style.css', `h1 {font-size: larger}`);
        env.write('test.ts', `
        import {Component} from '@angular/core';

        @Component({
          selector: 'test',
          template: '<link rel="stylesheet" href="./style.css">',
        })
        export class TestCmp {}
      `);

        env.driveMain();
        const jsContents = env.getContents('test.js');
        expect(jsContents).toContain('styles: ["h1[_ngcontent-%COMP%] {font-size: larger}"]');
      });
    });

    describe('non-exported classes', () => {
      beforeEach(() => env.tsconfig({compileNonExportedClasses: false}));

      it('should not emit directive definitions for non-exported classes if configured', () => {
        env.write('test.ts', `
          import {Directive} from '@angular/core';

          @Directive({
            selector: '[test]'
          })
          class TestDirective {}
        `);
        env.driveMain();
        const jsContents = env.getContents('test.js');

        expect(jsContents).not.toContain('defineDirective(');
        expect(jsContents).toContain('Directive({');
      });

      it('should not emit component definitions for non-exported classes if configured', () => {
        env.write('test.ts', `
          import {Component} from '@angular/core';

          @Component({
            selector: 'test',
            template: 'hello'
          })
          class TestComponent {}
        `);
        env.driveMain();
        const jsContents = env.getContents('test.js');

        expect(jsContents).not.toContain('defineComponent(');
        expect(jsContents).toContain('Component({');
      });

      it('should not emit module definitions for non-exported classes if configured', () => {
        env.write('test.ts', `
          import {NgModule} from '@angular/core';

          @NgModule({
            declarations: []
          })
          class TestModule {}
        `);
        env.driveMain();
        const jsContents = env.getContents('test.js');

        expect(jsContents).not.toContain('defineNgModule(');
        expect(jsContents).toContain('NgModule({');
      });
    });

    describe('undecorated providers', () => {
      it('should error when an undecorated class, with a non-trivial constructor, is provided directly in a module',
         () => {
           env.write('test.ts', `
            import {NgModule, NgZone} from '@angular/core';

            class NotAService {
              constructor(ngZone: NgZone) {}
            }

            @NgModule({
              providers: [NotAService]
            })
            export class SomeModule {}
          `);

           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(1);
           expect(diags[0].messageText).toContain('cannot be created via dependency injection');
         });

      it('should error when an undecorated class is provided via useClass', () => {
        env.write('test.ts', `
          import {NgModule, Injectable, NgZone} from '@angular/core';

          @Injectable({providedIn: 'root'})
          class Service {}

          class NotAService {
            constructor(ngZone: NgZone) {}
          }

          @NgModule({
            providers: [{provide: Service, useClass: NotAService}]
          })
          export class SomeModule {}
        `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(1);
        expect(diags[0].messageText).toContain('cannot be created via dependency injection');
      });

      it('should not error when an undecorated class is provided via useClass with deps', () => {
        env.write('test.ts', `
          import {NgModule, Injectable, NgZone} from '@angular/core';

          @Injectable({providedIn: 'root'})
          class Service {}

          class NotAService {
            constructor(ngZone: NgZone) {}
          }

          @NgModule({
            providers: [{provide: Service, useClass: NotAService, deps: [NgZone]}]
          })
          export class SomeModule {}
        `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(0);
      });

      it('should error when an undecorated class is provided via an array', () => {
        env.write('test.ts', `
          import {NgModule, Injectable, NgZone} from '@angular/core';

          @Injectable({providedIn: 'root'})
          class Service {}

          class NotAService {
            constructor(ngZone: NgZone) {}
          }

          @NgModule({
            providers: [Service, [NotAService]]
          })
          export class SomeModule {}
        `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(1);
        expect(diags[0].messageText).toContain('cannot be created via dependency injection');
      });

      it('should error when an undecorated class is provided to a directive', () => {
        env.write('test.ts', `
          import {NgModule, Directive, NgZone} from '@angular/core';

          class NotAService {
            constructor(ngZone: NgZone) {}
          }

          @Directive({
            selector: '[some-dir]',
            providers: [NotAService]
          })
          class SomeDirective {}

          @NgModule({
            declarations: [SomeDirective]
          })
          export class SomeModule {}
        `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(1);
        expect(diags[0].messageText).toContain('cannot be created via dependency injection');
      });

      it('should error when an undecorated class is provided to a component', () => {
        env.write('test.ts', `
          import {NgModule, Component, NgZone} from '@angular/core';

          class NotAService {
            constructor(ngZone: NgZone) {}
          }

          @Component({
            selector: 'some-comp',
            template: '',
            providers: [NotAService]
          })
          class SomeComponent {}

          @NgModule({
            declarations: [SomeComponent]
          })
          export class SomeModule {}
        `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(1);
        expect(diags[0].messageText).toContain('cannot be created via dependency injection');
      });

      it('should error when an undecorated class is provided to a component via viewProviders',
         () => {
           env.write('test.ts', `
          import {NgModule, Component, NgZone} from '@angular/core';

          class NotAService {
            constructor(ngZone: NgZone) {}
          }

          @Component({
            selector: 'some-comp',
            template: '',
            viewProviders: [NotAService]
          })
          class SomeComponent {}

          @NgModule({
            declarations: [SomeComponent]
          })
          export class SomeModule {}
        `);

           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(1);
           expect(diags[0].messageText).toContain('cannot be created via dependency injection');
         });

      it('should not error when a class with a factory is provided', () => {
        env.write('test.ts', `
          import {NgModule, Pipe} from '@angular/core';

          @Pipe({
            name: 'some-pipe'
          })
          class SomePipe {}

          @NgModule({
            declarations: [SomePipe],
            providers: [SomePipe]
          })
          export class SomeModule {}
        `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(0);
      });

      it('should not error when an NgModule is provided', () => {
        env.write('test.ts', `
          import {Injectable, NgModule} from '@angular/core';

          @Injectable()
          export class Service {}

          @NgModule({
          })
          class SomeModule {
            constructor(dep: Service) {}
          }

          @NgModule({
            providers: [SomeModule],
          })
          export class Module {}
        `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(0);
      });

      it('should not error when an undecorated class from a declaration file is provided', () => {
        env.write('node_modules/@angular/core/testing/index.d.ts', `
          export declare class Testability {
          }
        `);
        env.write('test.ts', `
          import {NgModule} from '@angular/core';
          import {Testability} from '@angular/core/testing';

          @NgModule({
            providers: [Testability]
          })
          export class SomeModule {}
        `);

        const diags = env.driveDiagnostics();
        expect(diags.length).toBe(0);
      });

      it('should not error when an undecorated class without a constructor from a declaration file is provided via useClass',
         () => {
           env.write('node_modules/@angular/core/testing/index.d.ts', `
            export declare class Testability {
            }
          `);
           env.write('test.ts', `
            import {NgModule, Injectable} from '@angular/core';
            import {Testability} from '@angular/core/testing';

            @Injectable()
            class TestingService {}

            @NgModule({
              providers: [{provide: TestingService, useClass: Testability}]
            })
            export class SomeModule {}
          `);

           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(0);
         });

      it('should not error if the undecorated class does not have a constructor or the constructor is blank',
         () => {
           env.write('test.ts', `
          import {NgModule, NgZone} from '@angular/core';

          class NoConstructorService {
          }

          class BlankConstructorService {
          }

          @NgModule({
            providers: [NoConstructorService, BlankConstructorService]
          })
          export class SomeModule {}
        `);

           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(0);
         });

      it('should error when an undecorated class with a non-trivial constructor in a declaration file is provided via useClass',
         () => {
           env.write('node_modules/@angular/core/testing/index.d.ts', `
            export declare class NgZone {}

            export declare class Testability {
              constructor(ngZone: NgZone) {}
            }
          `);
           env.write('test.ts', `
            import {NgModule, Injectable} from '@angular/core';
            import {Testability} from '@angular/core/testing';

            @Injectable()
            class TestingService {}

            @NgModule({
              providers: [{provide: TestingService, useClass: Testability}]
            })
            export class SomeModule {}
          `);

           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(1);
           expect(diags[0].messageText).toContain('cannot be created via dependency injection');
         });

      it('should not error when an class with a factory definition and a non-trivial constructor in a declaration file is provided via useClass',
         () => {
           env.write('node_modules/@angular/core/testing/index.d.ts', `
            import * as i0 from '@angular/core';

            export declare class NgZone {}

            export declare class Testability {
              static ɵfac: i0.ɵɵFactoryDef<Testability, never>;
              constructor(ngZone: NgZone) {}
            }
          `);
           env.write('test.ts', `
            import {NgModule, Injectable} from '@angular/core';
            import {Testability} from '@angular/core/testing';

            @Injectable()
            class TestingService {}

            @NgModule({
              providers: [{provide: TestingService, useClass: Testability}]
            })
            export class SomeModule {}
          `);

           const diags = env.driveDiagnostics();
           expect(diags.length).toBe(0);
         });
    });
  });

  function expectTokenAtPosition<T extends ts.Node>(
      sf: ts.SourceFile, pos: number, guard: (node: ts.Node) => node is T): T {
    // getTokenAtPosition is part of TypeScript's private API.
    const node = (ts as any).getTokenAtPosition(sf, pos) as ts.Node;
    expect(guard(node)).toBe(true);
    return node as T;
  }

  function normalize(input: string): string {
    return input.replace(/\s+/g, ' ').trim();
  }
});
