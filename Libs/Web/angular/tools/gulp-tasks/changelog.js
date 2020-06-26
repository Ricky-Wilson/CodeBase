/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

module.exports = (gulp) => () => {
  const conventionalChangelog = require('gulp-conventional-changelog');
  const ignoredScopes = [
    'aio',
    'dev-infra',
    'docs-infra',
    'zone.js',
  ];

  return gulp.src('CHANGELOG.md')
      .pipe(conventionalChangelog({preset: 'angular'}, {}, {
        // Ignore commits that start with `<type>(<scope>)` for any of the ignored scopes.
        extendedRegexp: true,
        grep: `^[^(]+\\((${ignoredScopes.join('|')})\\)`,
        invertGrep: true,
      }))
      .pipe(gulp.dest('./'));
};
