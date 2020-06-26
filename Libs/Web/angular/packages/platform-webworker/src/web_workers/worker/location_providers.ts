/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {LOCATION_INITIALIZED, PlatformLocation} from '@angular/common';
import {APP_INITIALIZER, NgZone, StaticProvider} from '@angular/core';

import {WebWorkerPlatformLocation} from './platform_location';


/**
 * The {@link PlatformLocation} providers that should be added when the {@link Location} is used in
 * a worker context.
 *
 * @publicApi
 * @deprecated platform-webworker is deprecated in Angular and will be removed in a future version
 *     of Angular
 */
export const WORKER_APP_LOCATION_PROVIDERS: StaticProvider[] = [
  {provide: PlatformLocation, useClass: WebWorkerPlatformLocation} as any as StaticProvider, {
    provide: APP_INITIALIZER,
    useFactory: appInitFnFactory,
    multi: true,
    deps: [PlatformLocation, NgZone]
  },
  {provide: LOCATION_INITIALIZED, useFactory: locationInitialized, deps: [PlatformLocation]}
];

export function locationInitialized(platformLocation: WebWorkerPlatformLocation) {
  return platformLocation.initialized;
}

export function appInitFnFactory(platformLocation: WebWorkerPlatformLocation, zone: NgZone): () =>
    Promise<boolean> {
  return () => zone.runGuarded(() => platformLocation.init());
}
