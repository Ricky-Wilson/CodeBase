/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {DOCUMENT, ɵgetDOM as getDOM} from '@angular/common';
import {Inject, Injectable, Optional} from '@angular/core';
import {ɵSharedStylesHost as SharedStylesHost, ɵTRANSITION_ID} from '@angular/platform-browser';

@Injectable()
export class ServerStylesHost extends SharedStylesHost {
  private head: any = null;

  constructor(
      @Inject(DOCUMENT) private doc: any,
      @Optional() @Inject(ɵTRANSITION_ID) private transitionId: string) {
    super();
    this.head = doc.getElementsByTagName('head')[0];
  }

  private _addStyle(style: string): void {
    let adapter = getDOM();
    const el = adapter.createElement('style');
    el.textContent = style;
    if (!!this.transitionId) {
      el.setAttribute('ng-transition', this.transitionId);
    }
    this.head.appendChild(el);
  }

  onStylesAdded(additions: Set<string>) {
    additions.forEach(style => this._addStyle(style));
  }
}
