/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

importScripts('angular/modules/playground/src/web_workers/worker-configure.js');

System.config({packages: {'angular/modules/playground/src/web_workers': {defaultExtension: 'js'}}});

System.import('./background_index.js')
    .catch(error => console.error('error loading background', error));
