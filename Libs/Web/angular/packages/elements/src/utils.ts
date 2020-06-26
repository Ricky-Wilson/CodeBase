/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {ComponentFactoryResolver, Injector, Type} from '@angular/core';

const matches = (() => {
  const elProto = Element.prototype as any;
  return elProto.matches || elProto.matchesSelector || elProto.mozMatchesSelector ||
      elProto.msMatchesSelector || elProto.oMatchesSelector || elProto.webkitMatchesSelector;
})();

/**
 * Provide methods for scheduling the execution of a callback.
 */
export const scheduler = {
  /**
   * Schedule a callback to be called after some delay.
   *
   * Returns a function that when executed will cancel the scheduled function.
   */
  schedule(taskFn: () => void, delay: number): () => void {
    const id = setTimeout(taskFn, delay);
    return () => clearTimeout(id);
  },

  /**
   * Schedule a callback to be called before the next render.
   * (If `window.requestAnimationFrame()` is not available, use `scheduler.schedule()` instead.)
   *
   * Returns a function that when executed will cancel the scheduled function.
   */
  scheduleBeforeRender(taskFn: () => void): () => void {
    // TODO(gkalpak): Implement a better way of accessing `requestAnimationFrame()`
    //                (e.g. accounting for vendor prefix, SSR-compatibility, etc).
    if (typeof window === 'undefined') {
      // For SSR just schedule immediately.
      return scheduler.schedule(taskFn, 0);
    }

    if (typeof window.requestAnimationFrame === 'undefined') {
      const frameMs = 16;
      return scheduler.schedule(taskFn, frameMs);
    }

    const id = window.requestAnimationFrame(taskFn);
    return () => window.cancelAnimationFrame(id);
  },
};

/**
 * Convert a camelCased string to kebab-cased.
 */
export function camelToDashCase(input: string): string {
  return input.replace(/[A-Z]/g, char => `-${char.toLowerCase()}`);
}

/**
 * Create a `CustomEvent` (even on browsers where `CustomEvent` is not a constructor).
 */
export function createCustomEvent(doc: Document, name: string, detail: any): CustomEvent {
  const bubbles = false;
  const cancelable = false;

  // On IE9-11, `CustomEvent` is not a constructor.
  if (typeof CustomEvent !== 'function') {
    const event = doc.createEvent('CustomEvent');
    event.initCustomEvent(name, bubbles, cancelable, detail);
    return event;
  }

  return new CustomEvent(name, {bubbles, cancelable, detail});
}

/**
 * Check whether the input is an `Element`.
 */
export function isElement(node: Node|null): node is Element {
  return !!node && node.nodeType === Node.ELEMENT_NODE;
}

/**
 * Check whether the input is a function.
 */
export function isFunction(value: any): value is Function {
  return typeof value === 'function';
}

/**
 * Convert a kebab-cased string to camelCased.
 */
export function kebabToCamelCase(input: string): string {
  return input.replace(/-([a-z\d])/g, (_, char) => char.toUpperCase());
}

/**
 * Check whether an `Element` matches a CSS selector.
 */
export function matchesSelector(element: Element, selector: string): boolean {
  return matches.call(element, selector);
}

/**
 * Test two values for strict equality, accounting for the fact that `NaN !== NaN`.
 */
export function strictEquals(value1: any, value2: any): boolean {
  return value1 === value2 || (value1 !== value1 && value2 !== value2);
}

/** Gets a map of default set of attributes to observe and the properties they affect. */
export function getDefaultAttributeToPropertyInputs(
    inputs: {propName: string, templateName: string}[]) {
  const attributeToPropertyInputs: {[key: string]: string} = {};
  inputs.forEach(({propName, templateName}) => {
    attributeToPropertyInputs[camelToDashCase(templateName)] = propName;
  });

  return attributeToPropertyInputs;
}

/**
 * Gets a component's set of inputs. Uses the injector to get the component factory where the inputs
 * are defined.
 */
export function getComponentInputs(
    component: Type<any>, injector: Injector): {propName: string, templateName: string}[] {
  const componentFactoryResolver: ComponentFactoryResolver = injector.get(ComponentFactoryResolver);
  const componentFactory = componentFactoryResolver.resolveComponentFactory(component);
  return componentFactory.inputs;
}
