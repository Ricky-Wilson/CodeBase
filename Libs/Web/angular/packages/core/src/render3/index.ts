/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */
import {LifecycleHooksFeature, renderComponent, whenRendered} from './component';
import {ɵɵdefineComponent, ɵɵdefineDirective, ɵɵdefineNgModule, ɵɵdefinePipe, ɵɵsetComponentScope, ɵɵsetNgModuleScope} from './definition';
import {ɵɵCopyDefinitionFeature} from './features/copy_definition_feature';
import {ɵɵInheritDefinitionFeature} from './features/inherit_definition_feature';
import {ɵɵNgOnChangesFeature} from './features/ng_onchanges_feature';
import {ɵɵProvidersFeature} from './features/providers_feature';
import {ComponentDef, ComponentTemplate, ComponentType, DirectiveDef, DirectiveType, PipeDef, ɵɵComponentDefWithMeta, ɵɵDirectiveDefWithMeta, ɵɵFactoryDef, ɵɵPipeDefWithMeta} from './interfaces/definition';
import {getComponent, getDirectives, getHostElement, getRenderedText} from './util/discovery_utils';

export {ComponentFactory, ComponentFactoryResolver, ComponentRef, injectComponentFactoryResolver} from './component_ref';
export {ɵɵgetFactoryOf, ɵɵgetInheritedFactory} from './di';
export {getLocaleId, setLocaleId, ɵɵi18n, ɵɵi18nApply, ɵɵi18nAttributes, ɵɵi18nEnd, ɵɵi18nExp, ɵɵi18nPostprocess, ɵɵi18nStart,} from './i18n';
// clang-format off
export {
  detectChanges,
  markDirty,
  store,
  tick,
  ɵɵadvance,

  ɵɵattribute,
  ɵɵattributeInterpolate1,
  ɵɵattributeInterpolate2,
  ɵɵattributeInterpolate3,
  ɵɵattributeInterpolate4,
  ɵɵattributeInterpolate5,
  ɵɵattributeInterpolate6,
  ɵɵattributeInterpolate7,
  ɵɵattributeInterpolate8,
  ɵɵattributeInterpolateV,

  ɵɵclassMap,
  ɵɵclassMapInterpolate1,
  ɵɵclassMapInterpolate2,
  ɵɵclassMapInterpolate3,
  ɵɵclassMapInterpolate4,
  ɵɵclassMapInterpolate5,
  ɵɵclassMapInterpolate6,
  ɵɵclassMapInterpolate7,
  ɵɵclassMapInterpolate8,
  ɵɵclassMapInterpolateV,

  ɵɵclassProp,
  ɵɵcomponentHostSyntheticListener,

  ɵɵdirectiveInject,

  ɵɵelement,

  ɵɵelementContainer,
  ɵɵelementContainerEnd,
  ɵɵelementContainerStart,
  ɵɵelementEnd,
  ɵɵelementStart,

  ɵɵgetCurrentView,
  ɵɵhostProperty,
  ɵɵinjectAttribute,
  ɵɵinvalidFactory,

  ɵɵlistener,

  ɵɵnamespaceHTML,
  ɵɵnamespaceMathML,
  ɵɵnamespaceSVG,

  ɵɵnextContext,

  ɵɵprojection,
  ɵɵprojectionDef,
  ɵɵproperty,
  ɵɵpropertyInterpolate,
  ɵɵpropertyInterpolate1,
  ɵɵpropertyInterpolate2,
  ɵɵpropertyInterpolate3,
  ɵɵpropertyInterpolate4,
  ɵɵpropertyInterpolate5,
  ɵɵpropertyInterpolate6,
  ɵɵpropertyInterpolate7,
  ɵɵpropertyInterpolate8,
  ɵɵpropertyInterpolateV,

  ɵɵreference,

  // TODO: remove `select` once we've refactored all of the tests not to use it.
  ɵɵselect,
  ɵɵstyleMap,
  ɵɵstyleMapInterpolate1,
  ɵɵstyleMapInterpolate2,
  ɵɵstyleMapInterpolate3,
  ɵɵstyleMapInterpolate4,
  ɵɵstyleMapInterpolate5,
  ɵɵstyleMapInterpolate6,
  ɵɵstyleMapInterpolate7,
  ɵɵstyleMapInterpolate8,
  ɵɵstyleMapInterpolateV,

  ɵɵstyleProp,
  ɵɵstylePropInterpolate1,
  ɵɵstylePropInterpolate2,
  ɵɵstylePropInterpolate3,
  ɵɵstylePropInterpolate4,
  ɵɵstylePropInterpolate5,
  ɵɵstylePropInterpolate6,
  ɵɵstylePropInterpolate7,
  ɵɵstylePropInterpolate8,
  ɵɵstylePropInterpolateV,

  ɵɵtemplate,

  ɵɵtext,
  ɵɵtextInterpolate,
  ɵɵtextInterpolate1,
  ɵɵtextInterpolate2,
  ɵɵtextInterpolate3,
  ɵɵtextInterpolate4,
  ɵɵtextInterpolate5,
  ɵɵtextInterpolate6,
  ɵɵtextInterpolate7,
  ɵɵtextInterpolate8,
  ɵɵtextInterpolateV,

  ɵɵupdateSyntheticHostBinding,
} from './instructions/all';
export {RenderFlags} from './interfaces/definition';
export {
  AttributeMarker
} from './interfaces/node';
export {CssSelectorList, ProjectionSlots} from './interfaces/projection';
export {
  setClassMetadata,
} from './metadata';
export {NgModuleFactory, NgModuleRef, NgModuleType} from './ng_module_ref';
export {
  ɵɵpipe,
  ɵɵpipeBind1,
  ɵɵpipeBind2,
  ɵɵpipeBind3,
  ɵɵpipeBind4,
  ɵɵpipeBindV,
} from './pipe';
export {
  ɵɵpureFunction0,
  ɵɵpureFunction1,
  ɵɵpureFunction2,
  ɵɵpureFunction3,
  ɵɵpureFunction4,
  ɵɵpureFunction5,
  ɵɵpureFunction6,
  ɵɵpureFunction7,
  ɵɵpureFunction8,
  ɵɵpureFunctionV,
} from './pure_function';
export {
  ɵɵcontentQuery,
  ɵɵloadQuery,
  ɵɵqueryRefresh,
  ɵɵstaticContentQuery
,
  ɵɵstaticViewQuery,
  ɵɵviewQuery} from './query';
export {
  ɵɵdisableBindings,

  ɵɵenableBindings,
  ɵɵrestoreView,
} from './state';
export {NO_CHANGE} from './tokens';
export { ɵɵresolveBody, ɵɵresolveDocument,ɵɵresolveWindow} from './util/misc_utils';
export { ɵɵinjectPipeChangeDetectorRef,ɵɵtemplateRefExtractor} from './view_engine_compatibility_prebound';
// clang-format on

export {
  ComponentDef,
  ComponentTemplate,
  ComponentType,
  DirectiveDef,
  DirectiveType,
  getComponent,
  getDirectives,
  getHostElement,
  getRenderedText,
  LifecycleHooksFeature,
  PipeDef,
  renderComponent,
  whenRendered,
  ɵɵComponentDefWithMeta,
  ɵɵCopyDefinitionFeature,
  ɵɵdefineComponent,
  ɵɵdefineDirective,
  ɵɵdefineNgModule,
  ɵɵdefinePipe,
  ɵɵDirectiveDefWithMeta,
  ɵɵFactoryDef,
  ɵɵInheritDefinitionFeature,
  ɵɵNgOnChangesFeature,
  ɵɵPipeDefWithMeta,
  ɵɵProvidersFeature,
  ɵɵsetComponentScope,
  ɵɵsetNgModuleScope,
};
