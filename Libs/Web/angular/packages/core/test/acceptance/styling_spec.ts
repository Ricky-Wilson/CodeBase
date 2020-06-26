/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {CommonModule} from '@angular/common';
import {Component, ComponentFactoryResolver, ComponentRef, Directive, ElementRef, HostBinding, Input, NgModule, Renderer2, ViewChild, ViewContainerRef} from '@angular/core';
import {bypassSanitizationTrustStyle} from '@angular/core/src/sanitization/bypass';
import {ngDevModeResetPerfCounters} from '@angular/core/src/util/ng_dev_mode';
import {TestBed} from '@angular/core/testing';
import {getElementClasses, getElementStyles, getSortedClassName, getSortedStyle} from '@angular/core/testing/src/styling';
import {By, DomSanitizer, SafeStyle} from '@angular/platform-browser';
import {expect} from '@angular/platform-browser/testing/src/matchers';
import {ivyEnabled, modifiedInIvy, onlyInIvy} from '@angular/private/testing';

describe('styling', () => {
  beforeEach(ngDevModeResetPerfCounters);

  describe('apply in prioritization order', () => {
    it('should perform static bindings', () => {
      @Component({template: `<div class="STATIC" style="color: blue"></div>`})
      class Cmp {
      }

      TestBed.configureTestingModule({declarations: [Cmp]});
      const fixture = TestBed.createComponent(Cmp);

      const [staticDiv] = fixture.nativeElement.querySelectorAll('div');
      expect(getSortedClassName(staticDiv)).toEqual('STATIC');
      expect(getSortedStyle(staticDiv)).toEqual('color: blue;');
    });

    it('should perform prop bindings', () => {
      @Component({
        template: `<div [class.dynamic]="true"
                        [style.color]="'blue'"
                        [style.width.px]="100"></div>`
      })
      class Cmp {
      }

      TestBed.configureTestingModule({declarations: [Cmp]});
      const fixture = TestBed.createComponent(Cmp);
      fixture.detectChanges();

      const div = fixture.nativeElement.querySelector('div');
      expect(getSortedClassName(div)).toEqual('dynamic');
      expect(getSortedStyle(div)).toEqual('color: blue; width: 100px;');
    });

    onlyInIvy('style merging is ivy only feature').it('should perform map bindings', () => {
      @Component({
        template: `<div [class]="{dynamic: true}"
                        [style]="{color: 'blue', width: '100px'}"></div>`
      })
      class Cmp {
      }

      TestBed.configureTestingModule({declarations: [Cmp]});
      const fixture = TestBed.createComponent(Cmp);
      fixture.detectChanges();

      const div = fixture.nativeElement.querySelector('div');
      expect(getSortedClassName(div)).toEqual('dynamic');
      expect(getSortedStyle(div)).toEqual('color: blue; width: 100px;');
    });

    onlyInIvy('style merging is ivy only feature')
        .it('should perform interpolation bindings', () => {
          @Component({
            // TODO(misko): change `style-x` to `style` once #34202 lands
            template: `<div class="static {{'dynamic'}}"
                        style.color="blu{{'e'}}"
                        style-x="width: {{'100'}}px"></div>`
          })
          class Cmp {
          }

          TestBed.configureTestingModule({declarations: [Cmp]});
          const fixture = TestBed.createComponent(Cmp);
          fixture.detectChanges();

          const div = fixture.nativeElement.querySelector('div');
          expect(getSortedClassName(div)).toEqual('dynamic static');
          expect(getSortedStyle(div)).toEqual('color: blue;');
        });

    onlyInIvy('style merging is ivy only feature').it('should support hostBindings', () => {
      @Component({
        template:
            `<div my-host-bindings-2 my-host-bindings-1 class="STATIC" style="color: blue"></div>`
      })
      class Cmp {
      }
      @Directive({
        selector: '[my-host-bindings-1]',
        host: {'class': 'HOST_STATIC_1', 'style': 'font-family: "c1"'}
      })
      class Dir1 {
      }

      @Directive({
        selector: '[my-host-bindings-2]',
        host: {'class': 'HOST_STATIC_2', 'style': 'font-family: "c2"'}
      })
      class Dir2 {
      }

      TestBed.configureTestingModule({
        declarations: [
          // Order of directives in the template does not matter.
          // Order of declarations matters as it determines the relative priority for overrides.
          Dir1,
          Dir2,
          // Even thought component is at the end, it will still have lowest priority because
          // components are special that way.
          Cmp,
        ]
      });
      const fixture = TestBed.createComponent(Cmp);
      fixture.detectChanges();

      const div = fixture.nativeElement.querySelector('div');
      expect(getSortedClassName(div)).toEqual('HOST_STATIC_1 HOST_STATIC_2 STATIC');
      expect(getSortedStyle(div)).toEqual('color: blue; font-family: c2;');
    });

    it('should support hostBindings inheritance', () => {
      @Component({template: `<div my-host-bindings class="STATIC" style="color: blue;"></div>`})
      class Cmp {
      }
      @Directive({host: {'class': 'SUPER_STATIC', 'style': 'font-family: "super"; width: "1px";'}})
      class SuperDir {
      }
      @Directive({
        selector: '[my-host-bindings]',
        host: {'class': 'HOST_STATIC', 'style': 'font-family: "host font"'}
      })
      class Dir extends SuperDir {
      }

      TestBed.configureTestingModule({declarations: [Cmp, Dir]});
      const fixture = TestBed.createComponent(Cmp);
      fixture.detectChanges();

      const div = fixture.nativeElement.querySelector('div');
      expect(getSortedClassName(div))
          .toEqual(ivyEnabled ? 'HOST_STATIC STATIC SUPER_STATIC' : 'HOST_STATIC STATIC');
      // Browsers keep the '"' around the font name, but Domino removes it some we do search and
      // replace. Yes we could do `replace(/"/g, '')` but that fails on android.
      expect(getSortedStyle(div).replace('"', '').replace('"', ''))
          .toEqual(
              ivyEnabled ? 'color: blue; font-family: host font; width: 1px;' :
                           'color: blue; font-family: host font;');
    });

    onlyInIvy('style merging is ivy only feature')
        .it('should apply template classes in correct order', () => {
          @Component({
            template: `
        <div class="STATIC DELETE_MAP_A DELETE_PROP_B"
             [class]="{foo: true, DELETE_MAP_A: false}"
             [class.bar]="true"
             [class.DELETE_PROP_B]="false"></div>
        `
          })
          class Cmp {
          }

          TestBed.configureTestingModule({declarations: [Cmp]});
          const fixture = TestBed.createComponent(Cmp);
          fixture.detectChanges();

          const classDiv = fixture.nativeElement.querySelector('div');
          expect(getSortedClassName(classDiv)).toEqual('STATIC bar foo');
        });

    onlyInIvy('style merging is ivy only feature')
        .it('should apply template styles in correct order', () => {
          @Component({
            template: `
        <div style="width: 100px; height: 200px: color: red; background-color: yellow"
             [style]="{width: '110px', height: null}"
             [style.color]=" 'blue' "
             [style.height.px]="undefined"></div>
        `
          })
          class Cmp {
          }

          TestBed.configureTestingModule({declarations: [Cmp]});
          const fixture = TestBed.createComponent(Cmp);
          fixture.detectChanges();

          const styleDiv = fixture.nativeElement.querySelector('div');
          expect(getSortedStyle(styleDiv))
              .toEqual('background-color: yellow; color: blue; width: 110px;');
        });

    it('should work with ngClass/ngStyle', () => {
      @Component(
          {template: `<div [ngClass]="['dynamic']" [ngStyle]="{'font-family': 'dynamic'}"></div>`})
      class Cmp {
      }
      TestBed.configureTestingModule({declarations: [Cmp]});
      const fixture = TestBed.createComponent(Cmp);
      fixture.detectChanges();

      const div = fixture.nativeElement.querySelector('div');
      expect(getSortedClassName(div)).toEqual('dynamic');
      expect(getSortedStyle(div)).toEqual('font-family: dynamic;');
    });
  });

  describe('css variables', () => {
    onlyInIvy('css variables').it('should support css variables', () => {
      // This test only works in browsers which support CSS variables.
      if (!(typeof getComputedStyle !== 'undefined' && typeof CSS !== 'undefined' &&
            typeof CSS.supports !== 'undefined' && CSS.supports('color', 'var(--fake-var)')))
        return;
      @Component({
        template: `
            <div [style.--my-var]=" '100px' ">
              <span style="width: var(--my-var)">CONTENT</span>
            </div>`
      })
      class Cmp {
      }
      TestBed.configureTestingModule({declarations: [Cmp]});
      const fixture = TestBed.createComponent(Cmp);
      // document.body.appendChild(fixture.nativeElement);
      fixture.detectChanges();

      const span = fixture.nativeElement.querySelector('span') as HTMLElement;
      expect(getComputedStyle(span).getPropertyValue('width')).toEqual('100px');
    });
  });

  modifiedInIvy('shadow bindings include static portion')
      .it('should bind [class] as input to directive', () => {
        // VE Behavior https://stackblitz.com/edit/angular-cycpsf
        // IVY behavior is slightly different see next test with same name.
        @Component({
          template: `
      <div class="s1" [class]=" 'd1' " dir-shadows-class-input></div>
      <div class="s2 {{'d2'}}" dir-shadows-class-input></div>
      `
        })
        class Cmp {
        }

        @Directive({selector: '[dir-shadows-class-input]'})
        class DirectiveShadowsClassInput {
          constructor(private elementRef: ElementRef) {}
          @Input('class')
          set klass(value: string) {
            this.elementRef.nativeElement.setAttribute('shadow-class', value);
          }
        }

        TestBed.configureTestingModule({declarations: [Cmp, DirectiveShadowsClassInput]});
        const fixture = TestBed.createComponent(Cmp);
        fixture.detectChanges();

        const [div1, div2] = fixture.nativeElement.querySelectorAll('div');
        // Static value `class="s1"` is always written to the DOM.
        expect(div1.className).toEqual('s1');
        // VE passes the dynamic portion of `class` to the directive.
        expect(div1.getAttribute('shadow-class')).toEqual('d1');
        // Interpolation `class="s2 {{'d2'}}"` does not have a static portion and so no value is
        // written to DOM.
        expect(div2.className).toEqual('');
        expect(div2.getAttribute('shadow-class')).toEqual('s2 d2');
      });


  onlyInIvy('shadow bindings include static portion')
      .it('should bind [class] as input to directive', () => {
        // VE Behavior https://stackblitz.com/edit/angular-cycpsf
        // IVY behavior is slightly different see next test with same name.
        @Component({
          template: `
      <div class="s1" [class]=" 'd1' " dir-shadows-class-input></div>
      <div class="s2 {{'d2'}}" dir-shadows-class-input></div>
      `
        })
        class Cmp {
        }

        @Directive({selector: '[dir-shadows-class-input]'})
        class DirectiveShadowsClassInput {
          constructor(private elementRef: ElementRef) {}
          @Input('class')
          set klass(value: string) {
            this.elementRef.nativeElement.setAttribute('shadow-class', value);
          }
        }

        TestBed.configureTestingModule({declarations: [Cmp, DirectiveShadowsClassInput]});
        const fixture = TestBed.createComponent(Cmp);
        fixture.detectChanges();

        const [div1, div2] = fixture.nativeElement.querySelectorAll('div');
        // Static value `class="s1"` is always written to the DOM.
        expect(div1.className).toEqual('s1');
        // VE has weird behavior where it calls the @Input('class') with either `class="static` or
        // `[class]="dynamic"` but never both. This is determined at compile time. Due to locality
        // we don't know if `[class]` is coming if we see `class` only. So we need to combine the
        // static and dynamic parts. This results in slightly different calling sequence, but should
        // result in the same final DOM.
        expect(div1.getAttribute('shadow-class')).toEqual('s1 d1');

        expect(div2.className).toEqual('');
        expect(div2.getAttribute('shadow-class')).toEqual('s2 d2');
      });

  it('should not feed host classes back into shadow input', () => {
    @Component({
      template: `
          <div class="s1" dir-shadows-class-input></div>
          <div class="s1" [class]=" 'd1' " dir-shadows-class-input></div>
          `
    })
    class Cmp {
    }

    @Directive({selector: '[dir-shadows-class-input]', host: {'class': 'DIRECTIVE'}})
    class DirectiveShadowsClassInput {
      constructor(private elementRef: ElementRef) {}
      @Input('class')
      set klass(value: string) {
        this.elementRef.nativeElement.setAttribute('shadow-class', value);
      }
    }

    TestBed.configureTestingModule({declarations: [Cmp, DirectiveShadowsClassInput]});
    const fixture = TestBed.createComponent(Cmp);
    fixture.detectChanges();

    const [divStatic, divBinding] = fixture.nativeElement.querySelectorAll('div');
    expectClass(divStatic).toEqual({'DIRECTIVE': true, 's1': true});
    expect(divStatic.getAttribute('shadow-class')).toEqual('s1');

    expectClass(divBinding).toEqual({'DIRECTIVE': true, 's1': true});
    // VE has weird behavior where it calls the @Input('class') with either `class="static` or
    // `[class]="dynamic"` but never both. This is determined at compile time. Due to locality
    // we don't know if `[class]` is coming if we see `class` only. So we need to combine the
    // static and dynamic parts. This results in slightly different calling sequence, but should
    // result in the same final DOM.
    expect(divBinding.getAttribute('shadow-class')).toEqual(ivyEnabled ? 's1 d1' : 'd1');
  });

  it('should not feed host style back into shadow input', () => {
    @Component({
      template: `
          <div style="width: 1px;" dir-shadows-class-input></div>
          <div style="width: 1px;" [style]=" 'height:1px;' " dir-shadows-class-input></div>
          `
    })
    class Cmp {
    }

    @Directive({selector: '[dir-shadows-class-input]', host: {'style': 'color: red;'}})
    class DirectiveShadowsStyleInput {
      constructor(private elementRef: ElementRef) {}
      @Input('style')
      set style(value: string) {
        this.elementRef.nativeElement.setAttribute('shadow-style', value);
      }
    }

    TestBed.configureTestingModule({declarations: [Cmp, DirectiveShadowsStyleInput]});
    const fixture = TestBed.createComponent(Cmp);
    fixture.detectChanges();

    const [divStatic, divBinding] = fixture.nativeElement.querySelectorAll('div');
    expectStyle(divStatic).toEqual({'color': 'red', 'width': '1px'});
    expect(divStatic.getAttribute('shadow-style')).toEqual('width: 1px;');

    expectStyle(divBinding).toEqual({'color': 'red', 'width': '1px'});
    // VE has weird behavior where it calls the @Input('style') with either `style="static` or
    // `[style]="dynamic"` but never both. This is determined at compile time. Due to locality
    // we don't know if `[style]` is coming if we see `style` only. So we need to combine the
    // static and dynamic parts. This results in slightly different calling sequence, but should
    // result in the same final DOM.
    expect(divBinding.getAttribute('shadow-style'))
        .toEqual(ivyEnabled ? 'width: 1px; height:1px;' : 'height:1px;');
  });

  onlyInIvy('shadow bindings include static portion')
      .it('should bind [class] as input to directive when both static and falsy dynamic values are present',
          () => {
            @Component({
              template: `
                <div class="s1" [class]="classBinding" dir-shadows-class-input></div>
              `
            })
            class Cmp {
              classBinding: any = undefined;
            }

            @Directive({selector: '[dir-shadows-class-input]'})
            class DirectiveShadowsClassInput {
              constructor(private elementRef: ElementRef) {}
              @Input('class')
              set klass(value: string) {
                this.elementRef.nativeElement.setAttribute('shadow-class', value);
              }
            }

            TestBed.configureTestingModule({declarations: [Cmp, DirectiveShadowsClassInput]});
            const fixture = TestBed.createComponent(Cmp);
            fixture.detectChanges();

            const div = fixture.nativeElement.querySelector('div');
            expect(div.className).toEqual('s1');
            expect(div.getAttribute('shadow-class')).toEqual('s1');

            fixture.componentInstance.classBinding = null;
            fixture.detectChanges();
            expect(div.className).toEqual('s1');
            expect(div.getAttribute('shadow-class')).toEqual('s1');

            fixture.componentInstance.classBinding = false;
            fixture.detectChanges();
            expect(div.className).toEqual('s1');
            expect(div.getAttribute('shadow-class')).toEqual('s1');


            fixture.componentInstance.classBinding = {toString: () => 'd1'};
            fixture.detectChanges();
            expect(div.className).toEqual('s1');
            expect(div.getAttribute('shadow-class')).toEqual('s1 d1');
          });


  modifiedInIvy('shadow bindings include static portion')
      .it('should bind [style] as input to directive', () => {
        // VE Behavior https://stackblitz.com/edit/angular-cycpsf
        @Component({
          template: `
          <div style="color: red;" [style]=" 'width: 100px;' " dir-shadows-style-input></div>
          `
        })
        class Cmp {
        }

        @Directive({selector: '[dir-shadows-style-input]'})
        class DirectiveShadowsStyleInput {
          constructor(private elementRef: ElementRef) {}
          @Input('style')
          set style(value: string) {
            this.elementRef.nativeElement.setAttribute('shadow-style', value);
          }
        }

        TestBed.configureTestingModule({declarations: [Cmp, DirectiveShadowsStyleInput]});
        const fixture = TestBed.createComponent(Cmp);
        fixture.detectChanges();

        const div = fixture.nativeElement.querySelector('div');
        expect(div.style.cssText).toEqual('color: red;');
        // VE has weird behavior where it calls the @Input('class') with either `class="static` or
        // `[class]="dynamic"` but never both. This is determined at compile time. Due to locality
        // we
        // don't know if `[class]` is coming if we see `class` only. So we need to combine the two
        // This results in slightly different calling sequence, but should result in the same final
        // DOM.
        expect(div.getAttribute('shadow-style')).toEqual('width: 100px;');
      });

  onlyInIvy('shadow bindings include static portion')
      .it('should bind [style] as input to directive', () => {
        // VE Behavior https://stackblitz.com/edit/angular-cycpsf
        @Component({
          template: `
          <div style="color: red;" [style]=" 'width: 100px;' " dir-shadows-style-input></div>
          `
        })
        class Cmp {
        }

        @Directive({selector: '[dir-shadows-style-input]'})
        class DirectiveShadowsStyleInput {
          constructor(private elementRef: ElementRef) {}
          @Input('style')
          set style(value: string) {
            this.elementRef.nativeElement.setAttribute('shadow-style', value);
          }
        }

        TestBed.configureTestingModule({declarations: [Cmp, DirectiveShadowsStyleInput]});
        const fixture = TestBed.createComponent(Cmp);
        fixture.detectChanges();

        const div = fixture.nativeElement.querySelector('div');
        expect(div.style.cssText).toEqual('color: red;');
        // VE has weird behavior where it calls the @Input('class') with either `class="static` or
        // `[class]="dynamic"` but never both. This is determined at compile time. Due to locality
        // we
        // don't know if `[class]` is coming if we see `class` only. So we need to combine the two
        // This results in slightly different calling sequence, but should result in the same final
        // DOM.
        expect(div.getAttribute('shadow-style')).toEqual('color: red; width: 100px;');
      });

  it('should prevent circular ExpressionChangedAfterItHasBeenCheckedError on shadow inputs', () => {
    @Component({template: `<div class="s1" dir-shadows-class-input></div>`})
    class Cmp {
    }

    @Directive({selector: '[dir-shadows-class-input]'})
    class DirectiveShadowsClassInput {
      @Input('class') klass: string|undefined;

      @HostBinding('class')
      get hostClasses() {
        return `${this.klass} SUFFIX`;
      }
    }

    TestBed.configureTestingModule({declarations: [Cmp, DirectiveShadowsClassInput]});
    const fixture = TestBed.createComponent(Cmp);
    expect(() => fixture.detectChanges()).not.toThrow();

    const div = fixture.nativeElement.querySelector('div');
    expect(div.className).toEqual('s1 SUFFIX');
  });

  it('should recover from exceptions', () => {
    @Component({
      template: `
      <div [id]="maybeThrow(id)">
        <span my-dir [class]="maybeThrow(klass)" [class.foo]="maybeThrow(foo)"></span>
      </div>
      `
    })
    class Cmp {
      id = 'throw_id';
      klass: string|string[] = 'throw_klass';
      foo = `throw_foo`;

      maybeThrow(value: any) {
        if (typeof value === 'string' && value.indexOf('throw') === 0) {
          throw new Error(value);
        }
        return value;
      }
    }

    let myDirHostBinding = false;
    @Directive({selector: '[my-dir]'})
    class MyDirective {
      @HostBinding('class.myDir')
      get myDir(): boolean {
        if (myDirHostBinding === false) {
          throw new Error('class.myDir');
        }
        return myDirHostBinding;
      }
    }

    TestBed.configureTestingModule({declarations: [Cmp, MyDirective]});
    const fixture = TestBed.createComponent(Cmp);
    const cmp = fixture.componentInstance;
    const div = fixture.nativeElement.querySelector('div');
    const span = fixture.nativeElement.querySelector('span');

    expect(() => fixture.detectChanges()).toThrowError(/throw_id/);
    expect(div.id).toBeFalsy();
    expectClass(span).toEqual({});

    cmp.id = 'myId';
    expect(() => fixture.detectChanges()).toThrowError(/throw_klass/);
    expect(div.id).toEqual('myId');
    expectClass(span).toEqual({});

    cmp.klass = ['BAR'];
    expect(() => fixture.detectChanges()).toThrowError(/throw_foo/);
    expect(div.id).toEqual('myId');
    expectClass(span).toEqual(ivyEnabled ? {BAR: true} : {});

    cmp.foo = 'foo';
    expect(() => fixture.detectChanges()).toThrowError(/class.myDir/);
    expect(div.id).toEqual('myId');
    expectClass(span).toEqual(ivyEnabled ? {BAR: true, foo: true} : {});

    myDirHostBinding = true;
    fixture.detectChanges();
    expect(div.id).toEqual('myId');
    expectClass(span).toEqual({BAR: true, foo: true, myDir: true});
  });

  it('should render inline style and class attribute values on the element before a directive is instantiated',
     () => {
       @Component({
         template: `
        <div directive-expecting-styling style="width:200px" class="abc xyz"></div>
      `
       })
       class Cmp {
       }

       @Directive({selector: '[directive-expecting-styling]'})
       class DirectiveExpectingStyling {
         constructor(elm: ElementRef) {
           const native = elm.nativeElement;
           native.setAttribute('data-captured-width', native.style.width);
           native.setAttribute('data-captured-classes', native.className);
         }
       }

       TestBed.configureTestingModule({declarations: [Cmp, DirectiveExpectingStyling]});
       const fixture = TestBed.createComponent(Cmp);
       fixture.detectChanges();

       const element = fixture.nativeElement.querySelector('div');
       expect(element.style.width).toEqual('200px');
       expect(element.getAttribute('data-captured-width')).toEqual('200px');
       expect(element.className.trim()).toEqual('abc xyz');
       expect(element.getAttribute('data-captured-classes')).toEqual('abc xyz');
     });

  it('should only render the same initial styling values once before a directive runs', () => {
    @Component({
      template: `
        <div directive-expecting-styling style="width:200px" class="abc"></div>
      `
    })
    class Cmp {
    }

    @Directive({selector: '[directive-expecting-styling]'})
    class DirectiveExpectingStyling {
      constructor(elm: ElementRef) {
        const native = elm.nativeElement;
        native.style.width = '300px';
        native.classList.remove('abc');
      }
    }

    TestBed.configureTestingModule({declarations: [Cmp, DirectiveExpectingStyling]});
    const fixture = TestBed.createComponent(Cmp);
    fixture.detectChanges();

    const element = fixture.nativeElement.querySelector('div');
    expect(element.style.width).toEqual('300px');
    expect(element.classList.contains('abc')).toBeFalsy();
  });

  it('should ensure that static classes are assigned to ng-container elements and picked up for content projection',
     () => {
       @Component({
         template: `
            <project>
              outer
              <ng-container class="inner">
                inner
              </ng-container>
            </project>
          `
       })
       class MyApp {
       }

       @Component({
         selector: 'project',
         template: `
            <div class="outer-area">
              <ng-content></ng-content>
            </div>
            <div class="inner-area">
              <ng-content select=".inner"></ng-content>
            </div>
          `
       })
       class ProjectCmp {
       }

       TestBed.configureTestingModule({declarations: [MyApp, ProjectCmp]});
       const fixture = TestBed.createComponent(MyApp);
       const element = fixture.nativeElement;
       fixture.detectChanges();

       const inner = element.querySelector('.inner-area');
       expect(inner.textContent.trim()).toEqual('inner');
       const outer = element.querySelector('.outer-area');
       expect(outer.textContent.trim()).toEqual('outer');
     });

  it('should render initial styling for repeated nodes that a component host', () => {
    @Component({
      selector: '[comp]',
      template: '',
    })
    class Comp {
    }

    @Component({
      template: `
        <ng-template ngFor [ngForOf]="items" let-item>
          <p comp class="a">A</p>
        </ng-template>
      `
    })
    class App {
      items = [1, 2, 3];
    }

    TestBed.configureTestingModule({
      declarations: [App, Comp],
    });
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    expect(fixture.debugElement.queryAll(By.css('.a')).length).toBe(3);
  });

  it('should do nothing for empty style bindings', () => {
    @Component({template: '<div [style.color]></div>'})
    class App {
    }

    TestBed.configureTestingModule({declarations: [App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    expect(fixture.nativeElement.innerHTML).toBe('<div></div>');
  });

  it('should do nothing for empty class bindings', () => {
    @Component({template: '<div [class.is-open]></div>'})
    class App {
    }

    TestBed.configureTestingModule({declarations: [App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    expect(fixture.nativeElement.innerHTML).toBe('<div></div>');
  });

  it('should be able to bind zero', () => {
    @Component({template: '<div #div [style.opacity]="opacity"></div>'})
    class App {
      @ViewChild('div') div!: ElementRef<HTMLElement>;
      opacity = 0;
    }

    TestBed.configureTestingModule({declarations: [App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    expect(fixture.componentInstance.div.nativeElement.style.opacity).toBe('0');
  });

  it('should be able to bind a SafeValue to backgroundImage', () => {
    @Component({template: '<div [style.backgroundImage]="image"></div>'})
    class Cmp {
      image!: SafeStyle;
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    const sanitizer: DomSanitizer = TestBed.inject(DomSanitizer);

    fixture.componentInstance.image = sanitizer.bypassSecurityTrustStyle('url("#test")');
    fixture.detectChanges();

    const div = fixture.nativeElement.querySelector('div') as HTMLDivElement;
    expect(div.style.backgroundImage).toBe('url("#test")');

    onlyInIvy('perf counters').expectPerfCounters({
      rendererSetStyle: 1,
      tNode: 3,
    });
  });

  it('should not write to the native element if a directive shadows the class input', () => {
    // This ex is a bit contrived. In real apps, you might have a shared class that is extended
    // both by components with host elements and by directives on template nodes. In that case, the
    // host styles for the template directives should just be ignored.
    @Directive({selector: 'ng-template[styleDir]', host: {'[style.display]': 'display'}})
    class StyleDir {
      display = 'block';
    }

    @Component({selector: 'app-comp', template: `<ng-template styleDir></ng-template>`})
    class MyApp {
    }

    TestBed.configureTestingModule({declarations: [MyApp, StyleDir]});
    TestBed.createComponent(MyApp).detectChanges();
  });

  it('should be able to bind a SafeValue to clip-path', () => {
    @Component({template: '<div [style.clip-path]="path"></div>'})
    class Cmp {
      path!: SafeStyle;
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    const sanitizer: DomSanitizer = TestBed.inject(DomSanitizer);

    fixture.componentInstance.path = sanitizer.bypassSecurityTrustStyle('url("#test")');
    fixture.detectChanges();

    const html = fixture.nativeElement.innerHTML;

    // Note that check the raw HTML, because (at the time of writing) the Node-based renderer
    // that we use to run tests doesn't support `clip-path` in `CSSStyleDeclaration`.
    expect(html).toMatch(/style=["|']clip-path:\s*url\(.*#test.*\)/);
  });

  it('should support interpolations inside a class binding', () => {
    @Component({
      template: `
        <div class="a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g{{seven}}h{{eight}}i{{nine}}j"></div>
        <div class="a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g{{seven}}h{{eight}}i"></div>
        <div class="a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g{{seven}}h"></div>
        <div class="a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g"></div>
        <div class="a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f"></div>
        <div class="a{{one}}b{{two}}c{{three}}d{{four}}e"></div>
        <div class="a{{one}}b{{two}}c{{three}}d"></div>
        <div class="a{{one}}b{{two}}c"></div>
        <div class="a{{one}}b"></div>
        <div class="{{one}}"></div>
      `
    })
    class Cmp {
      one = '1';
      two = '2';
      three = '3';
      four = '4';
      five = '5';
      six = '6';
      seven = '7';
      eight = '8';
      nine = '9';
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    const instance = fixture.componentInstance;
    fixture.detectChanges();

    const divs = fixture.nativeElement.querySelectorAll('div');

    expect(divs[0].getAttribute('class')).toBe('a1b2c3d4e5f6g7h8i9j');
    expect(divs[1].getAttribute('class')).toBe('a1b2c3d4e5f6g7h8i');
    expect(divs[2].getAttribute('class')).toBe('a1b2c3d4e5f6g7h');
    expect(divs[3].getAttribute('class')).toBe('a1b2c3d4e5f6g');
    expect(divs[4].getAttribute('class')).toBe('a1b2c3d4e5f');
    expect(divs[5].getAttribute('class')).toBe('a1b2c3d4e');
    expect(divs[6].getAttribute('class')).toBe('a1b2c3d');
    expect(divs[7].getAttribute('class')).toBe('a1b2c');
    expect(divs[8].getAttribute('class')).toBe('a1b');
    expect(divs[9].getAttribute('class')).toBe('1');

    instance.one = instance.two = instance.three = instance.four = instance.five = instance.six =
        instance.seven = instance.eight = instance.nine = '';
    fixture.detectChanges();

    expect(divs[0].getAttribute('class')).toBe('abcdefghij');
    expect(divs[1].getAttribute('class')).toBe('abcdefghi');
    expect(divs[2].getAttribute('class')).toBe('abcdefgh');
    expect(divs[3].getAttribute('class')).toBe('abcdefg');
    expect(divs[4].getAttribute('class')).toBe('abcdef');
    expect(divs[5].getAttribute('class')).toBe('abcde');
    expect(divs[6].getAttribute('class')).toBe('abcd');
    expect(divs[7].getAttribute('class')).toBe('abc');
    expect(divs[8].getAttribute('class')).toBe('ab');
    expect(divs[9].getAttribute('class')).toBeFalsy();
  });

  onlyInIvy('only Ivy supports style interpolation')
      .it('should support interpolations inside a style binding', () => {
        @Component({
          template: `
        <div style="content: &quot;a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g{{seven}}h{{eight}}i{{nine}}j&quot;"></div>
        <div style="content: &quot;a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g{{seven}}h{{eight}}i&quot;"></div>
        <div style="content: &quot;a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g{{seven}}h&quot;"></div>
        <div style="content: &quot;a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f{{six}}g&quot;"></div>
        <div style="content: &quot;a{{one}}b{{two}}c{{three}}d{{four}}e{{five}}f&quot;"></div>
        <div style="content: &quot;a{{one}}b{{two}}c{{three}}d{{four}}e&quot;"></div>
        <div style="content: &quot;a{{one}}b{{two}}c{{three}}d&quot;"></div>
        <div style="content: &quot;a{{one}}b{{two}}c&quot;"></div>
        <div style="content: &quot;a{{one}}b&quot;"></div>
        <div style="{{self}}"></div>
      `
        })
        class Cmp {
          self = 'content: "self"';
          one = '1';
          two = '2';
          three = '3';
          four = '4';
          five = '5';
          six = '6';
          seven = '7';
          eight = '8';
          nine = '9';
        }

        TestBed.configureTestingModule({declarations: [Cmp]});
        const fixture = TestBed.createComponent(Cmp);
        const instance = fixture.componentInstance;
        fixture.detectChanges();

        const divs = fixture.nativeElement.querySelectorAll('div');

        expect(divs[0].style.getPropertyValue('content')).toBe('"a1b2c3d4e5f6g7h8i9j"');
        expect(divs[1].style.getPropertyValue('content')).toBe('"a1b2c3d4e5f6g7h8i"');
        expect(divs[2].style.getPropertyValue('content')).toBe('"a1b2c3d4e5f6g7h"');
        expect(divs[3].style.getPropertyValue('content')).toBe('"a1b2c3d4e5f6g"');
        expect(divs[4].style.getPropertyValue('content')).toBe('"a1b2c3d4e5f"');
        expect(divs[5].style.getPropertyValue('content')).toBe('"a1b2c3d4e"');
        expect(divs[6].style.getPropertyValue('content')).toBe('"a1b2c3d"');
        expect(divs[7].style.getPropertyValue('content')).toBe('"a1b2c"');
        expect(divs[8].style.getPropertyValue('content')).toBe('"a1b"');
        expect(divs[9].style.getPropertyValue('content')).toBe('"self"');

        instance.one = instance.two = instance.three = instance.four = instance.five =
            instance.six = instance.seven = instance.eight = instance.nine = instance.self = '';
        fixture.detectChanges();

        expect(divs[0].style.getPropertyValue('content')).toBe('"abcdefghij"');
        expect(divs[1].style.getPropertyValue('content')).toBe('"abcdefghi"');
        expect(divs[2].style.getPropertyValue('content')).toBe('"abcdefgh"');
        expect(divs[3].style.getPropertyValue('content')).toBe('"abcdefg"');
        expect(divs[4].style.getPropertyValue('content')).toBe('"abcdef"');
        expect(divs[5].style.getPropertyValue('content')).toBe('"abcde"');
        expect(divs[6].style.getPropertyValue('content')).toBe('"abcd"');
        expect(divs[7].style.getPropertyValue('content')).toBe('"abc"');
        expect(divs[8].style.getPropertyValue('content')).toBe('"ab"');
        expect(divs[9].style.getPropertyValue('content')).toBeFalsy();
      });

  it('should support interpolations inside a class binding when other classes are present', () => {
    @Component({template: '<div class="zero i-{{one}} {{two}} three"></div>'})
    class Cmp {
      one = 'one';
      two = 'two';
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    fixture.detectChanges();
    const classList = fixture.nativeElement.querySelector('div').classList;

    expect(classList).toContain('zero');
    expect(classList).toContain('i-one');
    expect(classList).toContain('two');
    expect(classList).toContain('three');

    fixture.componentInstance.one = fixture.componentInstance.two = '';
    fixture.detectChanges();

    expect(classList).toContain('zero');
    expect(classList).toContain('i-');
    expect(classList).toContain('three');
    expect(classList).not.toContain('i-one');
    expect(classList).not.toContain('two');
  });

  it('should support interpolations inside a style property binding', () => {
    @Component({
      template: `
        <div style.font-family="f{{one}}{{two}}{{three}}{{four}}{{five}}{{six}}{{seven}}{{eight}}{{nine}}"></div>
        <div style.font-family="f{{one}}{{two}}{{three}}{{four}}{{five}}{{six}}{{seven}}{{eight}}"></div>
        <div style.font-family="f{{one}}{{two}}{{three}}{{four}}{{five}}{{six}}{{seven}}"></div>
        <div style.font-family="f{{one}}{{two}}{{three}}{{four}}{{five}}{{six}}"></div>
        <div style.font-family="f{{one}}{{two}}{{three}}{{four}}{{five}}"></div>
        <div style.font-family="f{{one}}{{two}}{{three}}{{four}}"></div>
        <div style.font-family="f{{one}}{{two}}{{three}}"></div>
        <div style.font-family="f{{one}}{{two}}"></div>
        <div style.font-family="f{{one}}"></div>
        <div style.width="{{singleBinding}}"></div>
      `
    })
    class Cmp {
      singleBinding: string|null = '1337px';
      one = 1;
      two = 2;
      three = 3;
      four = 4;
      five = 5;
      six = 6;
      seven = 7;
      eight = 8;
      nine = 9;
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    const instance = fixture.componentInstance;
    fixture.detectChanges();

    const divs: NodeListOf<HTMLElement> = fixture.nativeElement.querySelectorAll('div');

    expect(divs[0].style.fontFamily).toBe('f123456789');
    expect(divs[1].style.fontFamily).toBe('f12345678');
    expect(divs[2].style.fontFamily).toBe('f1234567');
    expect(divs[3].style.fontFamily).toBe('f123456');
    expect(divs[4].style.fontFamily).toBe('f12345');
    expect(divs[5].style.fontFamily).toBe('f1234');
    expect(divs[6].style.fontFamily).toBe('f123');
    expect(divs[7].style.fontFamily).toBe('f12');
    expect(divs[8].style.fontFamily).toBe('f1');
    expect(divs[9].style.width).toBe('1337px');

    instance.singleBinding = null;
    instance.one = instance.two = instance.three = instance.four = instance.five = instance.six =
        instance.seven = instance.eight = instance.nine = 1;
    fixture.detectChanges();

    expect(divs[0].style.fontFamily).toBe('f111111111');
    expect(divs[1].style.fontFamily).toBe('f11111111');
    expect(divs[2].style.fontFamily).toBe('f1111111');
    expect(divs[3].style.fontFamily).toBe('f111111');
    expect(divs[4].style.fontFamily).toBe('f11111');
    expect(divs[5].style.fontFamily).toBe('f1111');
    expect(divs[6].style.fontFamily).toBe('f111');
    expect(divs[7].style.fontFamily).toBe('f11');
    expect(divs[8].style.fontFamily).toBe('f1');
    expect(divs[9].style.width).toBeFalsy();
  });

  it('should support interpolations when a style property has a unit suffix', () => {
    @Component({template: '<div style.width.px="{{one}}{{three}}{{three}}7"></div>'})
    class Cmp {
      one = 1;
      three = 3;
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    fixture.detectChanges();
    const div = fixture.nativeElement.querySelector('div');

    expect(div.style.width).toBe('1337px');

    fixture.componentInstance.one = 2;
    fixture.componentInstance.three = 6;
    fixture.detectChanges();

    expect(div.style.width).toBe('2667px');
  });

  it('should not write to a `class` input binding in the event that there is no static class value',
     () => {
       let capturedClassBindingCount = 0;
       let capturedClassBindingValue: string|null|undefined = undefined;
       let capturedMyClassBindingCount = 0;
       let capturedMyClassBindingValue: string|null|undefined = undefined;

       @Component({template: '<div [class]="c" [my-class-dir]="x"></div>'})
       class Cmp {
         c: any = null;
         x = 'foo';
       }

       @Directive({selector: '[my-class-dir]'})
       class MyClassDir {
         @Input('class')
         set classVal(v: string) {
           capturedClassBindingCount++;
           capturedClassBindingValue = v;
         }

         @Input('my-class-dir')
         set myClassVal(v: string) {
           capturedMyClassBindingCount++;
           capturedMyClassBindingValue = v;
         }
       }

       TestBed.configureTestingModule({declarations: [Cmp, MyClassDir]});
       const fixture = TestBed.createComponent(Cmp);
       fixture.detectChanges();

       expect(capturedClassBindingCount).toEqual(1);
       expect(capturedClassBindingValue as any).toEqual(null);
       expect(capturedMyClassBindingCount).toEqual(1);
       expect(capturedMyClassBindingValue!).toEqual('foo');

       fixture.componentInstance.c = 'dynamic-value';
       fixture.detectChanges();

       expect(capturedClassBindingCount).toEqual(2);
       expect(capturedClassBindingValue!).toEqual('dynamic-value');
       expect(capturedMyClassBindingCount).toEqual(1);
       expect(capturedMyClassBindingValue!).toEqual('foo');

       fixture.componentInstance.c = null;
       fixture.detectChanges();

       expect(capturedClassBindingCount).toEqual(3);
       expect(capturedClassBindingValue as any).toEqual(null);
       expect(capturedMyClassBindingCount).toEqual(1);
       expect(capturedMyClassBindingValue!).toEqual('foo');

       fixture.componentInstance.c = '';
       fixture.detectChanges();

       expect(capturedClassBindingCount).toEqual(4);
       expect(capturedClassBindingValue as any).toEqual('');
       expect(capturedMyClassBindingCount).toEqual(1);
       expect(capturedMyClassBindingValue!).toEqual('foo');
     });

  it('should write to [class] binding during `update` mode if there is an instantiation-level value',
     () => {
       let capturedClassBindingCount = 0;
       let capturedClassBindingValue: string|null|undefined = undefined;

       @Component({template: '<div [class]="c" my-class-dir></div>'})
       class Cmp {
         c: any = 'bar';
       }

       @Directive({selector: '[my-class-dir]'})
       class MyClassDir {
         @Input('class')
         set classVal(v: string) {
           capturedClassBindingCount++;
           capturedClassBindingValue = v;
         }
       }

       TestBed.configureTestingModule({declarations: [Cmp, MyClassDir]});
       const fixture = TestBed.createComponent(Cmp);
       expect(capturedClassBindingCount).toEqual(0);
       fixture.detectChanges();

       expect(capturedClassBindingCount).toEqual(1);
       expect(capturedClassBindingValue as any).toEqual('bar');

       fixture.componentInstance.c = 'dynamic-bar';
       fixture.detectChanges();

       expect(capturedClassBindingCount).toEqual(2);
       expect(capturedClassBindingValue!).toEqual('dynamic-bar');
     });

  it('should write to a `class` input binding if there is a static class value', () => {
    let capturedClassBindingCount = 0;
    let capturedClassBindingValue: string|null = null;
    let capturedMyClassBindingCount = 0;
    let capturedMyClassBindingValue: string|null = null;

    @Component({template: '<div class="static-val" [my-class-dir]="x"></div>'})
    class Cmp {
      x = 'foo';
    }

    @Directive({selector: '[my-class-dir]'})
    class MyClassDir {
      @Input('class')
      set classVal(v: string) {
        capturedClassBindingCount++;
        capturedClassBindingValue = v;
      }

      @Input('my-class-dir')
      set myClassVal(v: string) {
        capturedMyClassBindingCount++;
        capturedMyClassBindingValue = v;
      }
    }

    TestBed.configureTestingModule({declarations: [Cmp, MyClassDir]});
    const fixture = TestBed.createComponent(Cmp);
    fixture.detectChanges();

    expect(capturedClassBindingValue!).toEqual('static-val');
    expect(capturedClassBindingCount).toEqual(1);
    expect(capturedMyClassBindingValue!).toEqual('foo');
    expect(capturedMyClassBindingCount).toEqual(1);
  });

  it('should write to a `className` input binding', () => {
    @Component({
      selector: 'comp',
      template: `{{className}}`,
    })
    class Comp {
      @Input() className: string = '';
    }
    @Component({
      template: `<comp [className]="'my-className'"></comp>`,
    })
    class App {
    }

    TestBed.configureTestingModule({declarations: [Comp, App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    expect(fixture.debugElement.nativeElement.firstChild.innerHTML).toBe('my-className');
  });

  onlyInIvy('only ivy combines static and dynamic class-related attr values')
      .it('should write combined class attribute and class binding to the class input', () => {
        @Component({
          selector: 'comp',
          template: `{{className}}`,
        })
        class Comp {
          @Input('class') className: string = '';
        }

        @Component({
          template: `<comp class="static" [class]="'my-className'"></comp>`,
        })
        class App {
        }

        TestBed.configureTestingModule({declarations: [Comp, App]});
        const fixture = TestBed.createComponent(App);
        fixture.detectChanges();
        expect(fixture.debugElement.nativeElement.firstChild.innerHTML).toBe('static my-className');
      });

  onlyInIvy('only ivy persists static class/style attrs with their binding counterparts')
      .it('should write to a `class` input binding if there is a static class value and there is a binding value',
          () => {
            let capturedClassBindingCount = 0;
            let capturedClassBindingValue: string|null = null;
            let capturedMyClassBindingCount = 0;
            let capturedMyClassBindingValue: string|null = null;

            @Component({template: '<div class="static-val" [class]="c" [my-class-dir]="x"></div>'})
            class Cmp {
              c: any = null;
              x: any = 'foo';
            }

            @Directive({selector: '[my-class-dir]'})
            class MyClassDir {
              @Input('class')
              set classVal(v: string) {
                capturedClassBindingCount++;
                capturedClassBindingValue = v;
              }

              @Input('my-class-dir')
              set myClassVal(v: string) {
                capturedMyClassBindingCount++;
                capturedMyClassBindingValue = v;
              }
            }

            TestBed.configureTestingModule({declarations: [Cmp, MyClassDir]});
            const fixture = TestBed.createComponent(Cmp);
            fixture.detectChanges();

            expect(capturedClassBindingCount)
                .toEqual(
                    2
                    // '2' is not ideal as '1' would be preferred.
                    // The reason for two writes is that one is for the  static
                    // `class="static-val"` and one for `[class]="c"`. This means that
                    // `class="static-val"` is written during the create block which is not ideal.
                    // To do this correctly we would have to delay the `class="static-val"` until
                    // the update block, but that would be expensive since it would require that we
                    // would check if we possibly have this situation on every `advance()`
                    // instruction. We don't think this is worth it, and we are just going to live
                    // with this.
                );
            expect(capturedClassBindingValue!).toEqual('static-val');
            expect(capturedMyClassBindingCount).toEqual(1);
            expect(capturedMyClassBindingValue!).toEqual('foo');

            capturedClassBindingCount = 0;
            fixture.componentInstance.c = 'dynamic-val';
            fixture.detectChanges();

            expect(capturedClassBindingCount).toEqual(1);
            expect(capturedClassBindingValue!).toEqual('static-val dynamic-val');
            expect(capturedMyClassBindingCount).toEqual(1);
            expect(capturedMyClassBindingValue!).toEqual('foo');
          });

  onlyInIvy('only ivy balances styling across directives and component host bindings')
      .it('should allow multiple directives to set dynamic and static classes independent of one another',
          () => {
            @Component({
              template: `
        <div dir-one dir-two></div>
      `
            })
            class Cmp {
            }

            @Directive({selector: '[dir-one]', host: {'[class.dir-one]': 'dirOneExp'}})
            class DirOne {
              dirOneExp = true;
            }

            @Directive({selector: '[dir-two]', host: {'class': 'dir-two'}})
            class DirTwo {
            }

            TestBed.configureTestingModule({declarations: [Cmp, DirOne, DirTwo]});
            const fixture = TestBed.createComponent(Cmp);
            fixture.detectChanges();

            const element = fixture.nativeElement.querySelector('div');
            expect(element.classList.contains('dir-one')).toBeTruthy();
            expect(element.classList.contains('dir-two')).toBeTruthy();
          });

  describe('NgClass', () => {
    // We had a bug where NgClass would not allocate sufficient slots for host bindings,
    // so it would overwrite information about other directives nearby. This test checks
    // that TestDir's injector is not overwritten by NgClass, so TestDir should still
    // be found by DI when ChildDir is instantiated.
    it('should not overwrite other directive info when using NgClass', () => {
      @Directive({selector: '[test-dir]'})
      class TestDir {
      }

      @Directive({selector: '[child-dir]'})
      class ChildDir {
        constructor(public parent: TestDir) {}
      }

      @Component({
        selector: 'app',
        template: `
          <div class="my-class" [ngClass]="classMap" test-dir>
            <div *ngIf="showing" child-dir>Hello</div>
          </div>
        `
      })
      class AppComponent {
        classMap = {'with-button': true};
        showing = false;
      }

      TestBed.configureTestingModule({declarations: [AppComponent, TestDir, ChildDir]});
      const fixture = TestBed.createComponent(AppComponent);
      fixture.detectChanges();
      const testDirDiv = fixture.debugElement.nativeElement.querySelector('div');
      expect(testDirDiv.classList).toContain('with-button');
      expect(fixture.debugElement.nativeElement.textContent).not.toContain('Hello');

      fixture.componentInstance.classMap = {'with-button': false};
      fixture.componentInstance.showing = true;
      fixture.detectChanges();

      const childDir = fixture.debugElement.query(By.directive(ChildDir)).injector.get(ChildDir);
      expect(childDir.parent).toBeAnInstanceOf(TestDir);
      expect(testDirDiv.classList).not.toContain('with-button');
      expect(fixture.debugElement.nativeElement.textContent).toContain('Hello');
    });
  });

  it('should be able to name inputs starting with `class` or `style`', () => {
    @Directive({selector: '[dir]'})
    class Dir {
      @Input('classesInSchool') classes = '';
      @Input('styleOfClothing') style = '';
    }

    @Component({
      template: '<span dir [classesInSchool]="classes" [styleOfClothing]="style"></span>',
    })
    class App {
      @ViewChild(Dir) dir!: Dir;

      classes = 'math';
      style = '80s';
    }

    TestBed.configureTestingModule({declarations: [App, Dir]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const directive = fixture.componentInstance.dir;

    expect(directive.classes).toBe('math');
    expect(directive.style).toBe('80s');
  });

  it('should be able to bind to `className`', () => {
    @Component({template: ''})
    class App {
      @HostBinding('className') klass = 'one two';
    }

    TestBed.configureTestingModule({declarations: [App]});
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const classList = fixture.nativeElement.classList;

    expect(classList.contains('one')).toBe(true);
    expect(classList.contains('two')).toBe(true);
  });

  onlyInIvy('ivy resolves styling across directives, components and templates in unison')
      .it('should apply single property styles/classes to the element and default to any static styling values',
          () => {
            @Component({
              template: `
        <div [style.width]="w"
             [style.height]="h"
             [style.opacity]="o"
             style="width:200px; height:200px;"
             [class.abc]="abc"
             [class.xyz]="xyz"></div>
      `
            })
            class Cmp {
              w: string|null|undefined = '100px';
              h: string|null|undefined = '100px';
              o: string|null|undefined = '0.5';
              abc = true;
              xyz = false;
            }

            TestBed.configureTestingModule({declarations: [Cmp]});
            const fixture = TestBed.createComponent(Cmp);
            fixture.detectChanges();

            const element = fixture.nativeElement.querySelector('div');
            expect(element.style.width).toEqual('100px');
            expect(element.style.height).toEqual('100px');
            expect(element.style.opacity).toEqual('0.5');
            expect(element.classList.contains('abc')).toBeTruthy();
            expect(element.classList.contains('xyz')).toBeFalsy();

            fixture.componentInstance.w = undefined;
            fixture.componentInstance.h = undefined;
            fixture.componentInstance.o = undefined;
            fixture.componentInstance.abc = false;
            fixture.componentInstance.xyz = true;
            fixture.detectChanges();

            expect(element.style.width).toEqual('200px');
            expect(element.style.height).toEqual('200px');
            expect(element.style.opacity).toBeFalsy();
            expect(element.classList.contains('abc')).toBeFalsy();
            expect(element.classList.contains('xyz')).toBeTruthy();

            fixture.componentInstance.w = null;
            fixture.componentInstance.h = null;
            fixture.componentInstance.o = null;
            fixture.detectChanges();
            expect(element.style.width).toBeFalsy();
            expect(element.style.height).toBeFalsy();
            expect(element.style.opacity).toBeFalsy();
          });

  onlyInIvy('ivy resolves styling across directives, components and templates in unison')
      .it('should apply single style/class across the template and directive host bindings', () => {
        @Directive({selector: '[dir-that-sets-width]'})
        class DirThatSetsWidthDirective {
          @Input('dir-that-sets-width') @HostBinding('style.width') public width: string = '';
        }

        @Directive({selector: '[another-dir-that-sets-width]', host: {'[style.width]': 'width'}})
        class AnotherDirThatSetsWidthDirective {
          @Input('another-dir-that-sets-width') public width: string = '';
        }

        @Component({
          template: `
        <div [style.width]="w0"
             [dir-that-sets-width]="w1"
             [another-dir-that-sets-width]="w2">
      `
        })
        class Cmp {
          w0: string|null|undefined = null;
          w1: string|null|undefined = null;
          w2: string|null|undefined = null;
        }

        TestBed.configureTestingModule(
            {declarations: [Cmp, DirThatSetsWidthDirective, AnotherDirThatSetsWidthDirective]});
        const fixture = TestBed.createComponent(Cmp);
        fixture.componentInstance.w0 = '100px';
        fixture.componentInstance.w1 = '200px';
        fixture.componentInstance.w2 = '300px';
        fixture.detectChanges();

        const element = fixture.nativeElement.querySelector('div');
        expect(element.style.width).toEqual('100px');

        fixture.componentInstance.w0 = undefined;
        fixture.detectChanges();

        expect(element.style.width).toEqual('300px');

        fixture.componentInstance.w2 = undefined;
        fixture.detectChanges();

        expect(element.style.width).toEqual('200px');

        fixture.componentInstance.w1 = undefined;
        fixture.detectChanges();

        expect(element.style.width).toBeFalsy();

        fixture.componentInstance.w2 = '400px';
        fixture.detectChanges();

        expect(element.style.width).toEqual('400px');

        fixture.componentInstance.w1 = '500px';
        fixture.componentInstance.w0 = '600px';
        fixture.detectChanges();

        expect(element.style.width).toEqual('600px');
      });

  onlyInIvy('ivy resolves styling across directives, components and templates in unison')
      .it('should only run stylingFlush once when there are no collisions between styling properties',
          () => {
            @Directive({selector: '[dir-with-styling]'})
            class DirWithStyling {
              @HostBinding('style.font-size') public fontSize = '100px';
            }

            @Component({selector: 'comp-with-styling'})
            class CompWithStyling {
              @HostBinding('style.width') public width = '900px';

              @HostBinding('style.height') public height = '900px';
            }

            @Component({
              template: `
        <comp-with-styling
          [style.opacity]="opacity"
          dir-with-styling>...</comp-with-styling>
      `
            })
            class Cmp {
              opacity: string|null = '0.5';
              @ViewChild(CompWithStyling, {static: true})
              compWithStyling: CompWithStyling|null = null;
              @ViewChild(DirWithStyling, {static: true}) dirWithStyling: DirWithStyling|null = null;
            }

            TestBed.configureTestingModule({declarations: [Cmp, DirWithStyling, CompWithStyling]});
            const fixture = TestBed.createComponent(Cmp);
            fixture.detectChanges();

            const component = fixture.componentInstance;
            const element = fixture.nativeElement.querySelector('comp-with-styling');

            expect(element.style.opacity).toEqual('0.5');
            expect(element.style.width).toEqual('900px');
            expect(element.style.height).toEqual('900px');
            expect(element.style.fontSize).toEqual('100px');

            // once for the template flush and again for the host bindings
            expect(ngDevMode!.rendererSetStyle).toEqual(4);
            ngDevModeResetPerfCounters();

            component.opacity = '0.6';
            component.compWithStyling!.height = '100px';
            component.compWithStyling!.width = '100px';
            component.dirWithStyling!.fontSize = '50px';
            fixture.detectChanges();

            expect(element.style.opacity).toEqual('0.6');
            expect(element.style.width).toEqual('100px');
            expect(element.style.height).toEqual('100px');
            expect(element.style.fontSize).toEqual('50px');

            // once for the template flush and again for the host bindings
            expect(ngDevMode!.rendererSetStyle).toEqual(4);
          });

  onlyInIvy('ivy resolves styling across directives, components and templates in unison')
      .it('should combine all styling across the template, directive and component host bindings',
          () => {
            @Directive({selector: '[dir-with-styling]'})
            class DirWithStyling {
              @HostBinding('style.color') public color = 'red';

              @HostBinding('style.font-size') public fontSize = '100px';

              @HostBinding('class.dir') public dirClass = true;
            }

            @Component({selector: 'comp-with-styling'})
            class CompWithStyling {
              @HostBinding('style.width') public width = '900px';

              @HostBinding('style.height') public height = '900px';

              @HostBinding('class.comp') public compClass = true;
            }

            @Component({
              template: `
        <comp-with-styling
          [style.opacity]="opacity"
          [style.width]="width"
          [class.tpl]="tplClass"
          dir-with-styling>...</comp-with-styling>
      `
            })
            class Cmp {
              opacity: string|null|undefined = '0.5';
              width: string|null|undefined = 'auto';
              tplClass = true;
            }

            TestBed.configureTestingModule({declarations: [Cmp, DirWithStyling, CompWithStyling]});
            const fixture = TestBed.createComponent(Cmp);
            fixture.detectChanges();

            const element = fixture.nativeElement.querySelector('comp-with-styling');

            expectStyle(element).toEqual({
              'color': 'red',
              'font-size': '100px',
              'height': '900px',
              'opacity': '0.5',
              'width': 'auto',
            });
            expectClass(element).toEqual({
              'dir': true,
              'comp': true,
              'tpl': true,
            });

            fixture.componentInstance.width = undefined;
            fixture.componentInstance.opacity = undefined;
            fixture.componentInstance.tplClass = false;
            fixture.detectChanges();

            expectStyle(element).toEqual(
                {'color': 'red', 'width': '900px', 'height': '900px', 'font-size': '100px'});
            expectClass(element).toEqual({
              'dir': true,
              'comp': true,
            });

            fixture.componentInstance.width = null;
            fixture.componentInstance.opacity = null;
            fixture.detectChanges();

            expectStyle(element).toEqual({'color': 'red', 'height': '900px', 'font-size': '100px'});
          });

  onlyInIvy('ivy resolves styling across directives, components and templates in unison')
      .it('should properly apply styling across sub and super class directive host bindings',
          () => {
            @Directive({selector: '[super-class-dir]'})
            class SuperClassDirective {
              @HostBinding('style.width') public w1 = '100px';
            }

            @Component({selector: '[sub-class-dir]'})
            class SubClassDirective extends SuperClassDirective {
              @HostBinding('style.width') public w2 = '200px';
            }

            @Component({
              template: `
          <div sub-class-dir [style.width]="w3"></div>
      `
            })
            class Cmp {
              w3: string|null|undefined = '300px';
            }

            TestBed.configureTestingModule(
                {declarations: [Cmp, SuperClassDirective, SubClassDirective]});
            const fixture = TestBed.createComponent(Cmp);
            fixture.detectChanges();

            const element = fixture.nativeElement.querySelector('div');

            expectStyle(element).toEqual({
              'width': '300px',
            });

            fixture.componentInstance.w3 = null;
            fixture.detectChanges();

            expectStyle(element).toEqual({});

            fixture.componentInstance.w3 = undefined;
            fixture.detectChanges();

            expectStyle(element).toEqual({
              'width': '200px',
            });
          });


  onlyInIvy('only ivy has style debugging support')
      .it('should apply map-based style and class entries', () => {
        @Component({template: '<div [style]="s" [class]="c"></div>'})
        class Cmp {
          public c: {[key: string]: any}|null = null;
          updateClasses(classes: string) {
            const c = this.c || (this.c = {});
            Object.keys(this.c).forEach(className => {
              c[className] = false;
            });
            classes.split(/\s+/).forEach(className => {
              c[className] = true;
            });
          }

          public s: {[key: string]: any}|null = null;
          updateStyles(prop: string, value: string|number|null) {
            const s = this.s || (this.s = {});
            Object.assign(s, {[prop]: value});
          }

          reset() {
            this.s = null;
            this.c = null;
          }
        }

        TestBed.configureTestingModule({declarations: [Cmp]});
        const fixture = TestBed.createComponent(Cmp);
        const comp = fixture.componentInstance;
        comp.updateStyles('width', '100px');
        comp.updateStyles('height', '200px');
        comp.updateClasses('abc');
        fixture.detectChanges();

        const element = fixture.nativeElement.querySelector('div');
        expectStyle(element).toEqual({width: '100px', height: '200px'});
        expectClass(element).toEqual({abc: true});

        comp.reset();
        comp.updateStyles('width', '500px');
        comp.updateStyles('height', null);
        comp.updateClasses('def');
        fixture.detectChanges();

        expectStyle(element).toEqual({width: '500px'});
        expectClass(element).toEqual({def: true});
      });

  onlyInIvy('ivy resolves styling across directives, components and templates in unison')
      .it('should resolve styling collisions across templates, directives and components for prop and map-based entries',
          () => {
            @Directive({selector: '[dir-that-sets-styling]'})
            class DirThatSetsStyling {
              @HostBinding('style') public map: any = {color: 'red', width: '777px'};
            }

            @Component({
              template: `
        <div [style.width]="width"
             [style]="map"
             style="width:200px; font-size:99px"
             dir-that-sets-styling
             #dir
             [class.xyz]="xyz"></div>
      `
            })
            class Cmp {
              map: any = {width: '111px', opacity: '0.5'};
              width: string|null|undefined = '555px';

              @ViewChild('dir', {read: DirThatSetsStyling, static: true}) dir!: DirThatSetsStyling;
            }

            TestBed.configureTestingModule({declarations: [Cmp, DirThatSetsStyling]});
            const fixture = TestBed.createComponent(Cmp);
            const comp = fixture.componentInstance;
            fixture.detectChanges();

            const element = fixture.nativeElement.querySelector('div');
            expectStyle(element).toEqual({
              'width': '555px',
              'color': 'red',
              'font-size': '99px',
              'opacity': '0.5',
            });

            comp.width = undefined;
            fixture.detectChanges();

            expectStyle(element).toEqual({
              'width': '111px',
              'color': 'red',
              'font-size': '99px',
              'opacity': '0.5',
            });

            comp.map = null;
            fixture.detectChanges();

            expectStyle(element).toEqual({
              'width': '200px',
              'color': 'red',
              'font-size': '99px',
            });

            comp.dir.map = null;
            fixture.detectChanges();

            expectStyle(element).toEqual({
              'width': '200px',
              'font-size': '99px',
            });
          });

  onlyInIvy('ivy resolves styling across directives, components and templates in unison')
      .it('should only apply each styling property once per CD across templates, components, directives',
          () => {
            @Directive(
                {selector: '[dir-that-sets-styling]', host: {'style': 'width:0px; height:0px'}})
            class DirThatSetsStyling {
              @HostBinding('style') public map: any = {width: '999px', height: '999px'};
            }

            @Component({
              template: `
                <div #dir
                  [style.width]="width"
                  [style.height]="height"
                  [style]="map"
                  dir-that-sets-styling></div>
              `
            })
            class Cmp {
              width: string|null|undefined = '111px';
              height: string|null|undefined = '111px';

              map: any = {width: '555px', height: '555px'};

              @ViewChild('dir', {read: DirThatSetsStyling, static: true}) dir!: DirThatSetsStyling;
            }

            TestBed.configureTestingModule({declarations: [Cmp, DirThatSetsStyling]});
            const fixture = TestBed.createComponent(Cmp);
            const comp = fixture.componentInstance;

            ngDevModeResetPerfCounters();
            fixture.detectChanges();
            const element = fixture.nativeElement.querySelector('div');

            assertStyleCounters(4, 0);
            assertStyle(element, 'width', '111px');
            assertStyle(element, 'height', '111px');

            comp.width = '222px';
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            assertStyleCounters(1, 0);
            assertStyle(element, 'width', '222px');
            assertStyle(element, 'height', '111px');

            comp.height = '222px';
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            assertStyleCounters(1, 0);
            assertStyle(element, 'width', '222px');
            assertStyle(element, 'height', '222px');

            comp.width = undefined;
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            assertStyleCounters(1, 0);
            assertStyle(element, 'width', '555px');
            assertStyle(element, 'height', '222px');

            comp.width = '123px';
            comp.height = '123px';
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            assertStyle(element, 'width', '123px');
            assertStyle(element, 'height', '123px');

            comp.map = {};
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            // No change, hence no write
            assertStyleCounters(0, 0);
            assertStyle(element, 'width', '123px');
            assertStyle(element, 'height', '123px');

            comp.width = undefined;
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            assertStyleCounters(1, 0);
            assertStyle(element, 'width', '999px');
            assertStyle(element, 'height', '123px');

            comp.dir.map = null;
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            // the width is only applied once
            assertStyleCounters(1, 0);
            assertStyle(element, 'width', '0px');
            assertStyle(element, 'height', '123px');

            comp.dir.map = {width: '1000px', height: '1100px', color: 'red'};
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            assertStyleCounters(2, 0);
            assertStyle(element, 'width', '1000px');
            assertStyle(element, 'height', '123px');
            assertStyle(element, 'color', 'red');

            comp.height = undefined;
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            // height gets applied twice and all other
            // values get applied
            assertStyleCounters(1, 0);
            assertStyle(element, 'width', '1000px');
            assertStyle(element, 'height', '1100px');
            assertStyle(element, 'color', 'red');

            comp.map = {color: 'blue', width: '2000px', opacity: '0.5'};
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            assertStyleCounters(3, 0);
            assertStyle(element, 'width', '2000px');
            assertStyle(element, 'height', '1100px');
            assertStyle(element, 'color', 'blue');
            assertStyle(element, 'opacity', '0.5');

            comp.map = {color: 'blue', width: '2000px'};
            ngDevModeResetPerfCounters();
            fixture.detectChanges();

            // all four are applied because the map was altered
            assertStyleCounters(0, 1);
            assertStyle(element, 'width', '2000px');
            assertStyle(element, 'height', '1100px');
            assertStyle(element, 'color', 'blue');
            assertStyle(element, 'opacity', '');
          });

  onlyInIvy('only ivy has [style.prop] support')
      .it('should not sanitize style values before writing them', () => {
        @Component({
          template: `
                        <div [style.width]="widthExp"
                             [style.background-image]="bgImageExp"></div>
                      `
        })
        class Cmp {
          widthExp = '';
          bgImageExp = '';
          styleMapExp: any = {};
        }

        TestBed.configureTestingModule({declarations: [Cmp]});
        const fixture = TestBed.createComponent(Cmp);
        const comp = fixture.componentInstance;
        fixture.detectChanges();

        const div = fixture.nativeElement.querySelector('div');

        comp.bgImageExp = 'url("javascript:img")';
        fixture.detectChanges();
        expect(getSortedStyle(div)).toContain('javascript:img');

        // Prove that bindings work.
        comp.widthExp = '789px';
        comp.bgImageExp = bypassSanitizationTrustStyle(comp.bgImageExp) as string;
        fixture.detectChanges();

        expect(div.style.getPropertyValue('background-image')).toEqual('url("javascript:img")');
        expect(div.style.getPropertyValue('width')).toEqual('789px');
      });

  onlyInIvy('only ivy has [style] support')
      .it('should not sanitize style values before writing them', () => {
        @Component({
          template: `
                    <div [style.width]="widthExp"
                         [style]="styleMapExp"></div>
                  `
        })
        class Cmp {
          widthExp = '';
          styleMapExp: {[key: string]: any} = {};
        }

        TestBed.configureTestingModule({declarations: [Cmp]});
        const fixture = TestBed.createComponent(Cmp);
        const comp = fixture.componentInstance;
        fixture.detectChanges();

        const div = fixture.nativeElement.querySelector('div');

        comp.styleMapExp['background-image'] = 'url("javascript:img")';
        fixture.detectChanges();
        expect(getSortedStyle(div)).not.toContain('javascript');

        // Prove that bindings work.
        comp.widthExp = '789px';
        comp.styleMapExp = {
          'background-image': bypassSanitizationTrustStyle(comp.styleMapExp['background-image'])
        };
        fixture.detectChanges();

        expect(div.style.getPropertyValue('background-image')).toEqual('url("javascript:img")');
        expect(div.style.getPropertyValue('width')).toEqual('789px');
      });

  it('should apply a unit to a style before writing it', () => {
    @Component({
      template: `
            <div [style.width.px]="widthExp"
                 [style.height.em]="heightExp"></div>
          `
    })
    class Cmp {
      widthExp: string|number|null = '';
      heightExp: string|number|null = '';
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    const div = fixture.nativeElement.querySelector('div');

    comp.widthExp = '200';
    comp.heightExp = 10;
    fixture.detectChanges();

    expect(getSortedStyle(div)).toEqual('height: 10em; width: 200px;');

    comp.widthExp = 0;
    comp.heightExp = null;
    fixture.detectChanges();

    expect(getSortedStyle(div)).toEqual('width: 0px;');
  });

  it('should be able to bind a SafeValue to clip-path', () => {
    @Component({template: '<div [style.clip-path]="path"></div>'})
    class Cmp {
      path!: SafeStyle;
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    const sanitizer: DomSanitizer = TestBed.inject(DomSanitizer);

    fixture.componentInstance.path = sanitizer.bypassSecurityTrustStyle('url("#test")');
    fixture.detectChanges();

    const html = fixture.nativeElement.innerHTML;

    // Note that check the raw HTML, because (at the time of writing) the Node-based renderer
    // that we use to run tests doesn't support `clip-path` in `CSSStyleDeclaration`.
    expect(html).toMatch(/style=["|']clip-path:\s*url\(.*#test.*\)/);
  });

  it('should handle values wrapped into SafeValue', () => {
    @Component({
      template: `
        <!-- Verify sanitizable style prop values wrapped in SafeValue -->
        <div [style.background]="getBackgroundSafe()"></div>

        <!-- Verify regular style prop values wrapped in SafeValue -->
        <p [style.width]="getWidthSafe()" [style.height]="getHeightSafe()"></p>

        <!-- Verify regular style prop values not wrapped in SafeValue -->
        <span [style.color]="getColorUnsafe()"></span>
      `,
    })
    class MyComp {
      constructor(private sanitizer: DomSanitizer) {}
      public width: string = 'calc(20%)';
      public height: string = '10px';
      public background: string = '1.png';
      public color: string = 'red';

      private getSafeStyle(value: string) {
        return this.sanitizer.bypassSecurityTrustStyle(value);
      }

      getBackgroundSafe() {
        return this.getSafeStyle(`url("/${this.background}")`);
      }
      getWidthSafe() {
        return this.getSafeStyle(this.width);
      }
      getHeightSafe() {
        return this.getSafeStyle(this.height);
      }
      getColorUnsafe() {
        return this.color;
      }
    }

    TestBed.configureTestingModule({
      imports: [CommonModule],
      declarations: [MyComp],
    });
    const fixture = TestBed.createComponent(MyComp);
    fixture.detectChanges();

    const comp = fixture.componentInstance;
    const div = fixture.nativeElement.querySelector('div');
    const p = fixture.nativeElement.querySelector('p');
    const span = fixture.nativeElement.querySelector('span');

    expect(div.style.background).toContain('url("/1.png")');
    expect(p.style.width).toBe('calc(20%)');
    expect(p.style.height).toBe('10px');
    expect(span.style.color).toBe('red');

    comp.background = '2.png';
    comp.width = '5px';
    comp.height = '100%';
    comp.color = 'green';

    fixture.detectChanges();

    expect(div.style.background).toContain('url("/2.png")');
    expect(p.style.width).toBe('5px');
    expect(p.style.height).toBe('100%');
    expect(span.style.color).toBe('green');
  });

  onlyInIvy('only ivy has style/class bindings debugging support')
      .it('should evaluate follow-up [style] maps even if a former map is null', () => {
        @Directive({selector: '[dir-with-styling]'})
        class DirWithStyleMap {
          @HostBinding('style') public styleMap: any = {color: 'red'};
        }

        @Directive({selector: '[dir-with-styling-part2]'})
        class DirWithStyleMapPart2 {
          @HostBinding('style') public styleMap: any = {width: '200px'};
        }

        @Component({
          template: `
        <div #div
              [style]="map"
              dir-with-styling
              dir-with-styling-part2></div>
      `
        })
        class Cmp {
          map: any = null;

          @ViewChild('div', {read: DirWithStyleMap, static: true}) dir1!: DirWithStyleMap;

          @ViewChild('div', {read: DirWithStyleMapPart2, static: true}) dir2!: DirWithStyleMapPart2;
        }

        TestBed.configureTestingModule(
            {declarations: [Cmp, DirWithStyleMap, DirWithStyleMapPart2]});
        const fixture = TestBed.createComponent(Cmp);
        fixture.detectChanges();

        const element = fixture.nativeElement.querySelector('div');
        expectStyle(element).toEqual({
          color: 'red',
          width: '200px',
        });
      });

  onlyInIvy('only ivy has style/class bindings debugging support')
      .it('should evaluate initial style/class values on a list of elements that changes', () => {
        @Component({
          template: `
            <div *ngFor="let item of items"
                  class="initial-class item-{{ item }}">
              {{ item }}
            </div>
          `
        })
        class Cmp {
          items = [1, 2, 3];
        }

        TestBed.configureTestingModule({declarations: [Cmp]});
        const fixture = TestBed.createComponent(Cmp);
        const comp = fixture.componentInstance;
        fixture.detectChanges();

        function getItemElements(): HTMLElement[] {
          return [].slice.call(fixture.nativeElement.querySelectorAll('div'));
        }

        function getItemClasses(): string[] {
          return getItemElements().map(e => e.className).sort().join(' ').split(' ');
        }

        expect(getItemElements().length).toEqual(3);
        expect(getItemClasses()).toEqual([
          'initial-class',
          'item-1',
          'initial-class',
          'item-2',
          'initial-class',
          'item-3',
        ]);

        comp.items = [2, 4, 6, 8];
        fixture.detectChanges();

        expect(getItemElements().length).toEqual(4);
        expect(getItemClasses()).toEqual([
          'initial-class',
          'item-2',
          'initial-class',
          'item-4',
          'initial-class',
          'item-6',
          'initial-class',
          'item-8',
        ]);
      });

  onlyInIvy('only ivy has style/class bindings debugging support')
      .it('should create and update multiple class bindings across multiple elements in a template',
          () => {
            @Component({
              template: `
            <header class="header">header</header>
            <div *ngFor="let item of items" class="item item-{{ item }}">
              {{ item }}
            </div>
            <footer class="footer">footer</footer>
          `
            })
            class Cmp {
              items = [1, 2, 3];
            }

            TestBed.configureTestingModule({declarations: [Cmp]});
            const fixture = TestBed.createComponent(Cmp);
            const comp = fixture.componentInstance;
            fixture.detectChanges();

            function getItemElements(): HTMLElement[] {
              return [].slice.call(fixture.nativeElement.querySelectorAll('div'));
            }

            function getItemClasses(): string[] {
              return getItemElements().map(e => e.className).sort().join(' ').split(' ');
            }

            const header = fixture.nativeElement.querySelector('header');
            expect(header.classList.contains('header'));

            const footer = fixture.nativeElement.querySelector('footer');
            expect(footer.classList.contains('footer'));

            expect(getItemElements().length).toEqual(3);
            expect(getItemClasses()).toEqual([
              'item',
              'item-1',
              'item',
              'item-2',
              'item',
              'item-3',
            ]);
          });

  onlyInIvy('only ivy has style/class bindings debugging support')
      .it('should understand multiple directives which contain initial classes', () => {
        @Directive({selector: 'dir-one'})
        class DirOne {
          @HostBinding('class') public className = 'dir-one';
        }

        @Directive({selector: 'dir-two'})
        class DirTwo {
          @HostBinding('class') public className = 'dir-two';
        }

        @Component({
          template: `
            <dir-one></dir-one>
            <div class="initial"></div>
            <dir-two></dir-two>
          `
        })
        class Cmp {
        }

        TestBed.configureTestingModule({declarations: [Cmp, DirOne, DirTwo]});
        const fixture = TestBed.createComponent(Cmp);
        fixture.detectChanges();

        const dirOne = fixture.nativeElement.querySelector('dir-one');
        const div = fixture.nativeElement.querySelector('div');
        const dirTwo = fixture.nativeElement.querySelector('dir-two');

        expect(dirOne.classList.contains('dir-one')).toBeTruthy();
        expect(dirTwo.classList.contains('dir-two')).toBeTruthy();
        expect(div.classList.contains('initial')).toBeTruthy();
      });

  onlyInIvy('only ivy has style/class bindings debugging support')
      .it('should evaluate styling across the template directives when there are multiple elements/sources of styling',
          () => {
            @Directive({selector: '[one]'})
            class DirOne {
              @HostBinding('class') public className = 'dir-one';
            }

            @Directive({selector: '[two]'})
            class DirTwo {
              @HostBinding('class') public className = 'dir-two';
            }

            @Component({
              template: `
                <div class="a" [style.width.px]="w" one></div>
                <div class="b" [style.height.px]="h" one two></div>
                <div class="c" [style.color]="c" two></div>
              `
            })
            class Cmp {
              w = 100;
              h = 200;
              c = 'red';
            }

            TestBed.configureTestingModule({declarations: [Cmp, DirOne, DirTwo]});
            const fixture = TestBed.createComponent(Cmp);
            fixture.detectChanges();

            const divA = fixture.nativeElement.querySelector('.a');
            const divB = fixture.nativeElement.querySelector('.b');
            const divC = fixture.nativeElement.querySelector('.c');

            expect(divA.style.width).toEqual('100px');
            expect(divB.style.height).toEqual('200px');
            expect(divC.style.color).toEqual('red');
          });

  onlyInIvy('only ivy has style/class bindings debugging support')
      .it('should evaluate styling across the template and directives within embedded views',
          () => {
            @Directive({selector: '[some-dir-with-styling]'})
            class SomeDirWithStyling {
              @HostBinding('style')
              public styles = {
                width: '200px',
                height: '500px',
              };
            }

            @Component({
              template: `
                <div
                  class="item"
                  *ngFor="let item of items; let i = index"
                  [style.color]="c"
                  [style.height.px]="h * i"
                  some-dir-with-styling>
                  {{ item }}
                </div>
                <section [style.width.px]="w"></section>
                <p [style.height.px]="h"></p>
              `
            })
            class Cmp {
              items: any[] = [];
              c = 'red';
              w = 100;
              h = 100;
            }

            TestBed.configureTestingModule({declarations: [Cmp, SomeDirWithStyling]});
            const fixture = TestBed.createComponent(Cmp);
            const comp = fixture.componentInstance;
            comp.items = [1, 2, 3, 4];
            fixture.detectChanges();

            const items = fixture.nativeElement.querySelectorAll('.item');
            expect(items.length).toEqual(4);
            const [a, b, c, d] = items;
            expect(a.style.height).toEqual('0px');
            expect(b.style.height).toEqual('100px');
            expect(c.style.height).toEqual('200px');
            expect(d.style.height).toEqual('300px');

            const section = fixture.nativeElement.querySelector('section');
            const p = fixture.nativeElement.querySelector('p');

            expect(section.style['width']).toEqual('100px');
            expect(p.style['height']).toEqual('100px');
          });

  onlyInIvy('only ivy has style/class bindings debugging support')
      .it('should flush bindings even if any styling hasn\'t changed in a previous directive',
          () => {
            @Directive({selector: '[one]'})
            class DirOne {
              @HostBinding('style.width') w = '100px';
              @HostBinding('style.opacity') o = '0.5';
            }

            @Directive({selector: '[two]'})
            class DirTwo {
              @HostBinding('style.height') h = '200px';
              @HostBinding('style.color') c = 'red';
            }

            @Component({template: '<div #target one two></div>'})
            class Cmp {
              @ViewChild('target', {read: DirOne, static: true}) one!: DirOne;
              @ViewChild('target', {read: DirTwo, static: true}) two!: DirTwo;
            }

            TestBed.configureTestingModule({declarations: [Cmp, DirOne, DirTwo]});
            const fixture = TestBed.createComponent(Cmp);
            const comp = fixture.componentInstance;
            fixture.detectChanges();

            const div = fixture.nativeElement.querySelector('div');
            expect(div.style.opacity).toEqual('0.5');
            expect(div.style.color).toEqual('red');
            expect(div.style.width).toEqual('100px');
            expect(div.style.height).toEqual('200px');

            comp.two.h = '300px';
            fixture.detectChanges();
            expect(div.style.opacity).toEqual('0.5');
            expect(div.style.color).toEqual('red');
            expect(div.style.width).toEqual('100px');
            expect(div.style.height).toEqual('300px');
          });

  it('should work with NO_CHANGE values if they are applied to bindings ', () => {
    @Component({
      template: `
            <div
              [style.width]="w"
              style.height="{{ h }}"
              [style.opacity]="o"></div>
          `
    })
    class Cmp {
      w: any = null;
      h: any = null;
      o: any = null;
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    const comp = fixture.componentInstance;

    comp.w = '100px';
    comp.h = '200px';
    comp.o = '0.5';
    fixture.detectChanges();

    const div = fixture.nativeElement.querySelector('div');
    expect(div.style.width).toEqual('100px');
    expect(div.style.height).toEqual('200px');
    expect(div.style.opacity).toEqual('0.5');

    comp.w = '500px';
    comp.o = '1';
    fixture.detectChanges();

    expect(div.style.width).toEqual('500px');
    expect(div.style.height).toEqual('200px');
    expect(div.style.opacity).toEqual('1');
  });

  it('should allow [ngStyle] and [ngClass] to be used together', () => {
    @Component({
      template: `
            <div [ngClass]="c" [ngStyle]="s"></div>
          `
    })
    class Cmp {
      c: any = 'foo bar';
      s: any = {width: '200px'};
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    fixture.detectChanges();

    const div = fixture.nativeElement.querySelector('div');
    expect(div.style.width).toEqual('200px');
    expect(div.classList.contains('foo')).toBeTruthy();
    expect(div.classList.contains('bar')).toBeTruthy();
  });

  it('should allow to reset style property value defined using ngStyle', () => {
    @Component({
      template: `
        <div [ngStyle]="s"></div>
      `
    })
    class Cmp {
      s: any = {opacity: '1'};

      clearStyle(): void {
        this.s = null;
      }
    }

    TestBed.configureTestingModule({declarations: [Cmp]});
    const fixture = TestBed.createComponent(Cmp);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    const div = fixture.nativeElement.querySelector('div');
    expect(div.style.opacity).toEqual('1');

    comp.clearStyle();
    fixture.detectChanges();

    expect(div.style.opacity).toEqual('');
  });

  it('should allow detectChanges to be run in a property change that causes additional styling to be rendered',
     () => {
       @Component({
         selector: 'child',
         template: `
          <div [class.ready-child]="readyTpl"></div>
        `,
       })
       class ChildCmp {
         readyTpl = false;

         @HostBinding('class.ready-host') readyHost = false;
       }

       @Component({
         selector: 'parent',
         template: `
        <div>
          <div #template></div>
          <p>{{prop}}</p>
        </div>
      `,
         host: {
           '[style.color]': 'color',
         },
       })
       class ParentCmp {
         private _prop = '';

         @ViewChild('template', {read: ViewContainerRef}) vcr: ViewContainerRef = null!;

         private child: ComponentRef<ChildCmp> = null!;

         @Input()
         set prop(value: string) {
           this._prop = value;
           if (this.child && value === 'go') {
             this.child.instance.readyHost = true;
             this.child.instance.readyTpl = true;
             this.child.changeDetectorRef.detectChanges();
           }
         }

         get prop() {
           return this._prop;
         }

         ngAfterViewInit() {
           const factory = this.componentFactoryResolver.resolveComponentFactory(ChildCmp);
           this.child = this.vcr.createComponent(factory);
         }

         constructor(private componentFactoryResolver: ComponentFactoryResolver) {}
       }

       @Component({
         template: `<parent [prop]="prop"></parent>`,
       })
       class App {
         prop = 'a';
       }

       @NgModule({
         entryComponents: [ChildCmp],
         declarations: [ChildCmp],
       })
       class ChildCmpModule {
       }

       TestBed.configureTestingModule({declarations: [App, ParentCmp], imports: [ChildCmpModule]});
       const fixture = TestBed.createComponent(App);
       fixture.detectChanges(false);

       let readyHost = fixture.nativeElement.querySelector('.ready-host');
       let readyChild = fixture.nativeElement.querySelector('.ready-child');

       expect(readyHost).toBeFalsy();
       expect(readyChild).toBeFalsy();

       fixture.componentInstance.prop = 'go';
       fixture.detectChanges(false);

       readyHost = fixture.nativeElement.querySelector('.ready-host');
       readyChild = fixture.nativeElement.querySelector('.ready-child');
       expect(readyHost).toBeTruthy();
       expect(readyChild).toBeTruthy();
     });

  it('should allow detectChanges to be run in a hook that causes additional styling to be rendered',
     () => {
       @Component({
         selector: 'child',
         template: `
          <div [class.ready-child]="readyTpl"></div>
        `,
       })
       class ChildCmp {
         readyTpl = false;

         @HostBinding('class.ready-host') readyHost = false;
       }

       @Component({
         selector: 'parent',
         template: `
          <div>
            <div #template></div>
            <p>{{prop}}</p>
          </div>
        `,
       })
       class ParentCmp {
         updateChild = false;

         @ViewChild('template', {read: ViewContainerRef}) vcr: ViewContainerRef = null!;

         private child: ComponentRef<ChildCmp> = null!;

         ngDoCheck() {
           if (this.updateChild) {
             this.child.instance.readyHost = true;
             this.child.instance.readyTpl = true;
             this.child.changeDetectorRef.detectChanges();
           }
         }

         ngAfterViewInit() {
           const factory = this.componentFactoryResolver.resolveComponentFactory(ChildCmp);
           this.child = this.vcr.createComponent(factory);
         }

         constructor(private componentFactoryResolver: ComponentFactoryResolver) {}
       }

       @Component({
         template: `<parent #parent></parent>`,
       })
       class App {
         @ViewChild('parent', {static: true}) public parent: ParentCmp|null = null;
       }

       @NgModule({
         entryComponents: [ChildCmp],
         declarations: [ChildCmp],
       })
       class ChildCmpModule {
       }

       TestBed.configureTestingModule({declarations: [App, ParentCmp], imports: [ChildCmpModule]});
       const fixture = TestBed.createComponent(App);
       fixture.detectChanges(false);

       let readyHost = fixture.nativeElement.querySelector('.ready-host');
       let readyChild = fixture.nativeElement.querySelector('.ready-child');
       expect(readyHost).toBeFalsy();
       expect(readyChild).toBeFalsy();

       const parent = fixture.componentInstance.parent!;
       parent.updateChild = true;
       fixture.detectChanges(false);

       readyHost = fixture.nativeElement.querySelector('.ready-host');
       readyChild = fixture.nativeElement.querySelector('.ready-child');
       expect(readyHost).toBeTruthy();
       expect(readyChild).toBeTruthy();
     });

  onlyInIvy('only ivy allows for multiple styles/classes to be balanced across directives')
      .it('should allow various duplicate properties to be defined in various styling maps within the template and directive styling bindings',
          () => {
            @Component({
              template: `
           <div [style.width]="w"
                [style.height]="h"
                [style]="s1"
                [dir-with-styling]="s2">
         `
            })
            class Cmp {
              h = '100px';
              w = '100px';
              s1: any = {border: '10px solid black', width: '200px'};
              s2: any = {border: '10px solid red', width: '300px'};
            }

            @Directive({selector: '[dir-with-styling]'})
            class DirectiveExpectingStyling {
              @Input('dir-with-styling') @HostBinding('style') public styles: any = null;
            }

            TestBed.configureTestingModule({declarations: [Cmp, DirectiveExpectingStyling]});
            const fixture = TestBed.createComponent(Cmp);
            fixture.detectChanges();

            const element = fixture.nativeElement.querySelector('div');
            expect(element.style.border).toEqual('10px solid black');
            expect(element.style.width).toEqual('100px');
            expect(element.style.height).toEqual('100px');

            fixture.componentInstance.s1 = null;
            fixture.detectChanges();

            expect(element.style.border).toEqual('10px solid red');
            expect(element.style.width).toEqual('100px');
            expect(element.style.height).toEqual('100px');
          });

  it('should retrieve styles set via Renderer2', () => {
    let dirInstance: any;
    @Directive({
      selector: '[dir]',
    })
    class Dir {
      constructor(public elementRef: ElementRef, public renderer: Renderer2) {
        dirInstance = this;
      }

      setStyles() {
        const nativeEl = this.elementRef.nativeElement;
        this.renderer.setStyle(nativeEl, 'transform', 'translate3d(0px, 0px, 0px)');
        this.renderer.addClass(nativeEl, 'my-class');
      }
    }

    @Component({template: `<div dir></div>`})
    class App {
    }

    TestBed.configureTestingModule({
      declarations: [App, Dir],
    });
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    dirInstance.setStyles();

    const div = fixture.debugElement.children[0];
    expect(div.styles.transform).toMatch(/translate3d\(0px\s*,\s*0px\s*,\s*0px\)/);
    expect(div.classes['my-class']).toBe(true);
  });

  it('should not set classes when falsy value is passed while a sanitizer is present', () => {
    @Component({
      // Note that we use `background` here because it needs to be sanitized.
      template: `
        <span class="container" [ngClass]="{disabled: isDisabled}"></span>
        <div [style.background]="background"></div>
      `,
    })

    class AppComponent {
      isDisabled = false;
      background = 'orange';
    }

    TestBed.configureTestingModule({declarations: [AppComponent]});
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    const span = fixture.nativeElement.querySelector('span');
    expect(span.classList).not.toContain('disabled');

    // The issue we're testing for happens after the second change detection.
    fixture.detectChanges();
    expect(span.classList).not.toContain('disabled');
  });

  it('should not set classes when falsy value is passed while a sanitizer from host bindings is present',
     () => {
       @Directive({selector: '[blockStyles]'})
       class StylesDirective {
         @HostBinding('style.border') border = '1px solid red';

         @HostBinding('style.background') background = 'white';
       }

       @Component({
         template: `<div class="container" [ngClass]="{disabled: isDisabled}" blockStyles></div>`,
       })
       class AppComponent {
         isDisabled = false;
       }

       TestBed.configureTestingModule({declarations: [AppComponent, StylesDirective]});
       const fixture = TestBed.createComponent(AppComponent);
       fixture.detectChanges();

       const div = fixture.nativeElement.querySelector('div');
       expect(div.classList.contains('disabled')).toBe(false);

       // The issue we're testing for happens after the second change detection.
       fixture.detectChanges();
       expect(div.classList.contains('disabled')).toBe(false);
     });

  it('should throw an error if a prop-based style/class binding value is changed during checkNoChanges',
     () => {
       @Component({
         template: `
        <div [style.color]="color" [class.foo]="fooClass"></div>
      `
       })
       class Cmp {
         color = 'red';
         fooClass = true;

         ngAfterViewInit() {
           this.color = 'blue';
           this.fooClass = false;
         }
       }

       TestBed.configureTestingModule({declarations: [Cmp]});
       const fixture = TestBed.createComponent(Cmp);

       expect(() => {
         fixture.detectChanges();
       }).toThrowError(/ExpressionChangedAfterItHasBeenCheckedError/);
     });

  onlyInIvy('only ivy allows for map-based style AND class bindings')
      .it('should throw an error if a map-based style/class binding value is changed during checkNoChanges',
          () => {
            @Component({
              template: `
                <div [style]="style" [class]="klass"></div>
              `
            })
            class Cmp {
              style: any = 'width: 100px';
              klass: any = 'foo';

              ngAfterViewInit() {
                this.style = 'height: 200px';
                this.klass = 'bar';
              }
            }

            TestBed.configureTestingModule({declarations: [Cmp]});
            const fixture = TestBed.createComponent(Cmp);

            expect(() => {
              fixture.detectChanges();
            }).toThrowError(/ExpressionChangedAfterItHasBeenCheckedError/);
          });

  it('should properly merge class interpolation with class-based directives', () => {
    @Component(
        {template: `<div class="zero {{one}}" [class.two]="true" [ngClass]="'three'"></div>`})
    class MyComp {
      one = 'one';
    }

    const fixture =
        TestBed.configureTestingModule({declarations: [MyComp]}).createComponent(MyComp);
    fixture.detectChanges();

    expect(fixture.debugElement.nativeElement.innerHTML).toContain('zero');
    expect(fixture.debugElement.nativeElement.innerHTML).toContain('one');
    expect(fixture.debugElement.nativeElement.innerHTML).toContain('two');
    expect(fixture.debugElement.nativeElement.innerHTML).toContain('three');
  });

  it('should allow to reset style property value defined using [style.prop.px] binding', () => {
    @Component({
      template: '<div [style.left.px]="left"></div>',
    })
    class MyComp {
      left = '';
    }

    TestBed.configureTestingModule({declarations: [MyComp]});
    const fixture = TestBed.createComponent(MyComp);
    fixture.detectChanges();

    const checks = [
      ['15', '15px'],
      [undefined, ''],
      [null, ''],
      ['', ''],
      ['0', '0px'],
    ];
    const div = fixture.nativeElement.querySelector('div');
    checks.forEach((check: any[]) => {
      const [fieldValue, expectedValue] = check;
      fixture.componentInstance.left = fieldValue;
      fixture.detectChanges();
      expect(div.style.left).toBe(expectedValue);
    });
  });

  onlyInIvy('only ivy treats [class] in concert with other class bindings')
      .it('should retain classes added externally', () => {
        @Component({template: `<div [class]="exp"></div>`})
        class MyComp {
          exp = '';
        }

        const fixture =
            TestBed.configureTestingModule({declarations: [MyComp]}).createComponent(MyComp);
        fixture.detectChanges();

        const div = fixture.nativeElement.querySelector('div')!;
        div.className += ' abc';
        expect(splitSortJoin(div.className)).toEqual('abc');

        fixture.componentInstance.exp = '1 2 3';
        fixture.detectChanges();

        expect(splitSortJoin(div.className)).toEqual('1 2 3 abc');

        fixture.componentInstance.exp = '4 5 6 7';
        fixture.detectChanges();

        expect(splitSortJoin(div.className)).toEqual('4 5 6 7 abc');

        function splitSortJoin(s: string) {
          return s.split(/\s+/).sort().join(' ').trim();
        }
      });

  describe('ExpressionChangedAfterItHasBeenCheckedError', () => {
    it('should not throw when bound to SafeValue', () => {
      @Component({template: `<div [style.background-image]="iconSafe"></div>`})
      class MyComp {
        icon = 'https://i.imgur.com/4AiXzf8.jpg';
        get iconSafe() {
          return this.sanitizer.bypassSecurityTrustStyle(`url("${this.icon}")`);
        }

        constructor(private sanitizer: DomSanitizer) {}
      }

      const fixture =
          TestBed.configureTestingModule({declarations: [MyComp]}).createComponent(MyComp);
      fixture.detectChanges(true /* Verify that check no changes does not cause an exception */);
      const div: HTMLElement = fixture.nativeElement.querySelector('div');
      expect(div.style.getPropertyValue('background-image'))
          .toEqual('url("https://i.imgur.com/4AiXzf8.jpg")');
    });
  });

  isBrowser && it('should process <style> tag contents extracted from template', () => {
    @Component({
      template: `
        <style>
          div { width: 10px; }
        </style>
        <div></div>
      `,
      styles: [
        'div { width: 100px; }',
      ]
    })
    class MyComp {
    }

    TestBed.configureTestingModule({
      declarations: [MyComp],
    });

    const fixture = TestBed.createComponent(MyComp);
    fixture.detectChanges();

    // `styles` array values are applied first, styles from <style> tags second.
    const div = fixture.nativeElement.querySelector('div');
    expect(getComputedStyle(div).width).toBe('10px');
  });

  onlyInIvy('[style] binding is supported in Ivy only')
      .it('should allow multiple styling bindings to work alongside property/attribute bindings',
          () => {
            @Component({
              template: `
        <div
            dir-that-sets-styles
            [style]="{'font-size': '300px'}"
            [attr.title]="'my-title'"
            [attr.data-foo]="'my-foo'">
        </div>`
            })
            class MyComp {
            }

            @Directive({selector: '[dir-that-sets-styles]'})
            class DirThatSetsStyling {
              @HostBinding('style.width') public w = '100px';
              @HostBinding('style.height') public h = '200px';
            }

            const fixture =
                TestBed.configureTestingModule({declarations: [MyComp, DirThatSetsStyling]})
                    .createComponent(MyComp);
            fixture.detectChanges();
            const div = fixture.nativeElement.querySelector('div')!;
            expect(div.style.getPropertyValue('width')).toEqual('100px');
            expect(div.style.getPropertyValue('height')).toEqual('200px');
            expect(div.style.getPropertyValue('font-size')).toEqual('300px');
            expect(div.getAttribute('title')).toEqual('my-title');
            expect(div.getAttribute('data-foo')).toEqual('my-foo');
          });

  onlyInIvy('VE clobers in case of  @HostBinding("class")')
      .it('should allow host styling on the root element with external styling', () => {
        @Component({template: '...'})
        class MyComp {
          @HostBinding('class') public classes = '';
        }

        const fixture =
            TestBed.configureTestingModule({declarations: [MyComp]}).createComponent(MyComp);
        fixture.detectChanges();
        const root = fixture.nativeElement as HTMLElement;
        expect(root.className).toEqual('');

        fixture.componentInstance.classes = '1 2 3';
        fixture.detectChanges();
        expect(root.className.split(/\s+/).sort().join(' ')).toEqual('1 2 3');

        root.classList.add('0');
        expect(root.className.split(/\s+/).sort().join(' ')).toEqual('0 1 2 3');

        fixture.componentInstance.classes = '1 2 3 4';
        fixture.detectChanges();
        expect(root.className.split(/\s+/).sort().join(' ')).toEqual('0 1 2 3 4');
      });

  it('should apply camelCased class names', () => {
    @Component({template: `<div [class]="'fooBar'" [class.barFoo]="true"></div>`})
    class MyComp {
    }

    TestBed.configureTestingModule({
      declarations: [MyComp],
    });
    const fixture = TestBed.createComponent(MyComp);
    fixture.detectChanges();

    const classList = (fixture.nativeElement.querySelector('div') as HTMLDivElement).classList;
    expect(classList.contains('fooBar')).toBeTruthy();
    expect(classList.contains('barFoo')).toBeTruthy();
  });

  onlyInIvy('[style] bindings are ivy only')
      .it('should convert camelCased style property names to snake-case', () => {
        @Component({template: `<div [style]="myStyles"></div>`})
        class MyComp {
          myStyles = {};
        }

        TestBed.configureTestingModule({
          declarations: [MyComp],
        });
        const fixture = TestBed.createComponent(MyComp);
        fixture.detectChanges();

        const div = fixture.nativeElement.querySelector('div') as HTMLDivElement;
        fixture.componentInstance.myStyles = {fontSize: '200px'};
        fixture.detectChanges();

        expect(div.style.getPropertyValue('font-size')).toEqual('200px');
      });

  it('should recover from an error thrown in styling bindings', () => {
    let raiseWidthError = false;

    @Component({template: `<div [style.width]="myWidth" [style.height]="'200px'"></div>`})
    class MyComp {
      get myWidth() {
        if (raiseWidthError) {
          throw new Error('...');
        }
        return '100px';
      }
    }

    TestBed.configureTestingModule({declarations: [MyComp]});
    const fixture = TestBed.createComponent(MyComp);

    raiseWidthError = true;
    expect(() => fixture.detectChanges()).toThrow();

    raiseWidthError = false;
    fixture.detectChanges();
    const div = fixture.nativeElement.querySelector('div') as HTMLDivElement;
    expect(div.style.getPropertyValue('width')).toEqual('100px');
    expect(div.style.getPropertyValue('height')).toEqual('200px');
  });

  onlyInIvy('Prioritization works in Ivy only')
      .it('should prioritize host bindings for templates first, then directives and finally components',
          () => {
            @Component({selector: 'my-comp-with-styling', template: ''})
            class MyCompWithStyling {
              @HostBinding('style') myStyles: any = {width: '300px'};

              @HostBinding('style.height') myHeight: any = '305px';
            }

            @Directive({selector: '[my-dir-with-styling]'})
            class MyDirWithStyling {
              @HostBinding('style') myStyles: any = {width: '200px'};

              @HostBinding('style.height') myHeight: any = '205px';
            }

            @Component({
              template: `
          <my-comp-with-styling
            style="height:1px; width:2px"
            my-dir-with-styling
            [style.height]="myHeight"
            [style]="myStyles">
          </my-comp-with-styling>
      `
            })
            class MyComp {
              myStyles: {width?: string} = {width: '100px'};
              myHeight: string|null|undefined = '100px';

              @ViewChild(MyDirWithStyling) dir!: MyDirWithStyling;
              @ViewChild(MyCompWithStyling) comp!: MyCompWithStyling;
            }

            TestBed.configureTestingModule(
                {declarations: [MyComp, MyCompWithStyling, MyDirWithStyling]});
            const fixture = TestBed.createComponent(MyComp);
            const comp = fixture.componentInstance;
            const elm = fixture.nativeElement.querySelector('my-comp-with-styling')!;

            fixture.detectChanges();
            expect(elm.style.width).toEqual('100px');
            expect(elm.style.height).toEqual('100px');

            comp.myStyles = {};
            comp.myHeight = undefined;
            fixture.detectChanges();
            expect(elm.style.width).toEqual('2px');
            expect(elm.style.height).toEqual('1px');

            comp.comp.myStyles = {};
            comp.comp.myHeight = undefined;
            fixture.detectChanges();
            expect(elm.style.width).toEqual('2px');
            expect(elm.style.height).toEqual('1px');

            comp.dir.myStyles = {};
            comp.dir.myHeight = undefined;
            fixture.detectChanges();
            expect(elm.style.width).toEqual('2px');
            expect(elm.style.height).toEqual('1px');
          });

  onlyInIvy('Prioritization works in Ivy only')
      .it('should prioritize directive static bindings over components', () => {
        @Component({selector: 'my-comp-with-styling', host: {style: 'color: blue'}, template: ''})
        class MyCompWithStyling {
        }

        @Directive({selector: '[my-dir-with-styling]', host: {style: 'color: red'}})
        class MyDirWithStyling {
        }

        @Component({template: `<my-comp-with-styling my-dir-with-styling></my-comp-with-styling>`})
        class MyComp {
        }

        TestBed.configureTestingModule(
            {declarations: [MyComp, MyCompWithStyling, MyDirWithStyling]});
        const fixture = TestBed.createComponent(MyComp);
        const elm = fixture.nativeElement.querySelector('my-comp-with-styling')!;

        fixture.detectChanges();
        expect(elm.style.color).toEqual('red');
      });


  it('should combine host class.foo bindings from multiple directives', () => {
    @Directive({
      selector: '[dir-that-sets-one-two]',
      exportAs: 'one',
    })
    class DirThatSetsOneTwo {
      @HostBinding('class.one') one = false;
      @HostBinding('class.two') two = false;
    }

    @Directive({
      selector: '[dir-that-sets-three-four]',
      exportAs: 'two',
    })
    class DirThatSetsThreeFour {
      @HostBinding('class.three') three = false;
      @HostBinding('class.four') four = false;
    }

    @Component({
      template: `
           <div #div1
             dir-that-sets-one-two
             dir-that-sets-three-four></div>
           <div #div2
             [class.zero]="zero"
             dir-that-sets-one-two
             dir-that-sets-three-four></div>
         `
    })
    class MyComp {
      @ViewChild('div1', {static: true, read: DirThatSetsOneTwo})
      public dirOneA: DirThatSetsOneTwo|null = null;

      @ViewChild('div1', {static: true, read: DirThatSetsThreeFour})
      public dirTwoA: DirThatSetsThreeFour|null = null;

      @ViewChild('div2', {static: true, read: DirThatSetsOneTwo})
      public dirOneB: DirThatSetsOneTwo|null = null;

      @ViewChild('div2', {static: true, read: DirThatSetsThreeFour})
      public dirTwoB: DirThatSetsThreeFour|null = null;

      zero = false;
    }

    TestBed.configureTestingModule(
        {declarations: [MyComp, DirThatSetsThreeFour, DirThatSetsOneTwo]});

    const fixture = TestBed.createComponent(MyComp);
    fixture.detectChanges();

    const [div1, div2] = fixture.nativeElement.querySelectorAll('div') as HTMLDivElement[];

    expect(div1.className).toBe('');
    expect(div2.className).toBe('');

    const comp = fixture.componentInstance;
    comp.dirOneA!.one = comp.dirOneB!.one = true;
    comp.dirOneA!.two = comp.dirOneB!.two = true;
    fixture.detectChanges();

    expect(div1.classList.contains('one')).toBeTruthy();
    expect(div1.classList.contains('two')).toBeTruthy();
    expect(div1.classList.contains('three')).toBeFalsy();
    expect(div1.classList.contains('four')).toBeFalsy();
    expect(div2.classList.contains('one')).toBeTruthy();
    expect(div2.classList.contains('two')).toBeTruthy();
    expect(div2.classList.contains('three')).toBeFalsy();
    expect(div2.classList.contains('four')).toBeFalsy();
    expect(div2.classList.contains('zero')).toBeFalsy();

    comp.dirTwoA!.three = comp.dirTwoB!.three = true;
    comp.dirTwoA!.four = comp.dirTwoB!.four = true;
    fixture.detectChanges();

    expect(div1.classList.contains('one')).toBeTruthy();
    expect(div1.classList.contains('two')).toBeTruthy();
    expect(div1.classList.contains('three')).toBeTruthy();
    expect(div1.classList.contains('four')).toBeTruthy();
    expect(div2.classList.contains('one')).toBeTruthy();
    expect(div2.classList.contains('two')).toBeTruthy();
    expect(div2.classList.contains('three')).toBeTruthy();
    expect(div2.classList.contains('four')).toBeTruthy();
    expect(div2.classList.contains('zero')).toBeFalsy();

    comp.zero = true;
    fixture.detectChanges();

    expect(div1.classList.contains('one')).toBeTruthy();
    expect(div1.classList.contains('two')).toBeTruthy();
    expect(div1.classList.contains('three')).toBeTruthy();
    expect(div1.classList.contains('four')).toBeTruthy();
    expect(div2.classList.contains('one')).toBeTruthy();
    expect(div2.classList.contains('two')).toBeTruthy();
    expect(div2.classList.contains('three')).toBeTruthy();
    expect(div2.classList.contains('four')).toBeTruthy();
    expect(div2.classList.contains('zero')).toBeTruthy();
  });

  it('should combine static host classes with component "class" host attribute', () => {
    @Component({selector: 'comp-with-classes', template: '', host: {'class': 'host'}})
    class CompWithClasses {
      constructor(ref: ElementRef) {
        ref.nativeElement.classList.add('custom');
      }
    }

    @Component({
      template: `<comp-with-classes class="inline" *ngFor="let item of items"></comp-with-classes>`
    })
    class MyComp {
      items = [1, 2, 3];
    }

    const fixture = TestBed
                        .configureTestingModule({
                          declarations: [MyComp, CompWithClasses],
                        })
                        .createComponent(MyComp);
    fixture.detectChanges();

    const [one, two, three] =
        fixture.nativeElement.querySelectorAll('comp-with-classes') as HTMLDivElement[];

    expect(one.classList.contains('custom')).toBeTruthy();
    expect(one.classList.contains('inline')).toBeTruthy();
    expect(one.classList.contains('host')).toBeTruthy();

    expect(two.classList.contains('custom')).toBeTruthy();
    expect(two.classList.contains('inline')).toBeTruthy();
    expect(two.classList.contains('host')).toBeTruthy();

    expect(three.classList.contains('custom')).toBeTruthy();
    expect(three.classList.contains('inline')).toBeTruthy();
    expect(three.classList.contains('host')).toBeTruthy();
  });

  it('should allow a single style host binding on an element', () => {
    @Component({template: `<div single-host-style-dir></div>`})
    class Cmp {
    }

    @Directive({selector: '[single-host-style-dir]'})
    class SingleHostStyleDir {
      @HostBinding('style.width') width = '100px';
    }

    TestBed.configureTestingModule({declarations: [Cmp, SingleHostStyleDir]});
    const fixture = TestBed.createComponent(Cmp);
    fixture.detectChanges();

    const element = fixture.nativeElement.querySelector('div');
    expect(element.style.width).toEqual('100px');
  });

  it('should override class bindings when a directive extends another directive', () => {
    @Component({template: `<child-comp class="template"></child-comp>`})
    class Cmp {
    }

    @Component({
      selector: 'parent-comp',
      host: {'class': 'parent-comp', '[class.parent-comp-active]': 'true'},
      template: '...',
    })
    class ParentComp {
    }

    @Component({
      selector: 'child-comp',
      host: {
        'class': 'child-comp',
        '[class.child-comp-active]': 'true',
        '[class.parent-comp]': 'false',
        '[class.parent-comp-active]': 'false'
      },
      template: '...',
    })
    class ChildComp extends ParentComp {
    }

    TestBed.configureTestingModule({declarations: [Cmp, ChildComp, ParentComp]});
    const fixture = TestBed.createComponent(Cmp);
    fixture.detectChanges();

    const element = fixture.nativeElement.querySelector('child-comp');
    expect(element.classList.contains('template')).toBeTruthy();

    expect(element.classList.contains('child-comp')).toBeTruthy();
    expect(element.classList.contains('child-comp-active')).toBeTruthy();

    expect(element.classList.contains('parent-comp')).toBeFalsy();
    expect(element.classList.contains('parent-comp-active')).toBeFalsy();
  });

  it('should not set inputs called class if they are not being used in the template', () => {
    const logs: string[] = [];

    @Directive({selector: '[test]'})
    class MyDir {
      @Input('class')
      set className(value: string) {
        logs.push(value);
      }
    }

    @Component({
      // Note that we shouldn't have a `class` attribute here.
      template: `<div test></div>`
    })
    class MyComp {
    }

    TestBed.configureTestingModule({declarations: [MyComp, MyDir]});
    const fixture = TestBed.createComponent(MyComp);
    fixture.detectChanges();

    expect(logs).toEqual([]);
  });

  describe('regression', () => {
    it('should support sanitizer value in the [style] bindings', () => {
      if (!ivyEnabled && !supportsWritingStringsToStyleProperty()) {
        // VE does not treat `[style]` as anything special, instead it simply writes to the
        // `style` property on the element like so `element.style=value`. This seems to work fine
        // every where except ie10, where it throws an error and as a consequence this test fails in
        // VE on ie10.
        return;
      }
      @Component({template: `<div [style]="style"></div>`})
      class HostBindingTestComponent {
        style: SafeStyle = this.sanitizer.bypassSecurityTrustStyle('color: white; display: block;');
        constructor(private sanitizer: DomSanitizer) {}
      }
      TestBed.configureTestingModule({declarations: [HostBindingTestComponent]});
      const fixture = TestBed.createComponent(HostBindingTestComponent);
      fixture.detectChanges();
      const div: HTMLElement = fixture.nativeElement.querySelector('div');
      expectStyle(div).toEqual({color: 'white', display: 'block'});
    });

    /**
     * Tests to see if the current browser supports non standard way of writing into styles.
     *
     * This is not the correct way to write to style and is not supported in ie10.
     * ```
     * div.style = 'color: white';
     * ```
     *
     * This is the correct way to write to styles:
     * ```
     * div.style.cssText = 'color: white';
     * ```
     *
     * Even though writing to `div.style` is not officially supported, it works in all
     * browsers except ie10.
     *
     * This function detects this condition and allows us to skip the test.
     */
    function supportsWritingStringsToStyleProperty() {
      const div = document.createElement('div');
      const CSS = 'color: white;';
      try {
        (div as any).style = CSS;
      } catch (e) {
        return false;
      }
      return div.style.cssText === CSS;
    }

    onlyInIvy('styling priority resolution is Ivy only feature.')
        .it('should allow lookahead binding on second pass #35118', () => {
          @Component({
            selector: 'my-cmp',
            template: ``,
            host: {
              '[class.foo]': 'hostClass',
            }
          })
          class MyCmp {
            hostClass = true;
          }

          @Directive({
            selector: '[host-styling]',
            host: {
              '[class]': 'hostClass',
            }
          })
          class HostStylingsDir {
            hostClass = {'bar': true};
          }

          @Component({template: `<my-cmp *ngFor="let i of [1,2]" host-styling></my-cmp>`})
          class MyApp {
            // When the first view in the list gets CD-ed, everything works.
            // When the second view gets CD-ed, the styling has already created the data structures
            // in the `TView`. As a result when `[class.foo]` runs it already knows that `[class]`
            // is a duplicate and hence it can overwrite the `[class.foo]` binding. While the
            // styling resolution is happening the algorithm  reads the value of the `[class]`
            // (because it overwrites `[class.foo]`), however  `[class]` has not yet executed and
            // therefore it does not have normalized value in its `LView`. The result is that the
            // assertions fails as it expects an `KeyValueArray`.
          }

          TestBed.configureTestingModule({declarations: [MyApp, MyCmp, HostStylingsDir]});
          const fixture = TestBed.createComponent(MyApp);
          expect(() => fixture.detectChanges()).not.toThrow();
          const [cmp1, cmp2] = fixture.nativeElement.querySelectorAll('my-cmp');
          expectClass(cmp1).toEqual({foo: true, bar: true});
          expectClass(cmp2).toEqual({foo: true, bar: true});
        });

    it('should not bind [class] to @Input("className")', () => {
      @Component({
        selector: 'my-cmp',
        template: `className = {{className}}`,
      })
      class MyCmp {
        @Input() className: string = 'unbound';
      }
      @Component({template: `<my-cmp [class]="'bound'"></my-cmp>`})
      class MyApp {
      }

      TestBed.configureTestingModule({declarations: [MyApp, MyCmp]});
      const fixture = TestBed.createComponent(MyApp);
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toEqual('className = unbound');
    });

    it('should not bind class to @Input("className")', () => {
      @Component({
        selector: 'my-cmp',
        template: `className = {{className}}`,
      })
      class MyCmp {
        @Input() className: string = 'unbound';
      }
      @Component({template: `<my-cmp class="bound"></my-cmp>`})
      class MyApp {
      }

      TestBed.configureTestingModule({declarations: [MyApp, MyCmp]});
      const fixture = TestBed.createComponent(MyApp);
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toEqual('className = unbound');
    });
  });
});

function assertStyleCounters(countForSet: number, countForRemove: number) {
  expect(ngDevMode!.rendererSetStyle).toEqual(countForSet);
  expect(ngDevMode!.rendererRemoveStyle).toEqual(countForRemove);
}

function assertStyle(element: HTMLElement, prop: string, value: any) {
  expect((element.style as any)[prop]).toEqual(value);
}

function expectStyle(element: HTMLElement) {
  return expect(getElementStyles(element));
}

function expectClass(element: HTMLElement) {
  return expect(getElementClasses(element));
}
