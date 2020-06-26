import { ENV } from '@ember/-internals/environment';
import { set } from '@ember/-internals/metal';
import { Owner } from '@ember/-internals/owner';
import { assert, debugFreeze } from '@ember/debug';
import {
  Bounds,
  ComponentCapabilities,
  Destroyable,
  Dict,
  DynamicScope,
  PreparedArguments,
  VMArguments,
} from '@glimmer/interfaces';
import { ComponentRootReference, ConstReference, VersionedPathReference } from '@glimmer/reference';
import { registerDestructor } from '@glimmer/runtime';
import { CONSTANT_TAG, createTag, isConstTagged } from '@glimmer/validator';
import { EmberVMEnvironment } from '../environment';
import InternalComponentManager, { InternalDefinitionState } from './internal';

const CAPABILITIES: ComponentCapabilities = {
  dynamicLayout: false,
  dynamicTag: false,
  prepareArgs: true,
  createArgs: true,
  attributeHook: false,
  elementHook: false,
  createCaller: true,
  dynamicScope: false,
  updateHook: true,
  createInstance: true,
  wrapped: false,
  willDestroy: false,
};

export interface InputComponentState {
  env: EmberVMEnvironment;
  type: VersionedPathReference;
  instance: Destroyable;
}

const EMPTY_POSITIONAL_ARGS: VersionedPathReference[] = [];

debugFreeze(EMPTY_POSITIONAL_ARGS);

export default class InputComponentManager extends InternalComponentManager<InputComponentState> {
  getCapabilities(): ComponentCapabilities {
    return CAPABILITIES;
  }

  prepareArgs(_state: InternalDefinitionState, args: VMArguments): PreparedArguments {
    assert(
      'The `<Input />` component does not take any positional arguments',
      args.positional.length === 0
    );

    let __ARGS__: Dict<VersionedPathReference> = args.named.capture().map;

    return {
      positional: EMPTY_POSITIONAL_ARGS,
      named: {
        __ARGS__: new ConstReference(__ARGS__),
        type: args.named.get('type'),
      },
    };
  }

  create(
    env: EmberVMEnvironment,
    { ComponentClass, layout }: InternalDefinitionState,
    args: VMArguments,
    _dynamicScope: DynamicScope,
    caller: VersionedPathReference
  ): InputComponentState {
    assert('caller must be const', isConstTagged(caller));

    let type = args.named.get('type');

    let instance = ComponentClass.create({
      caller: caller.value(),
      type: type.value(),
    });

    let state = { env, type, instance };

    if (ENV._DEBUG_RENDER_TREE) {
      env.extra.debugRenderTree.create(state, {
        type: 'component',
        name: 'input',
        args: args.capture(),
        instance,
        template: layout,
      });

      registerDestructor(instance, () => env.extra.debugRenderTree.willDestroy(state));
    }

    return state;
  }

  getSelf({ env, instance }: InputComponentState): VersionedPathReference {
    return new ComponentRootReference(instance, env);
  }

  getTag() {
    if (ENV._DEBUG_RENDER_TREE) {
      // returning a const tag skips the update hook (VM BUG?)
      return createTag();
    } else {
      // an outlet has no hooks
      return CONSTANT_TAG;
    }
  }

  didRenderLayout(state: InputComponentState, bounds: Bounds): void {
    if (ENV._DEBUG_RENDER_TREE) {
      state.env.extra.debugRenderTree.didRender(state, bounds);
    }
  }

  update(state: InputComponentState): void {
    set(state.instance, 'type', state.type.value());

    if (ENV._DEBUG_RENDER_TREE) {
      state.env.extra.debugRenderTree.update(state);
    }
  }

  didUpdateLayout(state: InputComponentState, bounds: Bounds): void {
    if (ENV._DEBUG_RENDER_TREE) {
      state.env.extra.debugRenderTree.didRender(state, bounds);
    }
  }

  getDestroyable(state: InputComponentState): Destroyable {
    return state.instance;
  }
}

export const InputComponentManagerFactory = (owner: Owner) => {
  return new InputComponentManager(owner);
};
