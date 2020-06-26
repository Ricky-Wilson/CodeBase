/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 */

import {BindingPipe, PropertyWrite, TmplAstReference, TmplAstVariable} from '@angular/compiler';
import * as ts from 'typescript';

import {ErrorCode, ngErrorCode} from '../../diagnostics';

import {TemplateId} from './api';
import {makeTemplateDiagnostic, TemplateSourceResolver} from './diagnostics';



/**
 * Collects `ts.Diagnostic`s on problems which occur in the template which aren't directly sourced
 * from Type Check Blocks.
 *
 * During the creation of a Type Check Block, the template is traversed and the
 * `OutOfBandDiagnosticRecorder` is called to record cases when a correct interpretation for the
 * template cannot be found. These operations create `ts.Diagnostic`s which are stored by the
 * recorder for later display.
 */
export interface OutOfBandDiagnosticRecorder {
  readonly diagnostics: ReadonlyArray<ts.Diagnostic>;

  /**
   * Reports a `#ref="target"` expression in the template for which a target directive could not be
   * found.
   *
   * @param templateId the template type-checking ID of the template which contains the broken
   * reference.
   * @param ref the `TmplAstReference` which could not be matched to a directive.
   */
  missingReferenceTarget(templateId: TemplateId, ref: TmplAstReference): void;

  /**
   * Reports usage of a `| pipe` expression in the template for which the named pipe could not be
   * found.
   *
   * @param templateId the template type-checking ID of the template which contains the unknown
   * pipe.
   * @param ast the `BindingPipe` invocation of the pipe which could not be found.
   */
  missingPipe(templateId: TemplateId, ast: BindingPipe): void;

  illegalAssignmentToTemplateVar(
      templateId: TemplateId, assignment: PropertyWrite, target: TmplAstVariable): void;

  /**
   * Reports a duplicate declaration of a template variable.
   *
   * @param templateId the template type-checking ID of the template which contains the duplicate
   * declaration.
   * @param variable the `TmplAstVariable` which duplicates a previously declared variable.
   * @param firstDecl the first variable declaration which uses the same name as `variable`.
   */
  duplicateTemplateVar(
      templateId: TemplateId, variable: TmplAstVariable, firstDecl: TmplAstVariable): void;
}

export class OutOfBandDiagnosticRecorderImpl implements OutOfBandDiagnosticRecorder {
  private _diagnostics: ts.Diagnostic[] = [];

  constructor(private resolver: TemplateSourceResolver) {}

  get diagnostics(): ReadonlyArray<ts.Diagnostic> {
    return this._diagnostics;
  }

  missingReferenceTarget(templateId: TemplateId, ref: TmplAstReference): void {
    const mapping = this.resolver.getSourceMapping(templateId);
    const value = ref.value.trim();

    const errorMsg = `No directive found with exportAs '${value}'.`;
    this._diagnostics.push(makeTemplateDiagnostic(
        mapping, ref.valueSpan || ref.sourceSpan, ts.DiagnosticCategory.Error,
        ngErrorCode(ErrorCode.MISSING_REFERENCE_TARGET), errorMsg));
  }

  missingPipe(templateId: TemplateId, ast: BindingPipe): void {
    const mapping = this.resolver.getSourceMapping(templateId);
    const errorMsg = `No pipe found with name '${ast.name}'.`;

    const sourceSpan = this.resolver.toParseSourceSpan(templateId, ast.nameSpan);
    if (sourceSpan === null) {
      throw new Error(
          `Assertion failure: no SourceLocation found for usage of pipe '${ast.name}'.`);
    }
    this._diagnostics.push(makeTemplateDiagnostic(
        mapping, sourceSpan, ts.DiagnosticCategory.Error, ngErrorCode(ErrorCode.MISSING_PIPE),
        errorMsg));
  }

  illegalAssignmentToTemplateVar(
      templateId: TemplateId, assignment: PropertyWrite, target: TmplAstVariable): void {
    const mapping = this.resolver.getSourceMapping(templateId);
    const errorMsg = `Cannot use variable '${
        assignment
            .name}' as the left-hand side of an assignment expression. Template variables are read-only.`;

    const sourceSpan = this.resolver.toParseSourceSpan(templateId, assignment.sourceSpan);
    if (sourceSpan === null) {
      throw new Error(`Assertion failure: no SourceLocation found for property binding.`);
    }
    this._diagnostics.push(makeTemplateDiagnostic(
        mapping, sourceSpan, ts.DiagnosticCategory.Error,
        ngErrorCode(ErrorCode.WRITE_TO_READ_ONLY_VARIABLE), errorMsg, {
          text: `The variable ${assignment.name} is declared here.`,
          span: target.valueSpan || target.sourceSpan,
        }));
  }

  duplicateTemplateVar(
      templateId: TemplateId, variable: TmplAstVariable, firstDecl: TmplAstVariable): void {
    const mapping = this.resolver.getSourceMapping(templateId);
    const errorMsg = `Cannot redeclare variable '${
        variable.name}' as it was previously declared elsewhere for the same template.`;

    // The allocation of the error here is pretty useless for variables declared in microsyntax,
    // since the sourceSpan refers to the entire microsyntax property, not a span for the specific
    // variable in question.
    //
    // TODO(alxhub): allocate to a tighter span once one is available.
    this._diagnostics.push(makeTemplateDiagnostic(
        mapping, variable.sourceSpan, ts.DiagnosticCategory.Error,
        ngErrorCode(ErrorCode.DUPLICATE_VARIABLE_DECLARATION), errorMsg, {
          text: `The variable '${firstDecl.name}' was first declared here.`,
          span: firstDecl.sourceSpan,
        }));
  }
}
