/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {discardPeriodicTasksFallback, fakeAsyncFallback, flushFallback, flushMicrotasksFallback, resetFakeAsyncZoneFallback, tickFallback} from './fake_async_fallback';

const _Zone: any = typeof Zone !== 'undefined' ? Zone : null;
const fakeAsyncTestModule = _Zone && _Zone[_Zone.__symbol__('fakeAsyncTest')];

/**
 * Clears out the shared fake async zone for a test.
 * To be called in a global `beforeEach`.
 *
 * @publicApi
 */
export function resetFakeAsyncZone(): void {
  if (fakeAsyncTestModule) {
    return fakeAsyncTestModule.resetFakeAsyncZone();
  } else {
    return resetFakeAsyncZoneFallback();
  }
}

/**
 * Wraps a function to be executed in the fakeAsync zone:
 * - microtasks are manually executed by calling `flushMicrotasks()`,
 * - timers are synchronous, `tick()` simulates the asynchronous passage of time.
 *
 * If there are any pending timers at the end of the function, an exception will be thrown.
 *
 * Can be used to wrap inject() calls.
 *
 * @usageNotes
 * ### Example
 *
 * {@example core/testing/ts/fake_async.ts region='basic'}
 *
 * @param fn
 * @returns The function wrapped to be executed in the fakeAsync zone
 *
 * @publicApi
 */
export function fakeAsync(fn: Function): (...args: any[]) => any {
  if (fakeAsyncTestModule) {
    return fakeAsyncTestModule.fakeAsync(fn);
  } else {
    return fakeAsyncFallback(fn);
  }
}

/**
 * Simulates the asynchronous passage of time for the timers in the fakeAsync zone.
 *
 * The microtasks queue is drained at the very start of this function and after any timer callback
 * has been executed.
 *
 * @usageNotes
 * ### Example
 *
 * {@example core/testing/ts/fake_async.ts region='basic'}
 *
 * @param millis, the number of millisecond to advance the virtual timer
 * @param tickOptions, the options of tick with a flag called
 * processNewMacroTasksSynchronously, whether to invoke the new macroTasks, by default is
 * false, means the new macroTasks will be invoked
 *
 * For example,
 *
 * it ('test with nested setTimeout', fakeAsync(() => {
 *   let nestedTimeoutInvoked = false;
 *   function funcWithNestedTimeout() {
 *     setTimeout(() => {
 *       nestedTimeoutInvoked = true;
 *     });
 *   };
 *   setTimeout(funcWithNestedTimeout);
 *   tick();
 *   expect(nestedTimeoutInvoked).toBe(true);
 * }));
 *
 * in this case, we have a nested timeout (new macroTask), when we tick, both the
 * funcWithNestedTimeout and the nested timeout both will be invoked.
 *
 * it ('test with nested setTimeout', fakeAsync(() => {
 *   let nestedTimeoutInvoked = false;
 *   function funcWithNestedTimeout() {
 *     setTimeout(() => {
 *       nestedTimeoutInvoked = true;
 *     });
 *   };
 *   setTimeout(funcWithNestedTimeout);
 *   tick(0, {processNewMacroTasksSynchronously: false});
 *   expect(nestedTimeoutInvoked).toBe(false);
 * }));
 *
 * if we pass the tickOptions with processNewMacroTasksSynchronously to be false, the nested timeout
 * will not be invoked.
 *
 *
 * @publicApi
 */
export function tick(
    millis: number = 0, tickOptions: {processNewMacroTasksSynchronously: boolean} = {
      processNewMacroTasksSynchronously: true
    }): void {
  if (fakeAsyncTestModule) {
    return fakeAsyncTestModule.tick(millis, tickOptions);
  } else {
    return tickFallback(millis, tickOptions);
  }
}

/**
 * Simulates the asynchronous passage of time for the timers in the fakeAsync zone by
 * draining the macrotask queue until it is empty. The returned value is the milliseconds
 * of time that would have been elapsed.
 *
 * @param maxTurns
 * @returns The simulated time elapsed, in millis.
 *
 * @publicApi
 */
export function flush(maxTurns?: number): number {
  if (fakeAsyncTestModule) {
    return fakeAsyncTestModule.flush(maxTurns);
  } else {
    return flushFallback(maxTurns);
  }
}

/**
 * Discard all remaining periodic tasks.
 *
 * @publicApi
 */
export function discardPeriodicTasks(): void {
  if (fakeAsyncTestModule) {
    return fakeAsyncTestModule.discardPeriodicTasks();
  } else {
    discardPeriodicTasksFallback();
  }
}

/**
 * Flush any pending microtasks.
 *
 * @publicApi
 */
export function flushMicrotasks(): void {
  if (fakeAsyncTestModule) {
    return fakeAsyncTestModule.flushMicrotasks();
  } else {
    return flushMicrotasksFallback();
  }
}
