/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {DOCUMENT, ɵBrowserPlatformLocation as BrowserPlatformLocation} from '@angular/common';
import {Injector, NgZone, PLATFORM_INITIALIZER, StaticProvider} from '@angular/core';

import {MessageBus} from '../shared/message_bus';
import {Serializer} from '../shared/serializer';
import {ServiceMessageBrokerFactory} from '../shared/service_message_broker';

import {MessageBasedPlatformLocation} from './platform_location';



/**
 * A list of {@link Provider}s. To use the router in a Worker enabled application you must
 * include these providers when setting up the render thread.
 * @publicApi
 * @deprecated platform-webworker is deprecated in Angular and will be removed in a future version
 *     of Angular
 */
export const WORKER_UI_LOCATION_PROVIDERS = <StaticProvider[]>[
  {
    provide: MessageBasedPlatformLocation,
    deps: [ServiceMessageBrokerFactory, BrowserPlatformLocation, MessageBus, Serializer]
  },
  {provide: BrowserPlatformLocation, deps: [DOCUMENT]},
  {provide: PLATFORM_INITIALIZER, useFactory: initUiLocation, multi: true, deps: [Injector]}
];

function initUiLocation(injector: Injector): () => void {
  return () => {
    const zone = injector.get<NgZone>(NgZone);

    zone.runGuarded(() => injector.get(MessageBasedPlatformLocation).start());
  };
}
