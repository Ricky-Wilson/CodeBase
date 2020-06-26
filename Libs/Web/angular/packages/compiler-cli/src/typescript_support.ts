/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import * as ts from 'typescript';
import {compareVersions} from './diagnostics/typescript_version';

/**
 * Minimum supported TypeScript version
 * ∀ supported typescript version v, v >= MIN_TS_VERSION
 */
const MIN_TS_VERSION = '3.9.2';

/**
 * Supremum of supported TypeScript versions
 * ∀ supported typescript version v, v < MAX_TS_VERSION
 * MAX_TS_VERSION is not considered as a supported TypeScript version
 */
const MAX_TS_VERSION = '4.0.0';

/**
 * The currently used version of TypeScript, which can be adjusted for testing purposes using
 * `setTypeScriptVersionForTesting` and `restoreTypeScriptVersionForTesting` below.
 */
let tsVersion = ts.version;

export function setTypeScriptVersionForTesting(version: string): void {
  tsVersion = version;
}

export function restoreTypeScriptVersionForTesting(): void {
  tsVersion = ts.version;
}

/**
 * Checks whether a given version ∈ [minVersion, maxVersion[
 * An error will be thrown if the following statements are simultaneously true:
 * - the given version ∉ [minVersion, maxVersion[,
 *
 * @param version The version on which the check will be performed
 * @param minVersion The lower bound version. A valid version needs to be greater than minVersion
 * @param maxVersion The upper bound version. A valid version needs to be strictly less than
 * maxVersion
 *
 * @throws Will throw an error if the given version ∉ [minVersion, maxVersion[
 */
export function checkVersion(version: string, minVersion: string, maxVersion: string) {
  if ((compareVersions(version, minVersion) < 0 || compareVersions(version, maxVersion) >= 0)) {
    throw new Error(`The Angular Compiler requires TypeScript >=${minVersion} and <${
        maxVersion} but ${version} was found instead.`);
  }
}

export function verifySupportedTypeScriptVersion(): void {
  checkVersion(tsVersion, MIN_TS_VERSION, MAX_TS_VERSION);
}
