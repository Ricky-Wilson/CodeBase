/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {NgModule} from '@angular/core';
import {WorkerAppModule} from '@angular/platform-webworker';
import {platformWorkerAppDynamic} from '@angular/platform-webworker-dynamic';

import {InputCmp} from './index_common';

@NgModule({imports: [WorkerAppModule], bootstrap: [InputCmp], declarations: [InputCmp]})
export class ExampleModule {
}

platformWorkerAppDynamic().bootstrapModule(ExampleModule);
