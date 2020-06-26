'use strict';

const {
  buildVersion,
  parseTagVersion,
  buildFromParts,
  isTagBuild,
} = require('../../broccoli/build-info');

QUnit.module('buildVersion', () => {
  flatMap(
    [
      {
        args: ['3.4.4', '396fae9206'],
        expected: '3.4.4+396fae9206',
      },
      {
        args: ['3.2.2', '94f2258f', 'canary'],
        expected: '3.2.2-canary+94f2258f',
      },
      {
        args: ['3.2.2', 'f572d396', 'canary'],
        expected: '3.2.2-canary+f572d396',
      },
      {
        args: ['3.1.1-beta.2', 'f572d396fae9206628714fb2ce00f72e94f2258f'],
        expected: '3.1.1-beta.2+f572d396fae9206628714fb2ce00f72e94f2258f',
      },
      {
        args: ['3.1.1-beta.2', 'f572d396fae9206628714fb2ce00f72e94f2258f', 'beta'],
        expected: '3.1.1-beta.2.beta+f572d396fae9206628714fb2ce00f72e94f2258f',
      },
      {
        args: ['3.1.1-beta.2+build.100', '94f2258f', 'beta'],
        expected: '3.1.1-beta.2.beta+build.100.94f2258f',
      },
    ],
    padEmptyArgs(3, [null, ''])
  ).forEach(({ args, expected }) => {
    QUnit.test(JSON.stringify(args), assert => {
      assert.equal(buildVersion(...args), expected);
    });
  });
});

QUnit.module('parseTagVersion', () => {
  [
    {
      tag: 'v3.4.4',
      expected: '3.4.4',
    },
    {
      tag: 'v3.1.1-beta.2',
      expected: '3.1.1-beta.2',
    },
    {
      tag: 'some-non-version-tag',
      expected: undefined,
    },
  ].forEach(({ tag, expected }) => {
    QUnit.test(JSON.stringify(tag), assert => {
      assert.equal(parseTagVersion(tag), expected);
    });
  });
});

QUnit.module('buildFromParts', () => {
  [
    {
      args: [
        '3.4.4', // Channel build, no tag
        {
          sha: 'f572d396fae9206628714fb2ce00f72e94f2258f',
          branch: 'master',
          tag: null,
        },
      ],
      expected: {
        tag: null,
        branch: 'master',
        sha: 'f572d396fae9206628714fb2ce00f72e94f2258f',
        shortSha: 'f572d396',
        channel: 'canary',
        packageVersion: '3.4.4',
        tagVersion: null,
        version: '3.4.4-canary+f572d396',
        isBuildForTag: false,
      },
    },
    {
      args: [
        '3.4.4', // Channel build on CI, tag
        {
          sha: 'f572d396fae9206628714fb2ce00f72e94f2258f',
          branch: '',
          tag: 'v3.4.4-beta.2',
        },
        true,
        'beta',
      ],
      expected: {
        tag: 'v3.4.4-beta.2',
        branch: 'beta',
        sha: 'f572d396fae9206628714fb2ce00f72e94f2258f',
        shortSha: 'f572d396',
        channel: 'beta',
        packageVersion: '3.4.4',
        tagVersion: '3.4.4-beta.2',
        version: '3.4.4-beta+f572d396',
        isBuildForTag: false,
      },
    },
    {
      args: [
        '3.4.4', // Tag build, CI
        {
          sha: 'f572d396fae9206628714fb2ce00f72e94f2258f',
          branch: '',
          tag: 'v3.4.4-beta.2',
        },
        true,
        'v3.4.4-beta.2',
      ],
      expected: {
        tag: 'v3.4.4-beta.2',
        branch: 'v3.4.4-beta.2',
        sha: 'f572d396fae9206628714fb2ce00f72e94f2258f',
        shortSha: 'f572d396',
        channel: 'v3-4-4-beta-2',
        packageVersion: '3.4.4',
        tagVersion: '3.4.4-beta.2',
        version: '3.4.4-beta.2',
        isBuildForTag: true,
      },
    },
    {
      args: [
        '3.4.4',
        {
          sha: 'f572d396fae9206628714fb2ce00f72e94f2258f',
          branch: '',
          tag: 'some weird tag',
        },
        true,
        'a "funky" branch',
      ],
      expected: {
        tag: 'some weird tag',
        branch: 'a "funky" branch',
        sha: 'f572d396fae9206628714fb2ce00f72e94f2258f',
        shortSha: 'f572d396',
        channel: 'a--funky--branch',
        packageVersion: '3.4.4',
        tagVersion: undefined,
        version: '3.4.4-a--funky--branch+f572d396',
        isBuildForTag: false,
      },
    },
  ].forEach(({ args, expected }) => {
    QUnit.test(JSON.stringify(args), assert => {
      assert.deepEqual(buildFromParts(...args), expected);
    });
  });
});

QUnit.module('isTagBuild', () => {
  QUnit.test('on CI', assert => {
    assert.equal(isTagBuild('v3.4.4', 'v3.4.4', true), true);
    assert.equal(isTagBuild('v3.4.4', 'release', true), false);
    assert.equal(isTagBuild('v3.4.4-beta.4', 'random-branch', true), false);
    assert.equal(isTagBuild(null, 'release', true), false);
  });

  QUnit.test('not on CI', assert => {
    assert.equal(isTagBuild('v3.4.4', 'release', false), true);
    assert.equal(isTagBuild('v3.4.4', null, false), true);
    assert.equal(isTagBuild('v3.4.4-beta.4', 'random-branch', false), true);
    assert.equal(isTagBuild(null, 'release', false), false);
  });
});

/**
 * @typedef {Object} MatrixEntry
 * @property {any[]} args
 * @property {any} expected
 */

/**
 * Creates additional matrix entries with alternative empty values.
 * @param {number} count
 * @param {any[]} replacements
 */
function padEmptyArgs(count, replacements) {
  /** @type {function(MatrixEntry): MatrixEntry[]} */
  let expand = entry => {
    let expanded = [entry];
    let { args, expected } = entry;
    if (args.length < count) {
      replacements.forEach(replacement => {
        expanded.push({ args: padArgs(args, count, replacement), expected });
      });
    }
    return expanded;
  };
  return expand;
}

/**
 * @param {any[]} args
 * @param {number} count
 * @param {any} value
 */
function padArgs(args, count, value) {
  let padded = args.slice(0);
  for (let i = args.length; i < count; i++) {
    padded.push(value);
  }
  return padded;
}

/**
 * @param {MatrixEntry[]} matrix
 * @param {function(MatrixEntry): MatrixEntry[]} f
 * @returns {MatrixEntry[]}
 */
function flatMap(matrix, f) {
  return matrix.reduce((acc, x) => acc.concat(f(x)), []);
}
