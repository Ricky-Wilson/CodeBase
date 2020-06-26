import { privatize as P, Registry } from '@ember/-internals/container';
import { ENV } from '@ember/-internals/environment';
import Component from './component';
import Checkbox from './components/checkbox';
import Input from './components/input';
import LinkToComponent from './components/link-to';
import TextField from './components/text-field';
import TextArea from './components/textarea';
import { clientBuilder, rehydrationBuilder, serializeBuilder } from './dom';
import loc from './helpers/loc';
import { InertRenderer, InteractiveRenderer } from './renderer';
import ComponentTemplate from './templates/component';
import InputTemplate from './templates/input';
import OutletTemplate from './templates/outlet';
import RootTemplate from './templates/root';
import OutletView from './views/outlet';

export function setupApplicationRegistry(registry: Registry) {
  registry.injection('renderer', 'env', '-environment:main');

  // because we are using injections we can't use instantiate false
  // we need to use bind() to copy the function so factory for
  // association won't leak
  registry.register('service:-dom-builder', {
    create({ bootOptions }: { bootOptions: { _renderMode: string } }) {
      let { _renderMode } = bootOptions;

      switch (_renderMode) {
        case 'serialize':
          return serializeBuilder.bind(null);
        case 'rehydrate':
          return rehydrationBuilder.bind(null);
        default:
          return clientBuilder.bind(null);
      }
    },
  });
  registry.injection('service:-dom-builder', 'bootOptions', '-environment:main');
  registry.injection('renderer', 'builder', 'service:-dom-builder');

  registry.register(P`template:-root`, RootTemplate as any);
  registry.injection('renderer', 'rootTemplate', P`template:-root`);

  registry.register('renderer:-dom', InteractiveRenderer);
  registry.register('renderer:-inert', InertRenderer);

  registry.injection('renderer', 'document', 'service:-document');
}

export function setupEngineRegistry(registry: Registry) {
  registry.optionsForType('template', { instantiate: false });

  registry.register('view:-outlet', OutletView);
  registry.register('template:-outlet', OutletTemplate as any);
  registry.injection('view:-outlet', 'template', 'template:-outlet');

  registry.register(P`template:components/-default`, ComponentTemplate as any);

  registry.optionsForType('helper', { instantiate: false });

  registry.register('helper:loc', loc);

  registry.register('component:-text-field', TextField);
  registry.register('component:-checkbox', Checkbox);
  registry.register('component:link-to', LinkToComponent);

  registry.register('component:input', Input);
  registry.register('template:components/input', InputTemplate as any);

  registry.register('component:textarea', TextArea);

  if (!ENV._TEMPLATE_ONLY_GLIMMER_COMPONENTS) {
    registry.register(P`component:-default`, Component);
  }
}
