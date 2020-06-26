import * as angular from 'angular';
import 'angular-route';

const appName = 'myApp';

angular.module(appName, [
  'ngRoute'
])
.config(['$routeProvider', '$locationProvider',
  function config($routeProvider, $locationProvider) {
    $locationProvider.html5Mode(true);

    $routeProvider.
      when('/users', {
        template: `
          <p>
            Users Page
          </p>
        `
      }).
      otherwise({
        template: ''
      });
  }]
);

export function bootstrap(el: HTMLElement) {
  return angular.bootstrap(el,  [appName]);
}
