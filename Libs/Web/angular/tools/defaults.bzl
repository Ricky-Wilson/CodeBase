"""Re-export of some bazel rules with repository-wide defaults."""

load("@bazel_tools//tools/build_defs/pkg:pkg.bzl", "pkg_tar")
load("@build_bazel_rules_nodejs//:index.bzl", _nodejs_binary = "nodejs_binary", _pkg_npm = "pkg_npm")
load("@npm_bazel_jasmine//:index.bzl", _jasmine_node_test = "jasmine_node_test")
load("@npm_bazel_karma//:index.bzl", _karma_web_test = "karma_web_test", _karma_web_test_suite = "karma_web_test_suite")
load("@npm_bazel_rollup//:index.bzl", _rollup_bundle = "rollup_bundle")
load("@npm_bazel_terser//:index.bzl", "terser_minified")
load("@npm_bazel_typescript//:index.bzl", _ts_devserver = "ts_devserver", _ts_library = "ts_library")
load("@npm_bazel_protractor//:index.bzl", _protractor_web_test_suite = "protractor_web_test_suite")
load("@npm//typescript:index.bzl", "tsc")
load("//packages/bazel:index.bzl", _ng_module = "ng_module", _ng_package = "ng_package")
load("//dev-infra/benchmark/ng_rollup_bundle:ng_rollup_bundle.bzl", _ng_rollup_bundle = "ng_rollup_bundle")
load("//tools:ng_benchmark.bzl", _ng_benchmark = "ng_benchmark")
load("//tools/ts-api-guardian:index.bzl", _ts_api_guardian_test = "ts_api_guardian_test", _ts_api_guardian_test_npm_package = "ts_api_guardian_test_npm_package")

_DEFAULT_TSCONFIG_TEST = "//packages:tsconfig-test"
_INTERNAL_NG_MODULE_API_EXTRACTOR = "//packages/bazel/src/api-extractor:api_extractor"
_INTERNAL_NG_MODULE_COMPILER = "//packages/bazel/src/ngc-wrapped"
_INTERNAL_NG_MODULE_XI18N = "//packages/bazel/src/ngc-wrapped:xi18n"
_INTERNAL_NG_PACKAGE_PACKAGER = "//packages/bazel/src/ng_package:packager"
_INTERNAL_NG_PACKAGE_DEFALUT_TERSER_CONFIG_FILE = "//packages/bazel/src/ng_package:terser_config.default.json"
_INTERNAL_NG_PACKAGE_DEFAULT_ROLLUP_CONFIG_TMPL = "//packages/bazel/src/ng_package:rollup.config.js"
_INTERNAL_NG_PACKAGE_DEFAULT_ROLLUP = "//packages/bazel/src/ng_package:rollup_for_ng_package"

# Packages which are versioned together on npm
ANGULAR_SCOPED_PACKAGES = ["@angular/%s" % p for p in [
    # core should be the first package because it's the main package in the group
    # this is significant for Angular CLI and "ng update" specifically, @angular/core
    # is considered the identifier of the group by these tools.
    "core",
    "bazel",
    "common",
    "compiler",
    "compiler-cli",
    "animations",
    "elements",
    "platform-browser",
    "platform-browser-dynamic",
    "forms",
    # Current plan for Angular v8 is to not include @angular/http in ng update
    # "http",
    "platform-server",
    "platform-webworker",
    "platform-webworker-dynamic",
    "upgrade",
    "router",
    "language-service",
    "localize",
    "service-worker",
]]

PKG_GROUP_REPLACEMENTS = {
    "\"NG_UPDATE_PACKAGE_GROUP\"": """[
      %s
    ]""" % ",\n      ".join(["\"%s\"" % s for s in ANGULAR_SCOPED_PACKAGES]),
}

def _default_module_name(testonly):
    """ Provide better defaults for package names.

    e.g. rather than angular/packages/core/testing we want @angular/core/testing

    TODO(alexeagle): we ought to supply a default module name for every library in the repo.
    But we short-circuit below in cases that are currently not working.
    """
    pkg = native.package_name()

    if testonly:
        # Some tests currently rely on the long-form package names
        return None

    if pkg.startswith("packages/bazel"):
        # Avoid infinite recursion in the ViewEngine compiler. Error looks like:
        #  Compiling Angular templates (ngc) //packages/bazel/test/ngc-wrapped/empty:empty failed (Exit 1)
        # : RangeError: Maximum call stack size exceeded
        #    at normalizeString (path.js:57:25)
        #    at Object.normalize (path.js:1132:12)
        #    at Object.join (path.js:1167:18)
        #    at resolveModule (execroot/angular/bazel-out/host/bin/packages/bazel/src/ngc-wrapped/ngc-wrapped.runfiles/angular/packages/compiler-cli/src/metadata/bundler.js:582:50)
        #    at MetadataBundler.exportAll (execroot/angular/bazel-out/host/bin/packages/bazel/src/ngc-wrapped/ngc-wrapped.runfiles/angular/packages/compiler-cli/src/metadata/bundler.js:119:42)
        #    at MetadataBundler.exportAll (execroot/angular/bazel-out/host/bin/packages/bazel/src/ngc-wrapped/ngc-wrapped.runfiles/angular/packages/compiler-cli/src/metadata/bundler.js:121:52)
        return None

    if pkg.startswith("packages/"):
        return "@angular/" + pkg[len("packages/"):]

    return None

def ts_devserver(**kwargs):
    """Default values for ts_devserver"""
    serving_path = kwargs.pop("serving_path", "/app_bundle.js")
    _ts_devserver(
        serving_path = serving_path,
        **kwargs
    )

def ts_library(name, tsconfig = None, testonly = False, deps = [], module_name = None, **kwargs):
    """Default values for ts_library"""
    deps = deps + ["@npm//tslib"]
    if testonly:
        # Match the types[] in //packages:tsconfig-test.json
        deps.append("@npm//@types/jasmine")
        deps.append("@npm//@types/node")
        deps.append("@npm//@types/events")
    if not tsconfig and testonly:
        tsconfig = _DEFAULT_TSCONFIG_TEST

    if not module_name:
        module_name = _default_module_name(testonly)

    _ts_library(
        name = name,
        tsconfig = tsconfig,
        testonly = testonly,
        deps = deps,
        module_name = module_name,
        **kwargs
    )

    # Select the es5 .js output of the ts_library for use in downstream boostrap targets
    # with `output_group = "es5_sources"`. This exposes an internal detail of ts_library
    # that is not ideal.
    # TODO(gregmagolan): clean this up by using tsc() in these cases rather than ts_library
    native.filegroup(
        name = "%s_es5" % name,
        srcs = [":%s" % name],
        testonly = testonly,
        output_group = "es5_sources",
    )

def ng_module(name, tsconfig = None, entry_point = None, testonly = False, deps = [], module_name = None, bundle_dts = True, **kwargs):
    """Default values for ng_module"""
    deps = deps + ["@npm//tslib"]
    if testonly:
        # Match the types[] in //packages:tsconfig-test.json
        deps.append("@npm//@types/jasmine")
        deps.append("@npm//@types/node")
        deps.append("@npm//@types/events")
    if not tsconfig and testonly:
        tsconfig = _DEFAULT_TSCONFIG_TEST

    if not module_name:
        module_name = _default_module_name(testonly)
    if not entry_point:
        entry_point = "public_api.ts"
    _ng_module(
        name = name,
        flat_module_out_file = name,
        tsconfig = tsconfig,
        entry_point = entry_point,
        testonly = testonly,
        bundle_dts = bundle_dts,
        deps = deps,
        compiler = _INTERNAL_NG_MODULE_COMPILER,
        api_extractor = _INTERNAL_NG_MODULE_API_EXTRACTOR,
        ng_xi18n = _INTERNAL_NG_MODULE_XI18N,
        module_name = module_name,
        **kwargs
    )

def ng_package(name, readme_md = None, license_banner = None, deps = [], **kwargs):
    """Default values for ng_package"""
    if not readme_md:
        readme_md = "//packages:README.md"
    if not license_banner:
        license_banner = "//packages:license-banner.txt"
    deps = deps + [
        "@npm//tslib",
    ]
    visibility = kwargs.pop("visibility", None)

    _ng_package(
        name = name,
        deps = deps,
        readme_md = readme_md,
        license_banner = license_banner,
        substitutions = PKG_GROUP_REPLACEMENTS,
        ng_packager = _INTERNAL_NG_PACKAGE_PACKAGER,
        terser_config_file = _INTERNAL_NG_PACKAGE_DEFALUT_TERSER_CONFIG_FILE,
        rollup_config_tmpl = _INTERNAL_NG_PACKAGE_DEFAULT_ROLLUP_CONFIG_TMPL,
        rollup = _INTERNAL_NG_PACKAGE_DEFAULT_ROLLUP,
        visibility = visibility,
        **kwargs
    )

    pkg_tar(
        name = name + "_archive",
        srcs = [":%s" % name],
        extension = "tar.gz",
        strip_prefix = "./%s" % name,
        # should not be built unless it is a dependency of another rule
        tags = ["manual"],
        visibility = visibility,
    )

def pkg_npm(name, substitutions = {}, **kwargs):
    """Default values for pkg_npm"""
    visibility = kwargs.pop("visibility", None)

    _pkg_npm(
        name = name,
        substitutions = dict(substitutions, **PKG_GROUP_REPLACEMENTS),
        visibility = visibility,
        **kwargs
    )

    pkg_tar(
        name = name + "_archive",
        srcs = [":%s" % name],
        extension = "tar.gz",
        strip_prefix = "./%s" % name,
        # should not be built unless it is a dependency of another rule
        tags = ["manual"],
        visibility = visibility,
    )

def karma_web_test_suite(name, **kwargs):
    """Default values for karma_web_test_suite"""

    # Default value for bootstrap
    bootstrap = kwargs.pop("bootstrap", [
        "//:web_test_bootstrap_scripts",
    ])

    # Add common deps
    deps = kwargs.pop("deps", []) + [
        "@npm//karma-browserstack-launcher",
        "@npm//karma-sauce-launcher",
        "@npm//:node_modules/tslib/tslib.js",
        "//tools/rxjs:rxjs_umd_modules",
        "//packages/zone.js:npm_package",
    ]

    # Add common runtime deps
    runtime_deps = kwargs.pop("runtime_deps", []) + [
        "//tools/testing:browser",
    ]

    data = kwargs.pop("data", [])
    tags = kwargs.pop("tags", [])

    _karma_web_test_suite(
        name = name,
        runtime_deps = runtime_deps,
        bootstrap = bootstrap,
        deps = deps,
        browsers = ["//dev-infra/browsers:chromium"],
        data = data,
        tags = tags,
        **kwargs
    )

    # Add a saucelabs target for these karma tests
    _karma_web_test(
        name = "saucelabs_%s" % name,
        # Default timeout is moderate (5min). This causes the test to be terminated while
        # Saucelabs browsers keep running. Ultimately resulting in failing tests and browsers
        # unnecessarily being acquired. Our specified Saucelabs idle timeout is 10min, so we use
        # Bazel's long timeout (15min). This ensures that Karma can shut down properly.
        timeout = "long",
        runtime_deps = runtime_deps,
        bootstrap = bootstrap,
        config_file = "//:karma-js.conf.js",
        deps = deps,
        data = data + [
            "//:browser-providers.conf.js",
            "//tools:jasmine-seed-generator.js",
        ],
        karma = "//tools/saucelabs:karma-saucelabs",
        tags = tags + [
            "exclusive",
            "manual",
            "no-remote-exec",
            "saucelabs",
        ],
        configuration_env_vars = ["KARMA_WEB_TEST_MODE"],
        **kwargs
    )

def protractor_web_test_suite(**kwargs):
    """Default values for protractor_web_test_suite"""

    _protractor_web_test_suite(
        browsers = ["//dev-infra/browsers:chromium"],
        **kwargs
    )

def ng_benchmark(**kwargs):
    """Default values for ng_benchmark"""
    _ng_benchmark(**kwargs)

def nodejs_binary(data = [], **kwargs):
    """Default values for nodejs_binary"""
    _nodejs_binary(
        configuration_env_vars = ["angular_ivy_enabled"],
        data = data + ["@npm//source-map-support"],
        **kwargs
    )

def jasmine_node_test(bootstrap = [], **kwargs):
    """Default values for jasmine_node_test

    Args:
      bootstrap: A list of labels of scripts to run before the entry_point.

                 The labels can either be individual files or a filegroup that contain a single
                 file.

                 The label is automatically added to the deps of jasmine_node_test.
                 If the label ends in `_es5` which by convention selects the es5 outputs
                 of a ts_library rule, then corresponding ts_library target sans `_es5`
                 is also added to the deps of jasmine_node_test.

                 For example with,

                 jasmine_node_test(
                     name = "test",
                     bootstrap = ["//tools/testing:node_es5"],
                     deps = [":test_lib"],
                 )

                 the `//tools/testing:node` target will automatically get added to deps
                 by this macro. This removes the need for duplicate deps on the
                 target and makes the usage of this rule less verbose."""

    # Very common dependencies for tests
    deps = kwargs.pop("deps", []) + [
        "@npm//chokidar",
        "@npm//domino",
        "@npm//jasmine-core",
        "@npm//reflect-metadata",
        "@npm//source-map-support",
        "@npm//tslib",
        "@npm//xhr2",
    ]
    configuration_env_vars = kwargs.pop("configuration_env_vars", []) + [
        "angular_ivy_enabled",
    ]
    templated_args = kwargs.pop("templated_args", [])
    for label in bootstrap:
        deps += [label]
        templated_args += ["--node_options=--require=$$(rlocation $(rootpath %s))" % label]
        if label.endswith("_es5"):
            # If this label is a filegroup derived from a ts_library then automatically
            # add the ts_library target (which is the label sans `_es5`) to deps so we pull
            # in all of its transitive deps. This removes the need for duplicate deps on the
            # target and makes the usage of this rule less verbose.
            deps += [label[:-4]]

    _jasmine_node_test(
        deps = deps,
        configuration_env_vars = configuration_env_vars,
        templated_args = templated_args,
        **kwargs
    )

def ng_rollup_bundle(deps = [], **kwargs):
    """Default values for ng_rollup_bundle"""
    deps = deps + [
        "@npm//tslib",
        "@npm//reflect-metadata",
    ]
    _ng_rollup_bundle(
        deps = deps,
        **kwargs
    )

def rollup_bundle(name, testonly = False, sourcemap = "true", **kwargs):
    """A drop in replacement for the rules nodejs [legacy rollup_bundle].

    Runs [rollup_bundle], [terser_minified] and [babel] for downleveling to es5
    to produce a number of output bundles.

    es2015 iife                  : "%{name}.es2015.js"
    es2015 iife minified         : "%{name}.min.es2015.js"
    es2015 iife minified (debug) : "%{name}.min_debug.es2015.js"
    es5 iife                     : "%{name}.js"
    es5 iife minified            : "%{name}.min.js"
    es5 iife minified (debug)    : "%{name}.min_debug.js"
    es5 umd                      : "%{name}.es5umd.js"
    es5 umd minified             : "%{name}.min.es5umd.js"
    es2015 umd                   : "%{name}.umd.js"
    es2015 umd minified          : "%{name}.min.umd.js"

    ".js.map" files are also produced for each bundle.

    [legacy rollup_bundle]: https://github.com/bazelbuild/rules_nodejs/blob/0.38.3/internal/rollup/rollup_bundle.bzl
    [rollup_bundle]: https://bazelbuild.github.io/rules_nodejs/Rollup.html
    [terser_minified]: https://bazelbuild.github.io/rules_nodejs/Terser.html
    [babel]: https://babeljs.io/
    """

    # Common arguments for all terser_minified targets
    common_terser_args = {
        "args": ["--comments"],
        "sourcemap": False,
    }

    # es2015
    _rollup_bundle(name = name + ".es2015", testonly = testonly, format = "iife", sourcemap = sourcemap, **kwargs)
    terser_minified(name = name + ".min.es2015", testonly = testonly, src = name + ".es2015", **common_terser_args)
    native.filegroup(name = name + ".min.es2015.js", testonly = testonly, srcs = [name + ".min.es2015"])
    terser_minified(name = name + ".min_debug.es2015", testonly = testonly, src = name + ".es2015", **common_terser_args)
    native.filegroup(name = name + ".min_debug.es2015.js", testonly = testonly, srcs = [name + ".min_debug.es2015"])

    # es5
    tsc(
        name = name,
        testonly = testonly,
        outs = [
            name + ".js",
        ],
        args = [
            "$(execpath :%s.es2015.js)" % name,
            "--types",
            "--skipLibCheck",
            "--target",
            "es5",
            "--lib",
            "es2015,dom",
            "--allowJS",
            "--outFile",
            "$(execpath :%s.js)" % name,
        ],
        data = [
            name + ".es2015.js",
        ],
    )
    terser_minified(name = name + ".min", testonly = testonly, src = name + "", **common_terser_args)
    native.filegroup(name = name + ".min.js", testonly = testonly, srcs = [name + ".min"])
    terser_minified(name = name + ".min_debug", testonly = testonly, src = name + "", debug = True, **common_terser_args)
    native.filegroup(name = name + ".min_debug.js", testonly = testonly, srcs = [name + ".min_debug"])

    # umd
    _rollup_bundle(name = name + ".umd", testonly = testonly, format = "umd", sourcemap = sourcemap, **kwargs)
    terser_minified(name = name + ".min.umd", testonly = testonly, src = name + ".umd", **common_terser_args)
    native.filegroup(name = name + ".min.umd.js", testonly = testonly, srcs = [name + ".min.umd"])
    tsc(
        name = name + ".es5umd",
        testonly = testonly,
        outs = [
            name + ".es5umd.js",
        ],
        args = [
            "$(execpath :%s.umd.js)" % name,
            "--types",
            "--skipLibCheck",
            "--target",
            "es5",
            "--lib",
            "es2015,dom",
            "--allowJS",
            "--outFile",
            "$(execpath :%s.es5umd.js)" % name,
        ],
        data = [
            name + ".umd.js",
        ],
    )
    terser_minified(name = name + ".min.es5umd", testonly = testonly, src = name + ".es5umd", **common_terser_args)
    native.filegroup(name = name + ".min.es5umd.js", testonly = testonly, srcs = [name + ".min.es5umd"])

def ts_api_guardian_test(**kwargs):
    _ts_api_guardian_test(
        tags = [
            "fixme-ivy-aot",
        ],
        **kwargs
    )

def ts_api_guardian_test_npm_package(**kwargs):
    _ts_api_guardian_test_npm_package(
        tags = [
            "fixme-ivy-aot",
        ],
        **kwargs
    )
