/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {Component, Injectable, INJECTOR, NgModule} from '@angular/core';
import {TestBed} from '@angular/core/testing';
import {renderModuleFactory} from '@angular/platform-server';
import {BasicAppModuleNgFactory} from 'app_built/src/basic.ngfactory';
import {DepAppModuleNgFactory} from 'app_built/src/dep.ngfactory';
import {HierarchyAppModuleNgFactory} from 'app_built/src/hierarchy.ngfactory';
import {RootAppModuleNgFactory} from 'app_built/src/root.ngfactory';
import {SelfAppModuleNgFactory} from 'app_built/src/self.ngfactory';
import {StringAppModuleNgFactory} from 'app_built/src/string.ngfactory';
import {TokenAppModuleNgFactory} from 'app_built/src/token.ngfactory';

describe('ngInjectableDef Bazel Integration', () => {
  it('works in AOT', done => {
    renderModuleFactory(BasicAppModuleNgFactory, {
      document: '<id-app></id-app>',
      url: '/',
    }).then(html => {
      expect(html).toMatch(/>0:0<\//);
      done();
    });
  });

  it('@Self() works in component hierarchies', done => {
    renderModuleFactory(HierarchyAppModuleNgFactory, {
      document: '<hierarchy-app></hierarchy-app>',
      url: '/',
    }).then(html => {
      expect(html).toMatch(/>false<\//);
      done();
    });
  });

  it('@Optional() Self() resolves to @Injectable() scoped service', done => {
    renderModuleFactory(SelfAppModuleNgFactory, {
      document: '<self-app></self-app>',
      url: '/',
    }).then(html => {
      expect(html).toMatch(/>true<\//);
      done();
    });
  });

  it('InjectionToken ngInjectableDef works', done => {
    renderModuleFactory(TokenAppModuleNgFactory, {
      document: '<token-app></token-app>',
      url: '/',
    }).then(html => {
      expect(html).toMatch(/>fromToken<\//);
      done();
    });
  });

  it('APP_ROOT_SCOPE works', done => {
    renderModuleFactory(RootAppModuleNgFactory, {
      document: '<root-app></root-app>',
      url: '/',
    }).then(html => {
      expect(html).toMatch(/>true:false<\//);
      done();
    });
  });

  it('can inject dependencies', done => {
    renderModuleFactory(DepAppModuleNgFactory, {
      document: '<dep-app></dep-app>',
      url: '/',
    }).then(html => {
      expect(html).toMatch(/>true<\//);
      done();
    });
  });

  it('string tokens work', done => {
    renderModuleFactory(StringAppModuleNgFactory, {
      document: '<string-app></string-app>',
      url: '/',
    }).then(html => {
      expect(html).toMatch(/>works<\//);
      done();
    });
  });

  it('allows provider override in JIT for root-scoped @Injectables', () => {
    @Injectable({
      providedIn: 'root',
      useValue: new Service('default'),
    })
    class Service {
      constructor(readonly value: string) {}
    }

    TestBed.configureTestingModule({});
    TestBed.overrideProvider(Service, {useValue: new Service('overridden')});

    expect(TestBed.inject(Service).value).toEqual('overridden');
  });

  it('allows provider override in JIT for module-scoped @Injectables', () => {
    @NgModule()
    class Module {
    }

    @Injectable({
      providedIn: Module,
      useValue: new Service('default'),
    })
    class Service {
      constructor(readonly value: string) {}
    }

    TestBed.configureTestingModule({
      imports: [Module],
    });
    TestBed.overrideProvider(Service, {useValue: new Service('overridden')});

    expect(TestBed.inject(Service).value).toEqual('overridden');
  });

  it('does not override existing ɵprov', () => {
    @Injectable({
      providedIn: 'root',
      useValue: new Service(false),
    })
    class Service {
      constructor(public value: boolean) {}
      static ɵprov = {
        providedIn: 'root',
        factory: () => new Service(true),
        token: Service,
      };
    }

    TestBed.configureTestingModule({});
    expect(TestBed.inject(Service).value).toEqual(true);
  });

  it('does not override existing ɵprov in case of inheritance', () => {
    @Injectable({
      providedIn: 'root',
      useValue: new ParentService(false),
    })
    class ParentService {
      constructor(public value: boolean) {}
    }

    // ChildServices exteds ParentService but does not have @Injectable
    class ChildService extends ParentService {}

    TestBed.configureTestingModule({});
    // We are asserting that system throws an error, rather than taking the inherited annotation.
    expect(() => TestBed.inject(ChildService).value).toThrowError(/ChildService/);
  });

  it('uses legacy `ngInjectable` property even if it inherits from a class that has `ɵprov` property',
     () => {
       @Injectable({
         providedIn: 'root',
         useValue: new ParentService('parent'),
       })
       class ParentService {
         constructor(public value: string) {}
       }

       // ChildServices exteds ParentService but does not have @Injectable
       class ChildService extends ParentService {
         constructor(value: string) {
           super(value);
         }
         static ngInjectableDef = {
           providedIn: 'root',
           factory: () => new ChildService('child'),
           token: ChildService,
         };
       }

       TestBed.configureTestingModule({});
       // We are asserting that system throws an error, rather than taking the inherited
       // annotation.
       expect(TestBed.inject(ChildService).value).toEqual('child');
     });

  it('NgModule injector understands requests for INJECTABLE', () => {
    TestBed.configureTestingModule({
      providers: [{provide: 'foo', useValue: 'bar'}],
    });
    expect(TestBed.inject(INJECTOR).get('foo')).toEqual('bar');
  });

  it('Component injector understands requests for INJECTABLE', () => {
    @Component({
      selector: 'test-cmp',
      template: 'test',
      providers: [{provide: 'foo', useValue: 'bar'}],
    })
    class TestCmp {
    }

    TestBed.configureTestingModule({
      declarations: [TestCmp],
    });

    const fixture = TestBed.createComponent(TestCmp);
    expect(fixture.componentRef.injector.get(INJECTOR).get('foo')).toEqual('bar');
  });
});
