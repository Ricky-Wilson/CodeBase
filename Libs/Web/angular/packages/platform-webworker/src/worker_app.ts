/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {CommonModule, DOCUMENT, ViewportScroller, ɵNullViewportScroller as NullViewportScroller, ɵPLATFORM_WORKER_APP_ID as PLATFORM_WORKER_APP_ID} from '@angular/common';
import {APP_INITIALIZER, ApplicationModule, createPlatformFactory, ErrorHandler, NgModule, NgZone, PLATFORM_ID, platformCore, PlatformRef, RendererFactory2, StaticProvider, ɵINJECTOR_SCOPE as INJECTOR_SCOPE} from '@angular/core';
import {ɵBROWSER_SANITIZATION_PROVIDERS as BROWSER_SANITIZATION_PROVIDERS} from '@angular/platform-browser';

import {ON_WEB_WORKER} from './web_workers/shared/api';
import {ClientMessageBrokerFactory} from './web_workers/shared/client_message_broker';
import {MessageBus} from './web_workers/shared/message_bus';
import {PostMessageBus, PostMessageBusSink, PostMessageBusSource} from './web_workers/shared/post_message_bus';
import {RenderStore} from './web_workers/shared/render_store';
import {Serializer} from './web_workers/shared/serializer';
import {ServiceMessageBrokerFactory} from './web_workers/shared/service_message_broker';
import {WebWorkerRendererFactory2} from './web_workers/worker/renderer';
import {WorkerDomAdapter} from './web_workers/worker/worker_adapter';

/**
 * @publicApi
 * @deprecated platform-webworker is deprecated in Angular and will be removed in a future version
 *     of Angular
 */
export const platformWorkerApp: (extraProviders?: StaticProvider[]|undefined) => PlatformRef =
    createPlatformFactory(
        platformCore, 'workerApp', [{provide: PLATFORM_ID, useValue: PLATFORM_WORKER_APP_ID}]);

export function errorHandler(): ErrorHandler {
  return new ErrorHandler();
}


// TODO(jteplitz602): remove this and compile with lib.webworker.d.ts (#3492)
const _postMessage = {
  postMessage: (message: any, transferrables: [Transferable]) => {
    (<any>postMessage)(message, transferrables);
  }
};

export function createMessageBus(zone: NgZone): MessageBus {
  const sink = new PostMessageBusSink(_postMessage);
  const source = new PostMessageBusSource();
  const bus = new PostMessageBus(sink, source);
  bus.attachToZone(zone);
  return bus;
}

export function setupWebWorker(): void {
  WorkerDomAdapter.makeCurrent();
}

/**
 * The ng module for the worker app side.
 *
 * @publicApi
 * @deprecated platform-webworker is deprecated in Angular and will be removed in a future version
 *     of Angular
 */
@NgModule({
  providers: [
    BROWSER_SANITIZATION_PROVIDERS,
    {provide: INJECTOR_SCOPE, useValue: 'root'},
    Serializer,
    {provide: DOCUMENT, useValue: null},
    ClientMessageBrokerFactory,
    ServiceMessageBrokerFactory,
    WebWorkerRendererFactory2,
    {provide: RendererFactory2, useExisting: WebWorkerRendererFactory2},
    {provide: ON_WEB_WORKER, useValue: true},
    RenderStore,
    {provide: ErrorHandler, useFactory: errorHandler, deps: []},
    {provide: MessageBus, useFactory: createMessageBus, deps: [NgZone]},
    {provide: APP_INITIALIZER, useValue: setupWebWorker, multi: true},
    {provide: ViewportScroller, useClass: NullViewportScroller, deps: []},
  ],
  exports: [
    CommonModule,
    ApplicationModule,
  ]
})
export class WorkerAppModule {
}
